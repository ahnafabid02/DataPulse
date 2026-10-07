"""Health-only central API shell. No agent/business endpoints in M1."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Engine

from datapulse import __version__
from datapulse.central.config import Settings
from datapulse.central.db import build_engine, database_ready
from datapulse.central.logging import configure_logging


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    ui_directory: Path | None = None,
) -> FastAPI:
    config = settings if settings is not None else Settings()
    database = engine if engine is not None else build_engine(config)
    logger = configure_logging(config.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if engine is None:
                database.dispose()

    app = FastAPI(title="DataPulse central foundation", version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def request_metadata(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid4())
        started = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # The outer ASGI server must not log a traceback with future patient values.
            response = JSONResponse({"error": "internal_error", "request_id": request_id}, 500)
        finally:
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health/live", response_model=LiveResponse, tags=["health"])
    def live() -> LiveResponse:
        return LiveResponse()

    @app.get(
        "/health/ready",
        response_model=ReadyResponse,
        responses={503: {"model": ReadyResponse}},
        tags=["health"],
    )
    def ready(response: Response) -> ReadyResponse:
        if not database_ready(database):
            response.status_code = 503
            return ReadyResponse(status="not_ready")
        return ReadyResponse(status="ready")

    interface = ui_directory if ui_directory is not None else Path(__file__).parent / "static"

    @app.get("/", include_in_schema=False)
    def workspace() -> Response:
        if not (interface / "index.html").is_file():
            return JSONResponse({"error": "interface_not_built"}, status_code=503)
        return FileResponse(interface / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon() -> Response:
        if not (interface / "favicon.svg").is_file():
            return Response(status_code=404)
        return FileResponse(interface / "favicon.svg", media_type="image/svg+xml")

    if (interface / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=interface / "assets"), name="interface-assets")

    return app
