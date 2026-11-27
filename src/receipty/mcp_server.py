from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .database import session_scope
from .schemas import ReceiptCreate, ReceiptOut, ReceiptPatch


def build_mcp(context):
    mcp = FastMCP(
        "Receipty",
        instructions="Search and manage receipts in the currently opened Receipty workspace.",
        streamable_http_path="/",
        json_response=True,
    )

    @mcp.tool()
    def workspace_info() -> dict[str, Any]:
        """Return workspace paths, counts, and pending work."""
        with session_scope(context.sessions) as session:
            info = context.service.workspace_info(session)
            info["photos_available"] = context.photos.available()
            return info

    @mcp.tool()
    def rescan_workspace() -> dict[str, int]:
        """Scan receipt-files recursively and register new supported files."""
        return {"discovered": context.watcher.scan()}

    @mcp.tool()
    def search_receipts(
        query: str | None = None, state: str | None = None,
        field_filters: dict[str, Any] | None = None, offset: int = 0, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List or full-text search receipts and extracted attachment content."""
        with session_scope(context.sessions) as session:
            receipts = context.service.list(
                session, query=query, state=state, field_filters=field_filters,
                offset=offset, limit=min(limit, 200)
            )
            return [ReceiptOut.model_validate(receipt).model_dump(mode="json") for receipt in receipts]

    @mcp.tool()
    def get_receipt(receipt_id: str) -> dict[str, Any]:
        """Get one receipt and all attachments."""
        with session_scope(context.sessions) as session:
            return ReceiptOut.model_validate(
                context.service.get(session, receipt_id)
            ).model_dump(mode="json")

    @mcp.tool()
    def create_receipt(fields: dict[str, Any], state: str = "draft") -> dict[str, Any]:
        """Create a receipt with arbitrary JSON fields."""
        with session_scope(context.sessions) as session:
            receipt = context.service.create(session, ReceiptCreate(fields=fields, state=state))
            return ReceiptOut.model_validate(
                context.service.get(session, receipt.id)
            ).model_dump(mode="json")

    @mcp.tool()
    def update_receipt(
        receipt_id: str, fields: dict[str, Any] | None = None, state: str | None = None
    ) -> dict[str, Any]:
        """Replace receipt fields and/or change its state."""
        with session_scope(context.sessions) as session:
            receipt = context.service.patch(
                session, receipt_id, ReceiptPatch(fields=fields, state=state)
            )
            return ReceiptOut.model_validate(receipt).model_dump(mode="json")

    @mcp.tool()
    def attach_workspace_file(receipt_id: str, path: str) -> dict[str, Any]:
        """Attach an existing file inside the workspace and enqueue extraction."""
        with session_scope(context.sessions) as session:
            attachment = context.service.attach_file(session, receipt_id, path)
            return {"id": attachment.id, "path": attachment.path, "status": attachment.status}

    @mcp.tool()
    def merge_receipts(source_ids: list[str], target_id: str | None = None) -> dict[str, Any]:
        """Move attachments into one receipt and archive the source receipts."""
        with session_scope(context.sessions) as session:
            receipt = context.service.merge(session, source_ids, target_id)
            return ReceiptOut.model_validate(receipt).model_dump(mode="json")

    @mcp.tool()
    def archive_receipt(receipt_id: str) -> dict[str, Any]:
        """Archive a receipt without deleting its files."""
        with session_scope(context.sessions) as session:
            receipt = context.service.patch(session, receipt_id, ReceiptPatch(state="archived"))
            return ReceiptOut.model_validate(receipt).model_dump(mode="json")

    @mcp.tool()
    def restore_receipt(receipt_id: str) -> dict[str, Any]:
        """Restore an archived receipt to draft state."""
        with session_scope(context.sessions) as session:
            receipt = context.service.patch(session, receipt_id, ReceiptPatch(state="draft"))
            return ReceiptOut.model_validate(receipt).model_dump(mode="json")

    @mcp.tool()
    def purge_receipt(receipt_id: str) -> dict[str, Any]:
        """Permanently delete a deleted receipt (after the retention period)."""
        with session_scope(context.sessions) as session:
            context.service.purge(session, receipt_id)
            return {"purged": receipt_id}

    @mcp.tool()
    def retry_extraction(attachment_id: str) -> dict[str, str]:
        """Queue attachment text extraction again."""
        context.worker.retry(attachment_id)
        return {"status": "queued"}

    @mcp.tool()
    def list_photos_albums() -> list[dict[str, Any]]:
        """List accessible Apple Photos albums through the macOS helper."""
        return context.photos.albums()

    @mcp.tool()
    def list_photos_assets(album_id: str | None = None) -> list[dict[str, Any]]:
        """List accessible Apple Photos assets, optionally within an album."""
        return context.photos.assets(album_id)

    @mcp.tool()
    def link_photos_asset(
        receipt_id: str, asset_id: str, mode: str = "managed_copy"
    ) -> dict[str, Any]:
        """Link or import an Apple Photos asset into a receipt."""
        attachment = context.photos.link_asset(receipt_id, asset_id, mode)
        return {"id": attachment.id, "kind": attachment.kind, "path": attachment.path}

    @mcp.tool()
    def link_photos_album(
        receipt_id: str, album_id: str, mode: str = "dynamic"
    ) -> dict[str, Any]:
        """Attach an Apple Photos album dynamically or as an asset-ID snapshot."""
        attachment = context.photos.link_album(receipt_id, album_id, mode)
        return {"id": attachment.id, "kind": attachment.kind, "mode": mode}

    return mcp

