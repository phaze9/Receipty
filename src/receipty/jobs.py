from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .extraction import extract, file_identity
from .models import Attachment, Job
from .workspace import Workspace


class JobWorker:
    def __init__(self, workspace: Workspace, sessions: sessionmaker[Session]):
        self.workspace = workspace
        self.sessions = sessions
        self.stopping = False

    async def run(self) -> None:
        self._recover_jobs()
        while not self.stopping:
            processed = await asyncio.to_thread(self.process_one)
            if not processed:
                await asyncio.sleep(0.5)

    def stop(self) -> None:
        self.stopping = True

    def _recover_jobs(self) -> None:
        with self.sessions() as session:
            for job in session.scalars(select(Job).where(Job.state == "running")):
                job.state = "queued"
            session.commit()

    def process_one(self) -> bool:
        with self.sessions() as session:
            job = session.scalar(
                select(Job).where(Job.state == "queued").order_by(Job.created_at).limit(1)
            )
            if not job:
                return False
            job.state = "running"
            job.attempts += 1
            session.commit()
            attachment = session.get(Attachment, job.attachment_id)
            try:
                if not attachment or not attachment.path:
                    raise FileNotFoundError("Attachment has no local file")
                path = self.workspace.absolute_path(attachment.path)
                result = extract(path)
                attachment.sha256 = result.sha256
                attachment.size = result.size
                attachment.media_type = result.media_type
                attachment.extracted_text = result.text
                attachment.extraction_method = result.method
                attachment.file_identity = file_identity(path)
                thumbnail = self._thumbnail(path, attachment.id)
                if thumbnail:
                    attachment.provider_metadata = {
                        **attachment.provider_metadata,
                        "thumbnail": thumbnail.relative_to(self.workspace.metadata).as_posix(),
                    }
                attachment.status = "ready"
                attachment.error = None
                job.state = "done"
                job.error = None
            except Exception as exc:
                if attachment:
                    attachment.status = "error"
                    attachment.error = str(exc)
                job.state = "failed"
                job.error = str(exc)
            session.commit()
            return True

    def _thumbnail(self, path: Path, attachment_id: str) -> Path | None:
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
            return None
        from PIL import Image

        destination = self.workspace.thumbnails / f"{attachment_id}.jpg"
        with Image.open(path) as image:
            image.thumbnail((640, 640))
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image.save(destination, "JPEG", quality=82)
        return destination

    def retry(self, attachment_id: str) -> None:
        with self.sessions() as session:
            attachment = session.get(Attachment, attachment_id)
            if not attachment:
                raise LookupError(attachment_id)
            attachment.status = "pending"
            attachment.error = None
            session.add(Job(attachment_id=attachment.id))
            session.commit()

