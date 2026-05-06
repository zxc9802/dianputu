from __future__ import annotations

from typing import Any

from app.core.config import TextAnalysisSettings


Message = dict[str, Any]
MODEL_GATEWAY_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def build_chat_completion_payload(
    *,
    messages: list[Message],
    model: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


async def call_text_model(settings: TextAnalysisSettings, messages: list[Message]) -> str:
    if not settings.api_key:
        return ""

    import httpx

    payload = build_chat_completion_payload(
        messages=messages,
        model=settings.model,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )
    async with httpx.AsyncClient(timeout=120) as client:
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
        return data["choices"][0]["message"].get("content", "")
