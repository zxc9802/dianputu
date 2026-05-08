from __future__ import annotations

from typing import Any

from app.core.config import get_model_settings


def build_public_model_config() -> dict[str, Any]:
    settings = get_model_settings()
    image_options = [
        {
            "id": option.id,
            "label": option.label,
            "baseUrl": option.base_url,
            "endpoint": option.endpoint_path,
            "model": option.model,
            "defaults": {
                "size": option.size,
                "n": option.n,
                "quality": option.quality,
                "output_format": option.output_format,
                "response_format": option.response_format,
            },
            "configured": bool(option.api_key),
        }
        for option in settings.image_options.values()
    ]
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
        },
        "imageGeneration": {
            "baseUrl": settings.image.base_url,
            "endpoint": settings.image.endpoint_path,
            "model": settings.image.model,
            "defaults": {
                "size": settings.image.size,
                "n": settings.image.n,
                "quality": settings.image.quality,
                "output_format": settings.image.output_format,
                "response_format": settings.image.response_format,
            },
            "configured": bool(settings.image.api_key),
            "defaultOptionId": settings.image.id,
            "options": image_options,
            "fallback": {
                "baseUrl": settings.fallback_image.base_url,
                "endpoint": settings.fallback_image.endpoint_path,
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
    from fastapi import APIRouter, Depends

    from app.dependencies.auth import require_app_user

    router = APIRouter(prefix="/api/models", tags=["models"], dependencies=[Depends(require_app_user)])

    @router.get("/config")
    async def get_public_model_config() -> dict[str, Any]:
        return build_public_model_config()

except ModuleNotFoundError:
    router = None
