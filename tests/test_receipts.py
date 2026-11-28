from pathlib import Path

from fastapi.testclient import TestClient

from receipty.app import create_app


def test_rest_crud_attach_extract_search_and_archive(tmp_path: Path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        created = client.post("/api/v1/receipts", json={"fields": {"title": "Lotus receipt", "date": "2026-11-27", "vendor": "Lotus"}})
        assert created.status_code == 201
        receipt_id = created.json()["id"]

        source = workspace / "receipt-files" / "2026" / "lotus.txt"
        source.parent.mkdir(parents=True)
        source.write_text("Total THB 425")
        attached = client.post(
            f"/api/v1/receipts/{receipt_id}/attachments",
            json={"path": "receipt-files/2026/lotus.txt"},
        )
        assert attached.status_code == 200
        attachment_id = attached.json()["id"]
        assert app.state.context.worker.process_one()

        found = client.get("/api/v1/receipts", params={"query": "425"})
        assert [item["id"] for item in found.json()] == [receipt_id]
        filtered = client.get(
            "/api/v1/receipts", params={"field_key": "vendor", "field_value": "Lotus"}
        )
        assert [item["id"] for item in filtered.json()] == [receipt_id]
        assert client.get(f"/api/v1/attachments/{attachment_id}/content").text == "Total THB 425"

        archived = client.post(f"/api/v1/receipts/{receipt_id}/archive")
        assert archived.json()["state"] == "archived"
        assert source.exists()


def test_watcher_creates_drafts_for_nested_files_and_reconciles_rename(tmp_path: Path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    watched = workspace / "receipt-files" / "2025" / "shop.txt"
    watched.parent.mkdir(parents=True)
    watched.write_text("receipt")
    assert app.state.context.watcher.scan() == 1

    with TestClient(app) as client:
        receipts = client.get("/api/v1/receipts", params={"state": "draft"}).json()
        assert len(receipts) == 1
        receipt_id = receipts[0]["id"]
        renamed = watched.with_name("renamed.txt")
        watched.rename(renamed)
        app.state.context.watcher.scan()
        receipt = client.get(f"/api/v1/receipts/{receipt_id}").json()
        assert len(receipt["attachments"]) == 1
        assert receipt["attachments"][0]["path"].endswith("renamed.txt")

        renamed.unlink()
        app.state.context.watcher.scan()
        receipt = client.get(f"/api/v1/receipts/{receipt_id}").json()
        assert receipt["attachments"][0]["status"] == "missing"


def test_mcp_streamable_http_initializes(tmp_path: Path):
    app = create_app(tmp_path / "workspace", start_background=False)
    with TestClient(app, base_url="http://localhost:8000") as client:
        response = client.post(
            "/mcp/",
            headers={"Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["result"]["serverInfo"]["name"] == "Receipty"


def test_merge_moves_attachments_and_archives_sources(tmp_path: Path):
    app = create_app(tmp_path / "workspace", start_background=False)
    with TestClient(app) as client:
        first = client.post("/api/v1/receipts", json={"fields": {"title": "A", "date": "2026-11-01", "vendor": "A"}}).json()
        second = client.post("/api/v1/receipts", json={"fields": {"title": "B", "date": "2026-11-02", "total": 10}}).json()
        merged = client.post(
            "/api/v1/receipts/merge",
            json={"source_ids": [first["id"], second["id"]], "target_id": first["id"]},
        )
        assert merged.status_code == 200
        assert merged.json()["fields"] == {"title": "A", "total": 10, "vendor": "A", "date": "2026-11-01"}
        assert client.get(f"/api/v1/receipts/{second['id']}").json()["state"] == "archived"



def test_title_and_date_are_mandatory_and_backfill_legacy_receipts(tmp_path: Path):
    from sqlalchemy import select

    from receipty.database import session_scope
    from receipty.models import Receipt

    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        missing = client.post("/api/v1/receipts", json={"fields": {"vendor": "Lotus"}})
        assert missing.status_code == 400
        blank_title = client.post("/api/v1/receipts", json={"fields": {"title": "  ", "date": "todo"}})
        assert blank_title.status_code == 400
        missing_date = client.post("/api/v1/receipts", json={"fields": {"title": "Lotus"}})
        assert missing_date.status_code == 400
        blank_date = client.post("/api/v1/receipts", json={"fields": {"title": "Lotus", "date": "  "}})
        assert blank_date.status_code == 400

        created = client.post("/api/v1/receipts", json={"fields": {"title": "Desk receipt", "date": "todo"}})
        assert created.status_code == 201
        receipt_id = created.json()["id"]

        bad_patch = client.patch(
            f"/api/v1/receipts/{receipt_id}", json={"fields": {"title": "X", "vendor": "No date"}}
        )
        assert bad_patch.status_code == 400

        with session_scope(app.state.context.sessions) as session:
            receipt = session.scalar(select(Receipt).where(Receipt.id == receipt_id))
            receipt.fields = {"description": "Legacy description"}

        with session_scope(app.state.context.sessions) as session:
            assert app.state.context.service.backfill_required_fields(session) == 1
            receipt = session.scalar(select(Receipt).where(Receipt.id == receipt_id))
            assert receipt.fields["title"] == "Legacy description"
            assert receipt.fields["date"] == "todo"
            assert "description" not in receipt.fields

        with session_scope(app.state.context.sessions) as session:
            receipt = session.scalar(select(Receipt).where(Receipt.id == receipt_id))
            receipt.fields = {"title": "Cafe", "description": "Cafe"}

        with session_scope(app.state.context.sessions) as session:
            assert app.state.context.service.backfill_required_fields(session) == 1
            receipt = session.scalar(select(Receipt).where(Receipt.id == receipt_id))
            assert receipt.fields == {"title": "Cafe", "date": "todo"}


def test_delete_purge_flow_and_read_only(tmp_path: Path):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from receipty.database import session_scope
    from receipty.models import Receipt

    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/receipts",
            json={"fields": {"title": "Cafe", "date": "2026-11-27"}},
        )
        assert created.status_code == 201
        receipt_id = created.json()["id"]

        deleted = client.patch(f"/api/v1/receipts/{receipt_id}", json={"state": "deleted"})
        assert deleted.status_code == 200
        assert deleted.json()["state"] == "deleted"
        assert deleted.json()["deleted_at"] is not None

        # Read-only: fields and state changes are refused.
        assert client.patch(f"/api/v1/receipts/{receipt_id}", json={"fields": {"title": "X", "date": "todo"}}).status_code == 400
        assert client.patch(f"/api/v1/receipts/{receipt_id}", json={"state": "draft"}).status_code == 400
        assert client.post(f"/api/v1/receipts/{receipt_id}/restore").status_code == 400

        # Purge is blocked inside the retention window.
        blocked = client.post(f"/api/v1/receipts/{receipt_id}/purge")
        assert blocked.status_code == 400

        # After the window passes, purge succeeds and the receipt is gone.
        with session_scope(app.state.context.sessions) as session:
            receipt = session.scalar(select(Receipt).where(Receipt.id == receipt_id))
            receipt.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)

        purged = client.post(f"/api/v1/receipts/{receipt_id}/purge")
        assert purged.status_code == 204
        assert client.get(f"/api/v1/receipts/{receipt_id}").status_code == 404


def test_deleted_receipt_detail_view_shows_purge_button(tmp_path: Path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/receipts",
            json={"fields": {"title": "Cafe", "date": "2026-11-27"}},
        )
        receipt_id = created.json()["id"]
        assert client.patch(f"/api/v1/receipts/{receipt_id}", json={"state": "deleted"}).status_code == 200

        page = client.get(f"/receipts/{receipt_id}")
        assert page.status_code == 200
        assert "Purge" in page.text
        assert "Save" not in page.text
        assert 'action="/receipts/%s/purge"' % receipt_id in page.text

        # Purge is disabled while still inside the retention window.
        assert "disabled" in page.text

        # List view shows the deleted state filter.
        assert "deleted" in client.get("/", params={"state": "deleted"}).text


def test_api_list_hides_deleted_unless_requested(tmp_path: Path):
    from receipty.app import create_app
    from fastapi.testclient import TestClient

    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/receipts",
            json={"fields": {"title": "Deleted One", "date": "2026-11-27"}},
        )
        receipt_id = created.json()["id"]
        assert client.patch(f"/api/v1/receipts/{receipt_id}", json={"state": "deleted"}).status_code == 200
        client.post("/api/v1/receipts", json={"fields": {"title": "Visible One", "date": "2026-11-27"}})

        default = client.get("/api/v1/receipts").json()
        titles = [item["fields"]["title"] for item in default]
        assert "Deleted One" not in titles
        assert "Visible One" in titles

        deleted = client.get("/api/v1/receipts", params={"state": "deleted"}).json()
        titles = [item["fields"]["title"] for item in deleted]
        assert titles == ["Deleted One"]
