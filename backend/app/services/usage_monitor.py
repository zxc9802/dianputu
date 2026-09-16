"""OpenLux metadata-only outbox. No prompts, generated content or secrets are stored."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from app.services.app_session import LOCAL_DEV_USER_ID, _source

_user: ContextVar[str | None] = ContextVar("usage_user", default=None)
logger = logging.getLogger(__name__)


@contextmanager
def usage_user(user_id: str | None):
    """Only pass the server-verified SSO identity, never a request body identity."""
    token = _user.set(user_id if user_id and user_id != LOCAL_DEV_USER_ID else None)
    try:
        yield
    finally:
        _user.reset(token)


def current_usage_user() -> str | None:
    return _user.get()


def capture_usage_task(work):
    user_id = current_usage_user()

    async def run(*args, **kwargs):
        with usage_user(user_id):
            return await work(*args, **kwargs)

    return run


def is_openlux(url: str) -> bool:
    try:
        return urlparse(url).hostname == "api.openlux.ai"
    except ValueError:
        return False


def _object(value) -> dict:
    return value if isinstance(value, dict) else {}


def _count(*values) -> int | None:
    return next((v for v in values if type(v) is int and 0 <= v <= 2**53 - 1), None)


def parse_usage(data: Any) -> dict[str, Any]:
    root = _object(data)
    data = _object(root.get("response")) or root
    usage = _object(data.get("usage"))
    gemini = _object(data.get("usageMetadata"))
    details = _object(usage.get("input_tokens_details") or usage.get("prompt_tokens_details"))
    output_details = _object(usage.get("output_tokens_details") or usage.get("completion_tokens_details"))
    inputs = _count(usage.get("input_tokens"), usage.get("prompt_tokens"), gemini.get("promptTokenCount"))
    outputs = _count(usage.get("output_tokens"), usage.get("completion_tokens"))
    thoughts = _count(gemini.get("thoughtsTokenCount"))
    if outputs is None:
        candidates = _count(gemini.get("candidatesTokenCount"))
        outputs = candidates + (thoughts or 0) if candidates is not None else None
    total = _count(usage.get("total_tokens"), gemini.get("totalTokenCount"))
    if total is None and inputs is not None and outputs is not None:
        total = inputs + outputs
    image_counts = [_count(d.get("tokenCount")) for d in gemini.get("promptTokensDetails", []) if isinstance(d, dict) and d.get("modality") == "IMAGE"]
    image_input = _count(details.get("image_tokens"), usage.get("image_input_tokens"))
    if image_input is None and image_counts and all(n is not None for n in image_counts):
        image_input = sum(image_counts)
    return {
        "tokenBasis": "reported" if any(n is not None for n in (inputs, outputs, total)) else "missing",
        "inputTokens": inputs, "outputTokens": outputs, "totalTokens": total,
        "cachedInputTokens": _count(details.get("cached_tokens"), gemini.get("cachedContentTokenCount")),
        "cacheWriteTokens": _count(usage.get("cache_creation_input_tokens")),
        "reasoningTokens": _count(output_details.get("reasoning_tokens"), thoughts),
        "imageInputTokens": image_input,
    }


def _settings():
    env = _source()
    url = env.get("MAIN_APP_URL", "").strip().rstrip("/")
    secret = env.get("USAGE_MONITOR_INTERNAL_SECRET", "").strip()
    if not url or not secret:
        return None
    return {"url": url + "/api/sso/usage", "secret": secret, "dir": Path(env.get("USAGE_MONITOR_OUTBOX_DIR") or Path(__file__).resolve().parents[3] / "data" / "usage-outbox")}


def _persist(event: dict) -> None:
    settings = _settings()
    if settings is None:
        return
    path = settings["dir"] / f"{event['requestId']}-{'0' if event['status'] == 'pending' else '1'}.json"
    temp = path.with_suffix(f".{uuid4()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temp.open("x", encoding="utf-8") as stream:
            temp.chmod(0o600)
            json.dump(event, stream)
        temp.replace(path)
    except OSError:
        logger.error("Could not persist usage metadata; check persistent outbox storage")
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


async def _deliver(event, settings) -> bool:
    import httpx
    async with httpx.AsyncClient(timeout=2, follow_redirects=False) as client:
        response = await client.post(settings["url"], headers={"x-usage-tool": "dianputu", "x-usage-secret": settings["secret"]}, json=event)
        return response.is_success


async def drain_usage_outbox() -> None:
    settings = _settings()
    if settings is None:
        return
    try:
        paths = sorted(settings["dir"].glob("*.json"))[:10]
        for path in paths:
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
                if not await _deliver(event, settings):
                    break
                path.unlink(missing_ok=True)
            except Exception:
                break
    except OSError:
        pass


async def tracked_post(client, url: str, model: str, **kwargs):
    user_id = current_usage_user()
    if not user_id or not is_openlux(url) or not _settings():
        return await client.post(url, **kwargs)
    event = {"userId": user_id, "requestId": str(uuid4()), "provider": "api.openlux.ai", "model": model, "status": "pending", **parse_usage({})}
    _persist(event)
    try:
        response = await client.post(url, **kwargs)
    except (Exception, asyncio.CancelledError) as error:
        _persist({**event, "status": "interrupted" if isinstance(error, asyncio.CancelledError) else "failed"})
        await drain_usage_outbox()
        raise
    try:
        data = _object(response.json())
        status = "completed"
        if response.status_code >= 400 or data.get("error") or data.get("status") in ("failed", "error"):
            status = "failed"
        elif response.status_code == 202 or data.get("status") in ("pending", "queued", "processing", "in_progress"):
            status = "pending"
        event = {**event, **parse_usage(data), "status": status}
        if isinstance(data.get("id"), str):
            event["upstreamRequestId"] = data["id"][:200]
    except (ValueError, TypeError):
        event["status"] = "failed" if response.status_code >= 400 else "interrupted"
    _persist(event)
    await drain_usage_outbox()
    return response


if __name__ == "__main__":
    if _settings() is None:
        raise SystemExit("MAIN_APP_URL and USAGE_MONITOR_INTERNAL_SECRET are required")
    asyncio.run(drain_usage_outbox())
    remaining = len(list(_settings()["dir"].glob("*.json")))
    print(f"Usage retry batch finished; {remaining} events remain.")
