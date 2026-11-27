from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AttachmentOut(BaseModel):
    id: str
    receipt_id: str
    kind: str
    path: str | None
    provider_id: str | None
    name: str
    media_type: str | None
    size: int | None
    sha256: str | None
    status: str
    extracted_text: str | None
    extraction_method: str | None
    error: str | None
    provider_metadata: dict[str, Any]

    model_config = {"from_attributes": True}


class ReceiptOut(BaseModel):
    id: str
    state: str
    origin: str
    fields: dict[str, Any]
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentOut] = []

    model_config = {"from_attributes": True}


class ReceiptCreate(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    state: Literal["draft", "active"] = "draft"


class ReceiptPatch(BaseModel):
    fields: dict[str, Any] | None = None
    state: Literal["draft", "active", "archived", "deleted"] | None = None


class AttachFile(BaseModel):
    path: str


class MergeRequest(BaseModel):
    source_ids: list[str]
    target_id: str | None = None


class PhotoAssetLink(BaseModel):
    asset_id: str
    mode: Literal["managed_copy", "reference"] = "managed_copy"


class PhotoAlbumLink(BaseModel):
    album_id: str
    mode: Literal["dynamic", "snapshot"] = "dynamic"

