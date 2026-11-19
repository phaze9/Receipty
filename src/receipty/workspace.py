from __future__ import annotations

import json
import os
import fcntl
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    root: Path
    metadata: Path
    receipt_files: Path
    database: Path
    thumbnails: Path
    cache: Path
    config: Path
    lock: Path

    @classmethod
    def open(cls, root: str | Path, *, create: bool = True) -> "Workspace":
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            if not create:
                raise FileNotFoundError(root_path)
            root_path.mkdir(parents=True)
        if not root_path.is_dir():
            raise NotADirectoryError(root_path)
        metadata = root_path / ".receipty"
        ws = cls(
            root=root_path,
            metadata=metadata,
            receipt_files=root_path / "receipt-files",
            database=metadata / "receipty.sqlite3",
            thumbnails=metadata / "thumbnails",
            cache=metadata / "cache",
            config=metadata / "workspace.json",
            lock=metadata / "server.lock",
        )
        if create:
            ws.initialize()
        return ws

    def initialize(self) -> None:
        self.metadata.mkdir(exist_ok=True)
        self.receipt_files.mkdir(exist_ok=True)
        self.thumbnails.mkdir(exist_ok=True)
        self.cache.mkdir(exist_ok=True)
        if not self.config.exists():
            self.config.write_text(
                json.dumps({"version": 1, "receipt_files": "receipt-files"}, indent=2) + "\n",
                encoding="utf-8",
            )

    def relative_path(self, path: str | Path) -> str:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve(strict=False)
        try:
            return resolved.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise ValueError("Attachment paths must remain inside the workspace") from exc

    def absolute_path(self, relative: str) -> Path:
        self.relative_path(relative)
        return (self.root / relative).resolve(strict=False)


class WorkspaceLock:
    def __init__(self, path: Path):
        self.path = path
        self._handle = None

    def acquire(self) -> None:
        self._handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._handle.close()
            self._handle = None
            raise RuntimeError(f"Workspace is already in use: {self.path.parent.parent}") from exc
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(str(os.getpid()))
        self._handle.flush()

    def release(self) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None

