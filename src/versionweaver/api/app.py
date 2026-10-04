import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from versionweaver import __version__
from versionweaver.api.dependencies import require_admin_token
from versionweaver.api.routes import admin_router, control_router, public_router, runner_router
from versionweaver.api.web import mount_web_ui
from versionweaver.config import get_settings
from versionweaver.logging import configure_logging
from versionweaver.observability.metrics import metrics_response, record_request
from versionweaver.persistence.database import init_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    settings = get_settings()
    settings.validate_for_startup()
    configure_logging(settings.log_level)
    init_database()
    yield


app = FastAPI(
    title="VersionWeaver API",
    version=__version__,
    description="Dependency and AI model migration control plane",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(GZipMiddleware, minimum_size=1000)
cors_origins = settings.parsed_cors_origins()
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Next-Cursor", "X-Request-ID"],
    )
app.include_router(public_router)
app.include_router(runner_router)
app.include_router(control_router)
app.include_router(admin_router)


@app.get("/metrics", include_in_schema=False, dependencies=[Depends(require_admin_token)])
def metrics() -> Response:
    return metrics_response()


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logging.getLogger(__name__).exception(
            "unhandled request error", extra={"request_id": request_id}
        )
        response = JSONResponse(status_code=500, content={"detail": "internal server error"})
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    route_object = request.scope.get("route")
    route = getattr(route_object, "path", "unmatched")
    record_request(request.method, route, response.status_code, time.monotonic() - started)
    return response


mount_web_ui(app, settings.web_dist_dir)
