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


def test_ui_sort_by_date_and_title(tmp_path: Path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        for title, date in [("Bravo", "2026-11-20"), ("Alpha", "2026-11-25"), ("Charlie", "todo")]:
            response = client.post(
                "/receipts",
                data={"title": title, "date": date, "description": ""},
                follow_redirects=False,
            )
            assert response.status_code == 303

        page = client.get("/", params={"state": "", "sort": "date", "direction": "desc"})
        titles = [line.split("</strong>")[0].split("<strong>")[1] for line in page.text.splitlines() if "<strong>" in line]
        assert titles == ["Alpha", "Bravo", "Charlie"]

        page = client.get("/", params={"state": "", "sort": "title", "direction": "asc"})
        titles = [line.split("</strong>")[0].split("<strong>")[1] for line in page.text.splitlines() if "<strong>" in line]
        assert titles == ["Alpha", "Bravo", "Charlie"]

        page = client.get("/", params={"state": "", "sort": "title", "direction": "desc"})
        titles = [line.split("</strong>")[0].split("<strong>")[1] for line in page.text.splitlines() if "<strong>" in line]
        assert titles == ["Charlie", "Bravo", "Alpha"]

        # REST endpoint supports the same sort params.
        data = client.get("/api/v1/receipts", params={"state": "", "sort": "date", "direction": "asc"}).json()
        assert [item["fields"]["title"] for item in data] == ["Bravo", "Alpha", "Charlie"]
        bad = client.get("/api/v1/receipts", params={"sort": "bogus"})
        assert bad.status_code == 400


def test_state_select_submits_form_immediately(tmp_path: Path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        page = client.get("/", params={"sort": "date", "direction": "desc"})
        assert 'name="state" onchange="this.form.submit()"' in page.text
        assert 'type="hidden" name="sort" value="date"' in page.text
        assert 'type="hidden" name="direction" value="desc"' in page.text

        page = client.get("/", params={"state": "active"})
        assert 'name="state" onchange="this.form.submit()"' in page.text
        assert 'name="sort"' not in page.text


def test_ui_list_shows_description(tmp_path: Path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace, start_background=False)
    with TestClient(app) as client:
        response = client.post(
            "/receipts",
            data={"title": "Cafe", "date": "todo", "description": "Morning latte"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        page = client.get("/")
        assert "Morning latte" in page.text
