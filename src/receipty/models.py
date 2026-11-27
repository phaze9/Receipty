from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_string() -> str:
    return str(uuid.uuid4())


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    state: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    origin: Mapped[str] = mapped_column(String(32), default="manual")
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    receipt_id: Mapped[str] = mapped_column(ForeignKey("receipts.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="file")
    path: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    provider_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_identity: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    receipt: Mapped[Receipt] = relationship(back_populates="attachments")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    attachment_id: Mapped[str] = mapped_column(ForeignKey("attachments.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="extract")
    state: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

