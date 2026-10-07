"""Central M2 app: health, static workspace and authenticated registration APIs."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from datapulse import __version__
from datapulse.central.access import audit
from datapulse.central.api import install_api
from datapulse.central.config import Settings
from datapulse.central.db import build_engine, database_ready
from datapulse.central.logging import configure_logging
from datapulse.central.models import Principal


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

    app = FastAPI(title="DataPulse central", version=__version__, lifespan=lifespan)
    app.include_router(install_api(database, config))
    login_windows: dict[str, list[float]] = {}
    login_lock = Lock()

    def error_response(request: Request, status: int, message: str) -> JSONResponse:
        code = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            413: "body_too_large",
            422: "invalid_request",
            429: "rate_limited",
            503: "unavailable",
        }.get(status, "request_failed")
        if request.url.path.startswith("/v1/"):
            try:
                with Session(database) as session, session.begin():
                    actor_id = getattr(request.state, "actor_id", None)
                    actor = session.get(Principal, actor_id) if actor_id else None
                    audit(
                        session,
                        actor,
                        "security.request_denied" if status < 500 else "security.request_failed",
                        "request",
                        None,
                        request.state.request_id,
                        {"status": status, "method": request.method, "code": code},
                    )
            except SQLAlchemyError:
                status, code, message = (
                    503,
                    "unavailable",
                    "The system could not safely record this request. Try again shortly.",
                )
        return JSONResponse(
            {
                "error": {"code": code, "message": message, "details": None},
                "request_id": request.state.request_id,
            },
            status,
            headers={"Retry-After": "900"} if status == 429 else None,
        )

    @app.exception_handler(HTTPException)
    def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return error_response(request, error.status_code, str(error.detail))

    @app.exception_handler(RequestValidationError)
    def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # FastAPI's default validation response can echo secrets from invalid input.
        return error_response(
            request,
            422,
            "Check the required details and try again. Unexpected fields are not accepted.",
        )

    @app.exception_handler(IntegrityError)
    def conflict_error(request: Request, error: IntegrityError) -> JSONResponse:
        duplicate = (
            getattr(error.orig, "sqlstate", None) == "23505"
            or getattr(error.orig, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_UNIQUE"
        )
        if duplicate:
            return error_response(request, 409, "That hospital or source code already exists.")
        return error_response(
            request, 503, "The system could not safely save this action. Try again shortly."
        )

    @app.exception_handler(SQLAlchemyError)
    def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return error_response(
            request, 503, "The database is temporarily unavailable. Try again shortly."
        )

    @app.middleware("http")
    async def request_metadata(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        started = perf_counter()
        status_code = 500
        response: Response
        try:
            throttled = False
            if request.url.path == "/v1/auth/login":
                peer = request.client.host if request.client else "unknown"
                with login_lock:
                    now = perf_counter()
                    for key in list(login_windows):
                        login_windows[key] = [
                            value for value in login_windows[key] if now - value < 900
                        ]
                        if not login_windows[key]:
                            del login_windows[key]
                    attempts = login_windows.get(peer, [])
                    throttled = len(attempts) >= 20 or (
                        peer not in login_windows and len(login_windows) >= 1000
                    )
                    if not throttled:
                        login_windows[peer] = [*attempts, now]
            # Count actual streamed bytes, including requests without Content-Length.
            body = bytearray()
            if throttled:
                response = error_response(
                    request, 429, "Too many sign-in attempts. Wait 15 minutes before trying again."
                )
            elif request.url.path.startswith("/v1/") and request.method in {"POST", "PATCH", "PUT"}:
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 65536:
                        response = error_response(request, 413, "This request is too large.")
                        break
                else:
                    request._body = bytes(body)
                    response = await call_next(request)
            else:
                response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # The outer ASGI server must not log a traceback with future patient values.
            if request.url.path.startswith("/v1/"):
                response = error_response(
                    request, 500, "The system could not complete this action. Try again shortly."
                )
            else:
                response = JSONResponse({"error": "internal_error", "request_id": request_id}, 500)
            status_code = response.status_code
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
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path in {"/docs", "/redoc"}:
            # FastAPI's documentation HTML uses CDN assets and inline initialization.
            # The application workspace keeps the stricter same-origin policy above.
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com "
                "'unsafe-inline'; font-src https://fonts.gstatic.com; "
                "img-src 'self' https://fastapi.tiangolo.com data:; frame-ancestors 'none'"
            )
        if request.url.path.startswith("/v1/"):
            response.headers["Cache-Control"] = "no-store"
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
