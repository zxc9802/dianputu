from __future__ import annotations

import re
from typing import Any

from app.core.config import ImageGenerationSettings


MODEL_GATEWAY_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
DATA_IMAGE_RE = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=_-]+")


def build_image_generation_payload(
    *,
    prompt: str,
    model: str,
    size: str,
    n: int,
    quality: str = "",
    output_format: str = "",
    response_format: str = "",
    image: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "size": size,
        "n": n,
        "prompt": prompt,
    }
    if quality:
        payload["quality"] = quality
    if output_format:
        payload["output_format"] = output_format
    if response_format:
        payload["response_format"] = response_format
    if image:
        payload["image"] = image
    return payload


def extract_image_urls_from_response(data: dict[str, Any], *, image_format: str = "png") -> list[str]:
    urls: list[str] = []
    for item in data.get("data", []):
        if item.get("url"):
            urls.append(item["url"])
        elif item.get("b64_json"):
            urls.append(f"data:image/{image_format};base64,{item['b64_json']}")

    for choice in data.get("choices", []):
        content = choice.get("message", {}).get("content", "")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("image_url", {}).get("url") or ""))
            content = "\n".join(parts)
        if isinstance(content, str):
            urls.extend(DATA_IMAGE_RE.findall(content))

    return urls


async def call_image_model(
    settings: ImageGenerationSettings,
    prompt: str,
    image: list[str] | None = None,
    size: str | None = None,
) -> list[str]:
    if not settings.api_key:
        return []

    import httpx

    payload = build_image_generation_payload(
        prompt=prompt,
        model=settings.model,
        size=size or settings.size,
        n=settings.n,
        quality=settings.quality,
        output_format=settings.output_format,
        response_format=settings.response_format,
        image=image,
    )
    async with httpx.AsyncClient(timeout=480) as client:
        response = await client.post(
            settings.endpoint_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
                "User-Agent": MODEL_GATEWAY_USER_AGENT,
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return extract_image_urls_from_response(data, image_format=settings.output_format or "png")


def _detect_image_format(image_bytes: bytes) -> str:
    """Detect image format from file magic bytes."""
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if image_bytes[:2] == b"\xff\xd8":
        return "jpeg"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    return "png"


async def call_image_edit_model(
    settings: ImageGenerationSettings,
    prompt: str,
    image_bytes: bytes,
    size: str | None = None,
) -> list[str]:
    """Call the /images/edits endpoint using multipart form-data.

    This is a true edit endpoint: the model receives the original image as a
    file upload and applies targeted modifications, preserving areas the user
    did not ask to change.
    """
    if not settings.api_key:
        return []

    import httpx

    edit_url = settings.base_url.rstrip("/") + "/images/edits"
    img_format = _detect_image_format(image_bytes)
    mime = f"image/{img_format}"

    files = {"image": (f"source.{img_format}", image_bytes, mime)}
    data: dict[str, str] = {
        "model": settings.model,
        "prompt": prompt,
        "size": size or settings.size,
    }
    if settings.quality:
        data["quality"] = settings.quality
    if settings.output_format:
        data["output_format"] = settings.output_format
    if settings.response_format:
        data["response_format"] = settings.response_format

    async with httpx.AsyncClient(timeout=480) as client:
        response = await client.post(
            edit_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {settings.api_key}",
                "User-Agent": MODEL_GATEWAY_USER_AGENT,
            },
            files=files,
            data=data,
        )
        response.raise_for_status()
        result = response.json()
        return extract_image_urls_from_response(result, image_format=settings.output_format or "png")
