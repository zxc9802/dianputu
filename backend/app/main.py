from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import history, models, projects, session
from app.services.app_session import AppSessionUnauthorizedError, app_session_error_payload
from app.services.database import close_pool, ensure_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure database tables exist.  Shutdown: close the pool."""
    await ensure_tables()
    yield
    await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(title="商品详情图生成智能体 API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(AppSessionUnauthorizedError)
    async def app_session_exception_handler(request: Request, exc: AppSessionUnauthorizedError) -> JSONResponse:
        return JSONResponse(app_session_error_payload(exc), status_code=exc.status_code)

    if session.router is not None:
        app.include_router(session.router)
    if models.router is not None:
        app.include_router(models.router)
    if projects.router is not None:
        app.include_router(projects.router)
    if history.router is not None:
        app.include_router(history.router)
    return app


app = create_app()
