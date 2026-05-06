from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import models, projects


def create_app() -> FastAPI:
    app = FastAPI(title="商品详情图生成智能体 API", version="0.1.0")
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

    if models.router is not None:
        app.include_router(models.router)
    if projects.router is not None:
        app.include_router(projects.router)
    return app


app = create_app()
