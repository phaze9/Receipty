from pathlib import Path

from receipty.database import create_database, session_scope
from receipty.photos import PhotosBridge
from receipty.schemas import ReceiptCreate
from receipty.service import ReceiptService
from receipty.workspace import Workspace


class FakePhotos(PhotosBridge):
    def asset(self, asset_id):
        return {"id": asset_id, "filename": "photo.txt", "creationYear": 2026, "mediaType": "image"}

    def export(self, asset_id, destination):
        destination.write_text("photo bytes")
        return {"path": str(destination)}

    def albums(self):
        return [{"id": "album-1", "title": "Receipts", "count": 1}]

    def assets(self, album_id=None):
        return [self.asset("asset-1")]


def test_managed_photo_import_and_album_snapshot(tmp_path: Path):
    workspace = Workspace.open(tmp_path)
    _, sessions = create_database(workspace.database)
    service = ReceiptService(workspace, sessions)
    photos = FakePhotos(workspace=workspace, service=service, sessions=sessions)
    with session_scope(sessions) as session:
        receipt = service.create(session, ReceiptCreate(fields={}))
        receipt_id = receipt.id

    photo = photos.link_asset(receipt_id, "asset-1")
    assert photo.path == "receipt-files/2026/photo.txt"
    assert (workspace.root / photo.path).exists()
    album = photos.link_album(receipt_id, "album-1", "snapshot")
    assert album.provider_metadata["assetIds"] == ["asset-1"]



def test_photos_denied_explains_settings_and_hides_request(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from receipty.app import create_app

    app = create_app(tmp_path, start_background=False)
    monkeypatch.setattr(app.state.context.photos, "authorization", lambda: {"status": "denied"})
    with TestClient(app) as client:
        response = client.get("/photos")
        assert response.status_code == 200
        assert "macOS will not show the permission prompt again" in response.text
        assert "Privacy_Photos" in response.text
        assert "Request Photos access" not in response.text


def test_photos_request_preserves_receipt_and_displays_failure(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from receipty.app import create_app
    from receipty.photos import PhotosUnavailable

    app = create_app(tmp_path, start_background=False)
    bridge = app.state.context.photos
    monkeypatch.setattr(bridge, "authorization", lambda: {"status": "notDetermined"})
    monkeypatch.setattr(bridge, "request_authorization", lambda: {"status": "denied"})
    with TestClient(app) as client:
        response = client.post("/photos/authorize", data={"receipt_id": "receipt-1"}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/photos?receipt_id=receipt-1"

        def fail():
            raise PhotosUnavailable("Photos helper timed out")

        monkeypatch.setattr(bridge, "request_authorization", fail)
        response = client.post("/photos/authorize", data={"receipt_id": "receipt-1"})
        assert response.status_code == 200
        assert "Photos helper timed out" in response.text
        assert '/receipts/receipt-1' in response.text
