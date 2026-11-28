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
from .receipt_log import format_fields, log_action


def router() -> APIRouter:
    api = APIRouter(prefix="/api/v1")

    def context(request: Request):
        return request.app.state.context

    def apply_patch(ctx, receipt_id: str, body: ReceiptPatch):
        try:
            with session_scope(ctx.sessions) as session:
                ctx.service.patch(session, receipt_id, body)
                return ctx.service.get(session, receipt_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

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
        ctx = context(request)
        result = {"discovered": ctx.watcher.scan()}
        log_action(ctx.workspace, "rescan workspace", "receipt-files", channel="API")
        return result

    @api.get("/receipts", response_model=list[ReceiptOut])
    def list_receipts(
        request: Request,
        query: str | None = None,
        state: str | None = None,
        field_key: str | None = None,
        field_value: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        sort: str | None = None,
        direction: str = "asc",
    ):
        ctx = context(request)
        with session_scope(ctx.sessions) as session:
            try:
                return ctx.service.list(
                    session, query=query, state=state,
                    field_filters={field_key: field_value} if field_key and field_value is not None else None,
                    offset=offset, limit=limit, sort=sort, direction=direction,
                    exclude_deleted=not state,
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc

    @api.post("/receipts", response_model=ReceiptOut, status_code=201)
    def create_receipt(request: Request, body: ReceiptCreate):
        ctx = context(request)
        try:
            with session_scope(ctx.sessions) as session:
                receipt = ctx.service.create(session, body)
                session.flush()
                created = ctx.service.get(session, receipt.id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log_action(ctx.workspace, "create receipt", f"{created.id}: {format_fields(created.fields)}", channel="API",
                  link=f"{str(request.base_url).rstrip('/')}/receipts/{created.id}")
        return created

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
        result = apply_patch(ctx, receipt_id, body)
        log_action(ctx.workspace, "update receipt", f"{receipt_id}: {format_fields(result.fields)}", channel="API",
                  link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}")
        return result

    @api.post("/receipts/{receipt_id}/archive", response_model=ReceiptOut)
    def archive_receipt(request: Request, receipt_id: str):
        ctx = context(request)
        result = apply_patch(ctx, receipt_id, ReceiptPatch(state="archived"))
        log_action(ctx.workspace, "archive receipt", receipt_id, channel="API",
                  link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}")
        return result

    @api.post("/receipts/{receipt_id}/restore", response_model=ReceiptOut)
    def restore_receipt(request: Request, receipt_id: str):
        ctx = context(request)
        result = apply_patch(ctx, receipt_id, ReceiptPatch(state="draft"))
        log_action(ctx.workspace, "restore receipt", receipt_id, channel="API",
                  link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}")
        return result

    @api.post("/receipts/{receipt_id}/purge", status_code=204)
    def purge_receipt(request: Request, receipt_id: str):
        ctx = context(request)
        try:
            with session_scope(ctx.sessions) as session:
                ctx.service.purge(session, receipt_id)
        except NotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log_action(ctx.workspace, "purge receipt", receipt_id, channel="API",
                  link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}")

    @api.post("/receipts/merge", response_model=ReceiptOut)
    def merge_receipts(request: Request, body: MergeRequest):
        ctx = context(request)
        try:
            with session_scope(ctx.sessions) as session:
                merged = ctx.service.merge(session, body.source_ids, body.target_id)
                target_id = merged.id
                result = ctx.service.get(session, merged.id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log_action(ctx.workspace, "merge receipts", f"sources {len(body.source_ids)}, target {target_id}", channel="API",
                  link=f"{str(request.base_url).rstrip('/')}/receipts/{target_id}")
        return result

    @api.post("/receipts/{receipt_id}/attachments", response_model=AttachmentOut)
    def attach_file(request: Request, receipt_id: str, body: AttachFile):
        ctx = context(request)
        try:
            with session_scope(ctx.sessions) as session:
                attachment = ctx.service.attach_file(session, receipt_id, body.path)
                result = attachment
        except (NotFoundError, FileNotFoundError) as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log_action(ctx.workspace, "attach file", f"receipt {receipt_id}, path {body.path}", channel="API",
                  link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}")
        return result

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
        ctx = context(request)
        try:
            ctx.worker.retry(attachment_id)
        except LookupError as exc:
            raise HTTPException(404, "Attachment not found") from exc
        log_action(ctx.workspace, "retry extraction", attachment_id, channel="API")
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
        log_action(ctx.workspace, "detach attachment", attachment_id, channel="API")

    @api.get("/photos/authorization")
    def photos_authorization(request: Request):
        return context(request).photos.authorization()

    @api.post("/photos/authorization")
    def photos_request_authorization(request: Request):
        ctx = context(request)
        result = ctx.photos.request_authorization()
        log_action(ctx.workspace, "authorize photos", "", channel="API")
        return result

    @api.get("/photos/albums")
    def photos_albums(request: Request):
        return context(request).photos.albums()

    @api.get("/photos/assets")
    def photos_assets(request: Request, album_id: str | None = None):
        return context(request).photos.assets(album_id)

    @api.post("/receipts/{receipt_id}/photos/assets", response_model=AttachmentOut)
    def link_photo_asset(request: Request, receipt_id: str, body: PhotoAssetLink):
        ctx = context(request)
        result = ctx.photos.link_asset(receipt_id, body.asset_id, body.mode)
        log_action(ctx.workspace, "link photo asset", f"receipt {receipt_id}, asset {body.asset_id}", channel="API",
                  link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}")
        return result

    @api.post("/receipts/{receipt_id}/photos/albums", response_model=AttachmentOut)
    def link_photo_album(request: Request, receipt_id: str, body: PhotoAlbumLink):
        ctx = context(request)
        try:
            result = ctx.photos.link_album(receipt_id, body.album_id, body.mode)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        log_action(ctx.workspace, "link photo album", f"receipt {receipt_id}, album {body.album_id}", channel="API",
                  link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}")
        return result

    @api.get("/attachments/{attachment_id}/photos/assets")
    def resolve_photo_album(request: Request, attachment_id: str):
        ctx = context(request)
        with session_scope(ctx.sessions) as session:
            attachment = session.get(Attachment, attachment_id)
            if not attachment:
                raise HTTPException(404, "Attachment not found")
            return ctx.photos.resolve_album(attachment)

    return api

