from __future__ import annotations

from typing import Any

from app.core.config import get_model_settings


def _image_setting_configured(option) -> bool:
    return bool(option.api_key or any(alternate.api_key for alternate in option.retry_alternates))


def build_public_model_config() -> dict[str, Any]:
    settings = get_model_settings()
    default_image = settings.image_options.get(settings.default_image_option_id, settings.image)
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
            "configured": _image_setting_configured(option),
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
            "baseUrl": default_image.base_url,
            "endpoint": default_image.endpoint_path,
            "model": default_image.model,
            "defaults": {
                "size": default_image.size,
                "n": default_image.n,
                "quality": default_image.quality,
                "output_format": default_image.output_format,
                "response_format": default_image.response_format,
            },
            "configured": _image_setting_configured(default_image),
            "defaultOptionId": settings.default_image_option_id,
            "options": image_options,
            "fallback": {
                "label": settings.fallback_image.label,
                "baseUrl": settings.fallback_image.base_url,
                "endpoint": settings.fallback_image.endpoint_path,
                "model": settings.fallback_image.model,
                "defaults": {
                    "size": settings.fallback_image.size,
                    "n": settings.fallback_image.n,
                },
                "configured": _image_setting_configured(settings.fallback_image),
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
