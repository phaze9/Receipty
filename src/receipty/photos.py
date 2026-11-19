from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .database import session_scope
from .models import Attachment


class PhotosUnavailable(RuntimeError):
    pass


class PhotosBridge:
    def __init__(self, helper_path: Path | None = None, *, workspace=None, service=None, sessions=None):
        self.helper_path = helper_path
        self.workspace = workspace
        self.service = service
        self.sessions = sessions

    def available(self) -> bool:
        return bool(self.helper_path and self.helper_path.exists())

    def call(self, command: str, **arguments: Any) -> Any:
        if not self.available():
            raise PhotosUnavailable(
                "Receipty Photos helper is not built; run the macOS helper build first"
            )
        request = json.dumps({"command": command, "arguments": arguments}) + "\n"
        try:
            result = subprocess.run(
                [str(self.helper_path)],
                input=request,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PhotosUnavailable("Photos helper timed out. Check for a macOS permission dialog and try again.") from exc
        except OSError as exc:
            raise PhotosUnavailable(f"Could not start Photos helper: {exc}") from exc
        if result.returncode != 0:
            raise PhotosUnavailable(result.stderr.strip() or "Photos helper failed")
        response = json.loads(result.stdout)
        if not response.get("ok"):
            raise PhotosUnavailable(response.get("error", "Photos helper failed"))
        return response.get("result")

    def authorization(self) -> dict[str, Any]:
        return self.call("authorization")

    def request_authorization(self) -> dict[str, Any]:
        return self.call("requestAuthorization")

    def albums(self) -> list[dict[str, Any]]:
        return self.call("listAlbums")

    def assets(self, album_id: str | None = None) -> list[dict[str, Any]]:
        return self.call("listAssets", albumId=album_id)

    def asset(self, asset_id: str) -> dict[str, Any]:
        return self.call("getAsset", assetId=asset_id)

    def export(self, asset_id: str, destination: Path) -> dict[str, Any]:
        return self.call("exportAsset", assetId=asset_id, destination=str(destination))

    def link_asset(self, receipt_id: str, asset_id: str, mode: str = "managed_copy") -> Attachment:
        metadata = self.asset(asset_id)
        if mode == "reference":
            with session_scope(self.sessions) as session:
                self.service.get(session, receipt_id)
                attachment = Attachment(
                    receipt_id=receipt_id, kind="apple_photo", provider_id=asset_id,
                    name=metadata.get("filename") or asset_id,
                    media_type=metadata.get("mediaType"), status="ready",
                    provider_metadata=metadata,
                )
                session.add(attachment)
                session.flush()
                session.expunge(attachment)
                return attachment

        year = str(metadata.get("creationYear") or "unknown-year")
        filename = Path(metadata.get("filename") or f"{asset_id}.bin").name
        directory = self.workspace.receipt_files / year
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / filename
        if destination.exists():
            destination = directory / f"{destination.stem}-{asset_id[:8]}{destination.suffix}"
        self.export(asset_id, destination)
        with session_scope(self.sessions) as session:
            attachment = self.service.attach_file(session, receipt_id, destination)
            attachment.kind = "apple_photo"
            attachment.provider_id = asset_id
            attachment.provider_metadata = metadata
            session.flush()
            session.expunge(attachment)
            return attachment

    def link_album(self, receipt_id: str, album_id: str, mode: str = "dynamic") -> Attachment:
        album = next((item for item in self.albums() if item.get("id") == album_id), None)
        if not album:
            raise LookupError("Photos album not found")
        metadata = {**album, "mode": mode}
        if mode == "snapshot":
            metadata["assetIds"] = [item["id"] for item in self.assets(album_id)]
        with session_scope(self.sessions) as session:
            self.service.get(session, receipt_id)
            attachment = Attachment(
                receipt_id=receipt_id, kind="apple_photos_album", provider_id=album_id,
                name=album.get("title") or "Photos album", status="ready",
                provider_metadata=metadata,
            )
            session.add(attachment)
            session.flush()
            session.expunge(attachment)
            return attachment

    def resolve_album(self, attachment: Attachment) -> list[dict[str, Any]]:
        if attachment.kind != "apple_photos_album":
            raise ValueError("Attachment is not a Photos album")
        if attachment.provider_metadata.get("mode") == "snapshot":
            result = []
            for asset_id in attachment.provider_metadata.get("assetIds", []):
                try:
                    result.append(self.asset(asset_id))
                except PhotosUnavailable:
                    result.append({"id": asset_id, "missing": True})
            return result
        return self.assets(attachment.provider_id)

