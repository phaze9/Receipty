from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from .database import session_scope
from .models import Attachment, Job
from .schemas import (
    AttachFile, AttachmentOut, MergeRequest, PhotoAlbumLink, PhotoAssetLink,
    ReceiptCreate, ReceiptOut, ReceiptPatch,
)
from .service import NotFoundError


def router() -> APIRouter:
    api = APIRouter(prefix="/api/v1")

    def context(request: Request):
        return request.app.state.context

    @api.get("/workspace")
    def workspace_info(request: Request):
        ctx = context(request)
        return {
            "root": str(ctx.workspace.root),
            "receipt_files": str(ctx.workspace.receipt_files),
            "photos_available": ctx.photos.available(),
        }

    @api.post("/workspace/rescan")
    def rescan(request: Request):
        return {"discovered": context(request).watcher.scan()}

    @api.get("/receipts", response_model=list[ReceiptOut])
    def list_receipts(
        request: Request,
        query: str | None = None,
        state: str | None = None,
        field_key: str | None = None,
        field_value: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ):
        ctx = context(request)
        with session_scope(ctx.sessions) as session:
            return ctx.service.list(
                session, query=query, state=state,
                field_filters={field_key: field_value} if field_key and field_value is not None else None,
                offset=offset, limit=limit
            )

    @api.post("/receipts", response_model=ReceiptOut, status_code=201)
    def create_receipt(request: Request, body: ReceiptCreate):
        ctx = context(request)
        with session_scope(ctx.sessions) as session:
            receipt = ctx.service.create(session, body)
            session.flush()
            return ctx.service.get(session, receipt.id)

    @api.get("/receipts/{receipt_id}", response_model=ReceiptOut)
    def get_receipt(request: Request, receipt_id: str):
        ctx = context(request)
        try:
            with session_scope(ctx.sessions) as session:
                return ctx.service.get(session, receipt_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @api.patch("/receipts/{receipt_id}", response_model=ReceiptOut)
    def update_receipt(request: Request, receipt_id: str, body: ReceiptPatch):
        ctx = context(request)
        try:
            with session_scope(ctx.sessions) as session:
                ctx.service.patch(session, receipt_id, body)
                return ctx.service.get(session, receipt_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @api.post("/receipts/{receipt_id}/archive", response_model=ReceiptOut)
    def archive_receipt(request: Request, receipt_id: str):
        return update_receipt(request, receipt_id, ReceiptPatch(state="archived"))

    @api.post("/receipts/{receipt_id}/restore", response_model=ReceiptOut)
    def restore_receipt(request: Request, receipt_id: str):
        return update_receipt(request, receipt_id, ReceiptPatch(state="draft"))

    @api.post("/receipts/merge", response_model=ReceiptOut)
    def merge_receipts(request: Request, body: MergeRequest):
        ctx = context(request)
        with session_scope(ctx.sessions) as session:
            return ctx.service.merge(session, body.source_ids, body.target_id)

    @api.post("/receipts/{receipt_id}/attachments", response_model=AttachmentOut)
    def attach_file(request: Request, receipt_id: str, body: AttachFile):
        ctx = context(request)
        try:
            with session_scope(ctx.sessions) as session:
                return ctx.service.attach_file(session, receipt_id, body.path)
        except (NotFoundError, FileNotFoundError) as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @api.get("/attachments/{attachment_id}/content")
    def attachment_content(request: Request, attachment_id: str):
        ctx = context(request)
        with session_scope(ctx.sessions) as session:
            attachment = session.get(Attachment, attachment_id)
            if not attachment or not attachment.path:
                raise HTTPException(404, "Attachment not found")
            path = ctx.workspace.absolute_path(attachment.path)
            if not path.is_file():
                raise HTTPException(404, "Attachment file is missing")
            return FileResponse(path, media_type=attachment.media_type, filename=attachment.name)

    @api.get("/attachments/{attachment_id}/thumbnail")
    def attachment_thumbnail(request: Request, attachment_id: str):
        ctx = context(request)
        with session_scope(ctx.sessions) as session:
            attachment = session.get(Attachment, attachment_id)
            relative = attachment.provider_metadata.get("thumbnail") if attachment else None
            if not relative:
                raise HTTPException(404, "Thumbnail not available")
            path = (ctx.workspace.metadata / relative).resolve()
            if not path.is_relative_to(ctx.workspace.thumbnails) or not path.is_file():
                raise HTTPException(404, "Thumbnail not available")
            return FileResponse(path, media_type="image/jpeg")

    @api.post("/attachments/{attachment_id}/retry", status_code=202)
    def retry_attachment(request: Request, attachment_id: str):
        try:
            context(request).worker.retry(attachment_id)
        except LookupError as exc:
            raise HTTPException(404, "Attachment not found") from exc
        return {"status": "queued"}

    @api.delete("/attachments/{attachment_id}", status_code=204)
    def detach(request: Request, attachment_id: str):
        ctx = context(request)
        with session_scope(ctx.sessions) as session:
            attachment = session.get(Attachment, attachment_id)
            if not attachment:
                raise HTTPException(404, "Attachment not found")
            for job in session.scalars(select(Job).where(Job.attachment_id == attachment.id)):
                session.delete(job)
            session.delete(attachment)

    @api.get("/photos/authorization")
    def photos_authorization(request: Request):
        return context(request).photos.authorization()

    @api.post("/photos/authorization")
    def photos_request_authorization(request: Request):
        return context(request).photos.request_authorization()

    @api.get("/photos/albums")
    def photos_albums(request: Request):
        return context(request).photos.albums()

    @api.get("/photos/assets")
    def photos_assets(request: Request, album_id: str | None = None):
        return context(request).photos.assets(album_id)

    @api.post("/receipts/{receipt_id}/photos/assets", response_model=AttachmentOut)
    def link_photo_asset(request: Request, receipt_id: str, body: PhotoAssetLink):
        return context(request).photos.link_asset(receipt_id, body.asset_id, body.mode)

    @api.post("/receipts/{receipt_id}/photos/albums", response_model=AttachmentOut)
    def link_photo_album(request: Request, receipt_id: str, body: PhotoAlbumLink):
        try:
            return context(request).photos.link_album(receipt_id, body.album_id, body.mode)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @api.get("/attachments/{attachment_id}/photos/assets")
    def resolve_photo_album(request: Request, attachment_id: str):
        ctx = context(request)
        with session_scope(ctx.sessions) as session:
            attachment = session.get(Attachment, attachment_id)
            if not attachment:
                raise HTTPException(404, "Attachment not found")
            return ctx.photos.resolve_album(attachment)

    return api

