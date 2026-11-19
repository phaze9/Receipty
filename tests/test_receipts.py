from pathlib import Path

from fastapi.testclient import TestClient

from receipty.app import create_app


def test_rest_crud_attach_extract_search_and_archive(tmp_path: Path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        created = client.post("/api/v1/receipts", json={"fields": {"vendor": "Lotus"}})
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
        first = client.post("/api/v1/receipts", json={"fields": {"vendor": "A"}}).json()
        second = client.post("/api/v1/receipts", json={"fields": {"total": 10}}).json()
        merged = client.post(
            "/api/v1/receipts/merge",
            json={"source_ids": [first["id"], second["id"]], "target_id": first["id"]},
        )
        assert merged.status_code == 200
        assert merged.json()["fields"] == {"total": 10, "vendor": "A"}
        assert client.get(f"/api/v1/receipts/{second['id']}").json()["state"] == "archived"

