from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select
from watchfiles import Change, awatch

from .database import session_scope
from .models import Attachment
from .service import ReceiptService


WATCHED_SUFFIXES = {
    ".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp",
    ".txt", ".text", ".md", ".csv", ".json", ".docx",
}


class ReceiptWatcher:
    def __init__(self, service: ReceiptService):
        self.service = service
        self.stopping = False

    @staticmethod
    def supported(path: Path) -> bool:
        return path.suffix.lower() in WATCHED_SUFFIXES and not path.name.startswith(".")

    def scan(self) -> int:
        root = self.service.workspace.receipt_files
        discovered = 0
        with session_scope(self.service.sessions) as session:
            existing = {
                attachment.path: attachment
                for attachment in session.scalars(
                    select(Attachment).where(Attachment.path.is_not(None))
                )
                if attachment.path
            }
            paths = [path for path in root.rglob("*") if path.is_file() and self.supported(path)]
            present = {self.service.workspace.relative_path(path) for path in paths}
            for relative, attachment in existing.items():
                if relative.startswith("receipt-files/") and relative not in present:
                    attachment.status = "missing"
                    attachment.error = "File is missing from the workspace"
            session.flush()
            for path in paths:
                relative = self.service.workspace.relative_path(path)
                if relative not in existing:
                    self.service.discover_file(session, path)
                    discovered += 1
        return discovered

    async def run(self) -> None:
        await asyncio.to_thread(self.scan)
        async for changes in awatch(
            self.service.workspace.receipt_files,
            debounce=800,
            step=200,
        ):
            if self.stopping:
                return
            relevant = any(
                change in {Change.added, Change.modified, Change.deleted}
                and self.supported(Path(changed_path))
                for change, changed_path in changes
            )
            if relevant:
                await asyncio.to_thread(self.scan)

    def stop(self) -> None:
        self.stopping = True

