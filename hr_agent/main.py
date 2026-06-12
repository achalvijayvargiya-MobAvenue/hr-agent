"""
FastAPI application entry-point.

Routes are registered here; all business logic lives in services/.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Logging must be configured before any other hr_agent import so every
# module-level logger picks up the file + console handlers.
from hr_agent.config import get_settings
from hr_agent.logging_config import setup_logging

_s = get_settings()
setup_logging(log_level=_s.log_level, log_file=_s.log_file)

import hr_agent.models  # noqa: F401, E402 — registers all ORM models with Base.metadata
from hr_agent.api import admin, candidates, jobs, matches  # noqa: E402
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

    @app.get("/health", tags=["system"])
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.include_router(jobs.router)
    app.include_router(candidates.router)
    app.include_router(matches.router)
    app.include_router(admin.router)

    return app


app = create_app()
