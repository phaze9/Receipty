from pathlib import Path

import pytest

from receipty.workspace import Workspace, WorkspaceLock


def test_workspace_initializes_without_touching_unrelated_files(tmp_path: Path):
    unrelated = tmp_path / "family-notes.txt"
    unrelated.write_text("keep me")
    workspace = Workspace.open(tmp_path)
    assert workspace.database.parent == tmp_path / ".receipty"
    assert workspace.receipt_files.is_dir()
    assert unrelated.read_text() == "keep me"


def test_workspace_rejects_external_and_escaping_paths(tmp_path: Path):
    workspace = Workspace.open(tmp_path / "workspace")
    with pytest.raises(ValueError):
        workspace.relative_path(tmp_path / "outside.pdf")
    with pytest.raises(ValueError):
        workspace.relative_path("../outside.pdf")


def test_workspace_lock_prevents_two_servers(tmp_path: Path):
    workspace = Workspace.open(tmp_path)
    first = WorkspaceLock(workspace.lock)
    second = WorkspaceLock(workspace.lock)
    first.acquire()
    try:
        with pytest.raises(RuntimeError):
            second.acquire()
    finally:
        first.release()

