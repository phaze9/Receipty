from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from .extraction import file_identity
from .models import Attachment, Job, Receipt
from .schemas import ReceiptCreate, ReceiptPatch
from .workspace import Workspace


class NotFoundError(LookupError):
    pass


class ReceiptService:
    def __init__(self, workspace: Workspace, sessions: sessionmaker[Session]):
        self.workspace = workspace
        self.sessions = sessions

    @staticmethod
    def _receipt_query():
        return select(Receipt).options(selectinload(Receipt.attachments))

    def get(self, session: Session, receipt_id: str) -> Receipt:
        receipt = session.scalar(self._receipt_query().where(Receipt.id == receipt_id))
        if not receipt:
            raise NotFoundError(f"Receipt not found: {receipt_id}")
        return receipt

    def create(self, session: Session, body: ReceiptCreate, *, origin: str = "manual") -> Receipt:
        receipt = Receipt(state=body.state, origin=origin, fields=body.fields)
        session.add(receipt)
        session.flush()
        return receipt

    def patch(self, session: Session, receipt_id: str, body: ReceiptPatch) -> Receipt:
        receipt = self.get(session, receipt_id)
        if body.fields is not None:
            receipt.fields = body.fields
        if body.state is not None:
            receipt.state = body.state
        session.flush()
        return receipt

    def list(
        self, session: Session, *, query: str | None = None, state: str | None = None,
        field_filters: dict[str, Any] | None = None, offset: int = 0, limit: int = 50,
    ) -> list[Receipt]:
        statement = self._receipt_query().order_by(Receipt.updated_at.desc())
        if state:
            statement = statement.where(Receipt.state == state)
        for key, value in (field_filters or {}).items():
            statement = statement.where(Receipt.fields[key].as_string() == str(value))
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(
                    cast(Receipt.fields, String).ilike(pattern),
                    Receipt.attachments.any(Attachment.name.ilike(pattern)),
                    Receipt.attachments.any(Attachment.extracted_text.ilike(pattern)),
                )
            )
        statement = statement.offset(offset).limit(limit)
        return list(session.scalars(statement))

    def attach_file(self, session: Session, receipt_id: str, path: str | Path) -> Attachment:
        receipt = self.get(session, receipt_id)
        relative = self.workspace.relative_path(path)
        absolute = self.workspace.absolute_path(relative)
        if not absolute.is_file():
            raise FileNotFoundError(absolute)
        existing = session.scalar(select(Attachment).where(Attachment.path == relative))
        if existing:
            if existing.receipt_id != receipt.id:
                raise ValueError("File is already attached to another receipt")
            return existing
        attachment = Attachment(
            receipt_id=receipt.id,
            kind="file",
            path=relative,
            name=absolute.name,
            media_type=mimetypes.guess_type(absolute.name)[0],
            size=absolute.stat().st_size,
            file_identity=file_identity(absolute),
            status="pending",
        )
        session.add(attachment)
        session.flush()
        session.add(Job(attachment_id=attachment.id))
        return attachment

    def discover_file(self, session: Session, path: Path) -> Receipt | None:
        relative = self.workspace.relative_path(path)
        if session.scalar(select(Attachment.id).where(Attachment.path == relative)):
            return None
        identity = file_identity(path)
        missing = session.scalar(
            select(Attachment).where(
                Attachment.file_identity == identity, Attachment.status == "missing"
            )
        )
        if missing:
            missing.path = relative
            missing.name = path.name
            missing.status = "pending"
            missing.error = None
            session.add(Job(attachment_id=missing.id))
            return self.get(session, missing.receipt_id)
        receipt = self.create(
            session, ReceiptCreate(fields={"title": path.stem}, state="draft"), origin="watcher"
        )
        self.attach_file(session, receipt.id, path)
        return receipt

    def merge(self, session: Session, source_ids: list[str], target_id: str | None = None) -> Receipt:
        unique = list(dict.fromkeys(source_ids))
        if target_id and target_id not in unique:
            unique.insert(0, target_id)
        if len(unique) < 2:
            raise ValueError("At least two receipts are required")
        target = self.get(session, target_id or unique[0])
        for source_id in unique:
            if source_id == target.id:
                continue
            source = self.get(session, source_id)
            for attachment in list(source.attachments):
                attachment.receipt_id = target.id
            merged = dict(source.fields)
            merged.update(target.fields)
            target.fields = merged
            source.state = "archived"
        session.flush()
        return self.get(session, target.id)

    def reconcile(self, session: Session) -> None:
        for attachment in session.scalars(
            select(Attachment).where(Attachment.kind == "file", Attachment.path.is_not(None))
        ):
            path = self.workspace.absolute_path(attachment.path)
            if not path.is_file() and attachment.status != "missing":
                attachment.status = "missing"
                attachment.error = "File is missing"

    def workspace_info(self, session: Session) -> dict[str, Any]:
        return {
            "root": str(self.workspace.root),
            "database": str(self.workspace.database),
            "receipt_files": str(self.workspace.receipt_files),
            "receipts": len(list(session.scalars(select(Receipt.id)))),
            "pending_jobs": len(list(session.scalars(select(Job.id).where(Job.state == "queued")))),
        }

