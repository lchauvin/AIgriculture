"""FastAPI application factory.

Instantiate with ``create_app()`` so tests get fresh state per fixture
and the dev/prod uvicorn entrypoints share the same factory.

Run locally::

    .venv/bin/uvicorn aigriculture.api.app:app --reload --port 8008
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from .jobs import JobStore
from .routes import envelope as envelope_routes
from .routes import health as health_routes
from .routes import jobs as job_routes


def create_app() -> FastAPI:
    app = FastAPI(
        title="AIgriculture API",
        version=__version__,
        description=(
            "Climate-adaptive crop recommendation backend. Tier 1 "
            "envelope screening exposed via async job + polling — see "
            "/docs for the OpenAPI schema."
        ),
    )

    # Process-local job store. Initialized at app construction time
    # (not via lifespan) so TestClient sees it without context-managing
    # the client. Replace with a Redis-backed store when we deploy.
    app.state.job_store = JobStore()

    # Permissive CORS for local development. Lock down before any
    # public deployment. Frontend dev server runs at :3232 (see
    # frontend/package.json scripts).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3232", "http://127.0.0.1:3232"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(health_routes.router)
    app.include_router(envelope_routes.router)
    app.include_router(job_routes.router)

    return app


# Module-level instance for ``uvicorn aigriculture.api.app:app``.
app = create_app()
