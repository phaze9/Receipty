from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .database import create_database, session_scope
from .jobs import JobWorker
from .mcp_server import build_mcp
from .photos import PhotosBridge
from .service import ReceiptService
from .ui import router as ui_router
from .watcher import ReceiptWatcher
from .workspace import Workspace, WorkspaceLock


@dataclass
class AppContext:
    workspace: Workspace
    sessions: object
    service: ReceiptService
    watcher: ReceiptWatcher
    worker: JobWorker
    photos: PhotosBridge


def create_app(workspace_path: str | Path, *, start_background: bool = True) -> FastAPI:
    workspace = Workspace.open(workspace_path)
    engine, sessions = create_database(workspace.database)
    service = ReceiptService(workspace, sessions)
    watcher = ReceiptWatcher(service)
    worker = JobWorker(workspace, sessions)
    helper = Path(
        os.environ.get(
            "RECEIPTY_PHOTOS_HELPER",
            Path(__file__).resolve().parents[2]
            / "macos/ReceiptyPhotosHelper/build/ReceiptyPhotosHelper.app/Contents/MacOS/ReceiptyPhotosHelper",
        )
    )
    photos = PhotosBridge(helper, workspace=workspace, service=service, sessions=sessions)
    context = AppContext(workspace, sessions, service, watcher, worker, photos)
    mcp = build_mcp(context)
    mcp_app = mcp.streamable_http_app()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks: list[asyncio.Task] = []
        lock = WorkspaceLock(workspace.lock)
        lock.acquire()
        try:
            async with mcp.session_manager.run():
                with session_scope(sessions) as session:
                    service.backfill_titles(session)
                if start_background:
                    tasks = [
                        asyncio.create_task(watcher.run()),
                        asyncio.create_task(worker.run()),
                    ]
                try:
                    yield
                finally:
                    watcher.stop()
                    worker.stop()
                    for task in tasks:
                        task.cancel()
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            lock.release()
            engine.dispose()

    app = FastAPI(title="Receipty", version="0.1.0", lifespan=lifespan)
    app.state.context = context
    app.include_router(api_router())
    app.include_router(ui_router())
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    app.mount("/mcp", mcp_app)
    return app

