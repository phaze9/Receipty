from __future__ import annotations

import json
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .service import DELETE_RETENTION_DAYS
from .database import session_scope
from .receipt_log import format_fields, log_action
from .photos import PhotosUnavailable
from .schemas import ReceiptCreate, ReceiptPatch


templates = Jinja2Templates(directory=str(__import__("pathlib").Path(__file__).parent / "templates"))


def router() -> APIRouter:
    ui = APIRouter()

    @ui.get("/", response_class=HTMLResponse)
    def index(
        request: Request,
        query: str | None = None,
        state: str = "draft",
        sort: str | None = None,
        direction: str | None = None,
    ):
        ctx = request.app.state.context
        if sort not in ("date", "title"):
            sort, direction = None, None
        if sort and direction not in ("asc", "desc"):
            direction = "desc" if sort == "date" else "asc"
        if sort and not direction:
            direction = "desc" if sort == "date" else "asc"
        with session_scope(ctx.sessions) as session:
            receipts = ctx.service.list(session, query=query, state=state or None, sort=sort, direction=direction or "asc")
            params = {"state": state}
            if query:
                params["query"] = query
            def href(field, dir):
                return "/?" + urlencode({**params, "sort": field, "direction": dir})
            return templates.TemplateResponse(
                request,
                "index.html",
                {
                    "receipts": receipts, "query": query or "", "state": state,
                    "sort": sort, "direction": direction,
                    "href_date": href("date", "asc" if sort == "date" and direction == "desc" else "desc"),
                    "href_title": href("title", "desc" if sort == "title" and direction == "asc" else "asc"),
                },
            )

    @ui.post("/receipts")
    def create(request: Request, title: str = Form(""), date: str = Form(""), description: str = Form("")):
        ctx = request.app.state.context
        fields = {}
        if title:
            fields["title"] = title
        if date:
            fields["date"] = date
        if description:
            fields["description"] = description
        try:
            with session_scope(ctx.sessions) as session:
                receipt = ctx.service.create(session, ReceiptCreate(fields=fields))
                receipt_id = receipt.id
                stored_fields = dict(receipt.fields)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log_action(
            ctx.workspace, "create receipt", f"{receipt_id}: {format_fields(stored_fields)}",
            link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}",
        )
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)

    @ui.get("/receipts/{receipt_id}", response_class=HTMLResponse)
    def detail(request: Request, receipt_id: str):
        ctx = request.app.state.context
        with session_scope(ctx.sessions) as session:
            receipt = ctx.service.get(session, receipt_id)
            extras = {k: v for k, v in receipt.fields.items() if k not in ("title", "date", "description")}
            return templates.TemplateResponse(
                request,
                "detail.html",
                {
                    "receipt": receipt,
                    "title": receipt.fields.get("title", ""),
                    "date": receipt.fields.get("date", ""),
                    "description": receipt.fields.get("description", ""),
                    "fields_json": json.dumps(extras, indent=2),
                    "purgeable": ctx.service.purgeable(receipt),
                    "retention_days": DELETE_RETENTION_DAYS,
                },
            )

    @ui.post("/receipts/{receipt_id}")
    def update(
        request: Request,
        receipt_id: str,
        title: str = Form(""),
        date: str = Form(""),
        description: str = Form(""),
        fields_json: str = Form(...),
        state: str = Form(...),
    ):
        try:
            extras = json.loads(fields_json)
            if not isinstance(extras, dict):
                raise ValueError("Fields must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
        extras.pop("title", None)
        extras.pop("date", None)
        extras.pop("description", None)
        fields = {**extras, "title": title, "date": date}
        if description:
            fields["description"] = description
        ctx = request.app.state.context
        try:
            with session_scope(ctx.sessions) as session:
                patched = ctx.service.patch(session, receipt_id, ReceiptPatch(fields=fields, state=state))
                stored_fields = dict(patched.fields)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log_action(
            ctx.workspace, "update receipt", f"{receipt_id}: {format_fields(stored_fields)}",
            link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}",
        )
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)

    @ui.post("/receipts/{receipt_id}/purge")
    def purge(request: Request, receipt_id: str):
        ctx = request.app.state.context
        try:
            with session_scope(ctx.sessions) as session:
                ctx.service.purge(session, receipt_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log_action(
            ctx.workspace, "purge receipt", receipt_id,
            link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}",
        )
        return RedirectResponse("/", status_code=303)

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
        log_action(request.app.state.context.workspace, "authorize photos", receipt_id)
        target = "/photos"
        if receipt_id:
            target += "?" + urlencode({"receipt_id": receipt_id})
        return RedirectResponse(target, status_code=303)

    @ui.post("/receipts/{receipt_id}/photos/assets")
    def attach_photo_asset(
        request: Request, receipt_id: str, asset_id: str = Form(...), mode: str = Form("managed_copy")
    ):
        request.app.state.context.photos.link_asset(receipt_id, asset_id, mode)
        log_action(
            request.app.state.context.workspace, "attach photo asset", f"receipt {receipt_id}, asset {asset_id}",
            link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}",
        )
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)

    @ui.post("/receipts/{receipt_id}/photos/albums")
    def attach_photo_album(
        request: Request, receipt_id: str, album_id: str = Form(...), mode: str = Form("dynamic")
    ):
        request.app.state.context.photos.link_album(receipt_id, album_id, mode)
        log_action(
            request.app.state.context.workspace, "attach photo album", f"receipt {receipt_id}, album {album_id}",
            link=f"{str(request.base_url).rstrip('/')}/receipts/{receipt_id}",
        )
        return RedirectResponse(f"/receipts/{receipt_id}", status_code=303)

    return ui

