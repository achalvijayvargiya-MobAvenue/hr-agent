"""
FastAPI application entry-point.

Routes are registered here; all business logic lives in services/.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Logging must be configured before any other hr_agent import so every
# module-level logger picks up the file + console handlers.
from hr_agent.config import get_settings
from hr_agent.logging_config import setup_logging

_s = get_settings()
setup_logging(log_level=_s.log_level, log_file=_s.log_file, backup_count=_s.log_backup_days)

import hr_agent.models  # noqa: F401, E402 — registers all ORM models with Base.metadata
from hr_agent.api import admin, auth, candidates, jobs, matches, sources, users  # noqa: E402
from hr_agent.core.errors import HRAgentError  # noqa: E402
from hr_agent.database import init_db  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info(
        "HR Agent started — log_level=%s  log_file=%s  db=%s",
        _s.log_level, _s.log_file, _s.database_url,
    )
    yield
    logger.info("HR Agent shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="HR Agent API",
        description=(
            "Match candidate CVs to job descriptions using LLM extraction, "
            "vector embeddings, and rule-based scoring."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_s.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────

    _HTTP_STATUS_TO_ERROR_CODE: dict[int, str] = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
    }

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        error_code = _HTTP_STATUS_TO_ERROR_CODE.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error_code,
                "message": message,
                "status_code": exc.status_code,
                "path": str(request.url.path),
            },
            headers=dict(exc.headers) if exc.headers else None,
        )

    @app.exception_handler(HRAgentError)
    async def hr_agent_error_handler(request: Request, exc: HRAgentError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "status_code": exc.status_code,
                "path": str(request.url.path),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": str(exc),
                "status_code": 422,
                "path": str(request.url.path),
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "status_code": 500,
                "path": str(request.url.path),
            },
        )

    @app.get("/health", tags=["system"])
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/api/v1/health", tags=["system"])
    def health_v1() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(candidates.router, prefix="/api/v1")
    app.include_router(matches.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(users.roles_router, prefix="/api/v1")
    app.include_router(sources.router, prefix="/api/v1")

    return app


app = create_app()
