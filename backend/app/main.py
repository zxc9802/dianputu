from __future__ import annotations

from contextlib import asynccontextmanager, suppress
import asyncio

from app.dependencies.auth import require_app_user
from app.services.main_usage import enabled, usage_user, usage_worker

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import history, models, projects, session, styles
from app.services.app_session import AppSessionUnauthorizedError, app_session_error_payload
from app.services.database import close_pool, ensure_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure database tables exist.  Shutdown: close the pool."""
    await ensure_tables()
    reporter = asyncio.create_task(usage_worker())
    try:
        yield
    finally:
        reporter.cancel()
        with suppress(asyncio.CancelledError):
            await reporter
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

    @app.middleware("http")
    async def employee_usage_context(request: Request, call_next):
        if not enabled() or not request.url.path.startswith('/api/projects'):
            return await call_next(request)
        try:
            user = require_app_user(request)
        except AppSessionUnauthorizedError as error:
            return JSONResponse(app_session_error_payload(error), status_code=error.status_code)
        token = usage_user.set(user.user_id)
        try:
            return await call_next(request)
        finally:
            usage_user.reset(token)

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
    if styles.router is not None:
        app.include_router(styles.router)
    if history.router is not None:
        app.include_router(history.router)
    return app


app = create_app()
