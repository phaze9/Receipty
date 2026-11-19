from __future__ import annotations

import json
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .database import session_scope
from .photos import PhotosUnavailable
from .schemas import ReceiptCreate, ReceiptPatch


templates = Jinja2Templates(directory=str(__import__("pathlib").Path(__file__).parent / "templates"))


def router() -> APIRouter:
    ui = APIRouter()

    @ui.get("/", response_class=HTMLResponse)
    def index(request: Request, query: str | None = None, state: str = "draft"):
        ctx = request.app.state.context
        with session_scope(ctx.sessions) as session:
            receipts = ctx.service.list(session, query=query, state=state or None)
            return templates.TemplateResponse(
                request,
                "index.html",
                {"receipts": receipts, "query": query or "", "state": state},
            )

    @ui.post("/receipts")
    def create(request: Request, title: str = Form("")):
        ctx = request.app.state.context
        with session_scope(ctx.sessions) as session:
            receipt = ctx.service.create(
                session, ReceiptCreate(fields={"title": title} if title else {})
            )
            receipt_id = receipt.id
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)

    @ui.get("/receipts/{receipt_id}", response_class=HTMLResponse)
    def detail(request: Request, receipt_id: str):
        ctx = request.app.state.context
        with session_scope(ctx.sessions) as session:
            receipt = ctx.service.get(session, receipt_id)
            return templates.TemplateResponse(
                request,
                "detail.html",
                {"receipt": receipt, "fields_json": json.dumps(receipt.fields, indent=2)},
            )

    @ui.post("/receipts/{receipt_id}")
    def update(request: Request, receipt_id: str, fields_json: str = Form(...), state: str = Form(...)):
        try:
            fields = json.loads(fields_json)
            if not isinstance(fields, dict):
                raise ValueError("Fields must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
        ctx = request.app.state.context
        with session_scope(ctx.sessions) as session:
            ctx.service.patch(session, receipt_id, ReceiptPatch(fields=fields, state=state))
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)

    @ui.get("/photos", response_class=HTMLResponse)
    def photos(request: Request, receipt_id: str | None = None, album_id: str | None = None):
        return render_photos(request, receipt_id, album_id)

    def render_photos(request: Request, receipt_id=None, album_id=None, error=None):
        ctx = request.app.state.context
        authorization = None
        albums = []
        assets = []
        try:
            authorization = ctx.photos.authorization()
            if authorization.get("status") in {"authorized", "limited"}:
                albums = ctx.photos.albums()
                if album_id:
                    assets = ctx.photos.assets(album_id)
        except PhotosUnavailable as exc:
            error = str(exc)
        return templates.TemplateResponse(
            request, "photos.html",
            {"authorization": authorization, "albums": albums, "assets": assets,
             "receipt_id": receipt_id, "error": error},
        )

    @ui.post("/photos/authorize")
    def authorize_photos(request: Request, receipt_id: str = Form("")):
        try:
            request.app.state.context.photos.request_authorization()
        except PhotosUnavailable as exc:
            return render_photos(request, receipt_id or None, error=str(exc))
        target = "/photos"
        if receipt_id:
            target += "?" + urlencode({"receipt_id": receipt_id})
        return RedirectResponse(target, status_code=303)

    @ui.post("/receipts/{receipt_id}/photos/assets")
    def attach_photo_asset(
        request: Request, receipt_id: str, asset_id: str = Form(...), mode: str = Form("managed_copy")
    ):
        request.app.state.context.photos.link_asset(receipt_id, asset_id, mode)
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)

    @ui.post("/receipts/{receipt_id}/photos/albums")
    def attach_photo_album(
        request: Request, receipt_id: str, album_id: str = Form(...), mode: str = Form("dynamic")
    ):
        request.app.state.context.photos.link_album(receipt_id, album_id, mode)
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)

    return ui

