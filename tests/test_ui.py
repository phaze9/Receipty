from pathlib import Path

from fastapi.testclient import TestClient

from receipty.app import create_app


def test_ui_create_and_list_show_date(tmp_path: Path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        response = client.post(
            "/receipts",
            data={"title": "Cafe", "date": "todo", "description": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
        list_page = client.get("/")
        assert list_page.status_code == 200
        assert "todo" in list_page.text
        detail_page = client.get(response.headers["location"])
        assert detail_page.status_code == 200
        assert 'name="date" value="todo"' in detail_page.text

        missing_date = client.post(
            "/receipts",
            data={"title": "No date", "date": "", "description": ""},
            follow_redirects=False,
        )
        assert missing_date.status_code == 400
