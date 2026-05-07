from __future__ import annotations

from typing import Any

from app.core.config import ImageGenerationSettings


MODEL_GATEWAY_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


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
        urls: list[str] = []
        for item in data.get("data", []):
            if item.get("url"):
                urls.append(item["url"])
            elif item.get("b64_json"):
                image_format = settings.output_format or "png"
                urls.append(f"data:image/{image_format};base64,{item['b64_json']}")
        return urls
