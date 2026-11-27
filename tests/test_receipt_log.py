from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import receipty.receipt_log as receipt_log
from receipty.app import create_app
from receipty.mcp_server import build_mcp


@pytest.fixture(autouse=True)
def _configure_logging(monkeypatch):
    # Logging is skipped when these are unset; dummy values are fine because
    # generate_message is monkeypatched in every test.
    monkeypatch.setenv("RECEIPTY_LLM_URL", "http://example.invalid/v1/chat/completions")
    monkeypatch.setenv("RECEIPTY_MODEL_CONNECT", "/nonexistent/model_connect.py")


def test_ui_create_logs_entry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RECEIPTY_LOG", "1")
    monkeypatch.setattr(
        receipt_log, "generate_message",
        lambda action, detail, channel="UI": "A receipt was created in the UI",
    )
    app = create_app(tmp_path / "workspace", start_background=False)
    with TestClient(app) as client:
        response = client.post(
            "/receipts",
            data={"title": "Cafe", "date": "todo", "description": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
    log = (tmp_path / "workspace" / "LOG.md").read_text(encoding="utf-8")
    assert "A receipt was created in the UI" in log
    assert "—" in log


def test_llm_failure_falls_back(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RECEIPTY_LOG", "1")

    def boom(action, detail, channel="UI"):
        raise RuntimeError("endpoint unreachable")

    monkeypatch.setattr(receipt_log, "generate_message", boom)
    app = create_app(tmp_path / "workspace", start_background=False)
    with TestClient(app) as client:
        response = client.post(
            "/receipts",
            data={"title": "Cafe", "date": "todo", "description": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
    log = (tmp_path / "workspace" / "LOG.md").read_text(encoding="utf-8")
    assert "UI action: create receipt" in log
    assert "LLM unavailable" in log


def test_disabled_by_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RECEIPTY_LOG", "0")
    called = []

    def fake(action, detail, channel="UI"):
        called.append(action)
        return "message"

    monkeypatch.setattr(receipt_log, "generate_message", fake)
    app = create_app(tmp_path / "workspace", start_background=False)
    with TestClient(app) as client:
        response = client.post(
            "/receipts",
            data={"title": "Cafe", "date": "todo", "description": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
    assert called == []
    assert not (tmp_path / "workspace" / "LOG.md").exists()


def test_api_calls_logged(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RECEIPTY_LOG", "1")
    called = []

    def fake(action, detail, channel="API"):
        called.append((action, channel))
        return "message"

    monkeypatch.setattr(receipt_log, "generate_message", fake)
    app = create_app(tmp_path / "workspace", start_background=False)
    with TestClient(app) as client:
        response = client.post("/api/v1/receipts", json={"fields": {"title": "Cafe", "date": "todo"}})
        assert response.status_code == 201
    assert called == [("create receipt", "API")]
    assert "message" in (tmp_path / "workspace" / "LOG.md").read_text(encoding="utf-8")


def test_mcp_calls_logged(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RECEIPTY_LOG", "1")
    called = []

    def fake(action, detail, channel="MCP"):
        called.append((action, channel))
        return "message"

    monkeypatch.setattr(receipt_log, "generate_message", fake)
    app = create_app(tmp_path / "workspace", start_background=False)
    context = app.state.context
    mcp = build_mcp(context)
    result = mcp._tool_manager.get_tool("create_receipt").fn(
        {"title": "Cafe", "date": "todo"}, "draft"
    )
    assert result["fields"]["title"] == "Cafe"
    assert called == [("create receipt", "MCP")]
    assert "message" in (tmp_path / "workspace" / "LOG.md").read_text(encoding="utf-8")


def test_reads_not_logged(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RECEIPTY_LOG", "1")
    called = []

    def fake(action, detail, channel="API"):
        called.append(action)
        return "message"

    monkeypatch.setattr(receipt_log, "generate_message", fake)
    app = create_app(tmp_path / "workspace", start_background=False)
    with TestClient(app) as client:
        response = client.get("/api/v1/receipts")
        assert response.status_code == 200
    assert called == []
    assert not (tmp_path / "workspace" / "LOG.md").exists()


def test_unconfigured_skips_logging(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RECEIPTY_LOG", "1")
    monkeypatch.delenv("RECEIPTY_LLM_URL", raising=False)
    monkeypatch.delenv("RECEIPTY_MODEL_CONNECT", raising=False)
    called = []

    def fake(action, detail, channel="UI"):
        called.append(action)
        return "message"

    monkeypatch.setattr(receipt_log, "generate_message", fake)
    app = create_app(tmp_path / "workspace", start_background=False)
    with TestClient(app) as client:
        response = client.post(
            "/receipts",
            data={"title": "Cafe", "date": "todo", "description": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303
    assert called == []
    assert not (tmp_path / "workspace" / "LOG.md").exists()


def test_log_file_is_append_only(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RECEIPTY_LOG", "1")
    counter = {"n": 0}

    def fake(action, detail, channel="UI"):
        counter["n"] += 1
        return f"message {counter['n']}"

    monkeypatch.setattr(receipt_log, "generate_message", fake)
    app = create_app(tmp_path / "workspace", start_background=False)
    with TestClient(app) as client:
        for _ in range(2):
            client.post(
                "/receipts",
                data={"title": "Cafe", "date": "todo", "description": ""},
                follow_redirects=False,
            )
    log = (tmp_path / "workspace" / "LOG.md").read_text(encoding="utf-8")
    assert "message 1" in log
    assert "message 2" in log
