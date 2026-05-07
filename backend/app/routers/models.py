from __future__ import annotations

from typing import Any

from app.core.config import get_model_settings


def build_public_model_config() -> dict[str, Any]:
    settings = get_model_settings()
    return {
        "textAnalysis": {
            "baseUrl": settings.text.base_url,
            "endpoint": "/chat/completions",
            "model": settings.text.model,
            "defaults": {
                "max_tokens": settings.text.max_tokens,
                "temperature": settings.text.temperature,
            },
            "configured": bool(settings.text.api_key),
            "fallback": {
                "baseUrl": settings.fallback_text.base_url,
                "endpoint": "/chat/completions",
                "model": settings.fallback_text.model,
                "defaults": {
                    "max_tokens": settings.fallback_text.max_tokens,
                    "temperature": settings.fallback_text.temperature,
                },
                "configured": bool(settings.fallback_text.api_key),
            },
        },
        "imageGeneration": {
            "baseUrl": settings.image.base_url,
            "endpoint": "/images/generations",
            "model": settings.image.model,
            "defaults": {
                "size": settings.image.size,
                "n": settings.image.n,
                "quality": settings.image.quality,
                "output_format": settings.image.output_format,
                "response_format": settings.image.response_format,
            },
            "configured": bool(settings.image.api_key),
            "fallback": {
                "baseUrl": settings.fallback_image.base_url,
                "endpoint": "/images/generations",
                "model": settings.fallback_image.model,
                "defaults": {
                    "size": settings.fallback_image.size,
                    "n": settings.fallback_image.n,
                },
                "configured": bool(settings.fallback_image.api_key),
            },
        },
    }


try:
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/models", tags=["models"])

    @router.get("/config")
    async def get_public_model_config() -> dict[str, Any]:
        return build_public_model_config()

except ModuleNotFoundError:
    router = None
