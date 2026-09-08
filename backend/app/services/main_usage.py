"""Employee usage only; never store prompts, provider keys or wallet credits."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from uuid import uuid4

import httpx

usage_user: ContextVar[str | None] = ContextVar('usage_user', default=None)
logger = logging.getLogger(__name__)
_flush_lock = asyncio.Lock()


def enabled() -> bool:
    return all(os.getenv(key) for key in ('MAIN_APP_URL', 'USAGE_TOOL', 'USAGE_REPORT_SECRET'))


def directory() -> Path:
    return Path(os.getenv('USAGE_OUTBOX_DIR') or str(Path(os.getenv('DATA_DIR') or os.getcwd()) / '.usage-outbox'))


def save(event: dict, suffix: str) -> Path:
    folder = directory()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(f"{os.environ['USAGE_TOOL']}:{event['requestId']}".encode()).hexdigest()
    target = folder / (key + suffix)
    temporary = folder / (key + '.' + str(uuid4()) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump(event, file)
    temporary.replace(target)
    return target


def count(value):
    return value if type(value) is int and 0 <= value <= 1_000_000_000 else None


def token_usage(payload: dict) -> dict:
    usage = payload.get('usage') or {}
    metadata = payload.get('usageMetadata') or {}
    read = count((usage.get('prompt_tokens_details') or usage.get('input_tokens_details') or {}).get('cached_tokens'))
    write = count(usage.get('cache_creation_input_tokens'))
    reasoning = count((usage.get('completion_tokens_details') or usage.get('output_tokens_details') or {}).get('reasoning_tokens'))
    incoming = count(usage.get('prompt_tokens', usage.get('input_tokens')))
    outgoing = count(usage.get('completion_tokens', usage.get('output_tokens')))
    total = count(usage.get('total_tokens'))
    if 'cache_read_input_tokens' in usage or 'cache_creation_input_tokens' in usage:
        read = count(usage.get('cache_read_input_tokens'))
        if incoming is not None:
            incoming += (read or 0) + (write or 0)
    if metadata:
        incoming = count(metadata.get('promptTokenCount'))
        outgoing = count(metadata.get('candidatesTokenCount'))
        read = count(metadata.get('cachedContentTokenCount'))
        reasoning = count(metadata.get('thoughtsTokenCount'))
        total = count(metadata.get('totalTokenCount'))
        if outgoing is not None:
            outgoing += reasoning or 0
    if incoming is not None and outgoing is not None:
        total = incoming + outgoing
    return dict(inputTokens=incoming, outputTokens=outgoing, totalTokens=total,
                cachedInputTokens=read, cacheWriteTokens=write, reasoningTokens=reasoning,
                tokenBasis='reported' if any(v is not None for v in (incoming, outgoing, total)) else 'missing')


async def metered_post(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    if not enabled():
        return await client.post(url, **kwargs)
    user_id = usage_user.get()
    if not user_id:
        raise RuntimeError('Usage reporting requires an authenticated employee')
    body = kwargs.get('json') or kwargs.get('data') or {}
    event = dict(userId=user_id, requestId=str(uuid4()), provider=httpx.URL(url).host,
                 model=str(body.get('model') or 'unknown'), status='interrupted', **token_usage({}))
    pending = await asyncio.to_thread(save, event, '.pending')
    try:
        response = await client.post(url, **kwargs)
    except BaseException as error:
        event['status'] = 'interrupted' if isinstance(error, asyncio.CancelledError) else 'failed'
        await finish(event, pending)
        raise
    event['upstreamRequestId'] = response.headers.get('x-request-id')
    event['status'] = 'completed' if response.is_success else 'failed'
    try:
        payload = response.json()
        if isinstance(payload, dict):
            event.update(token_usage(payload))
            if payload.get('error'):
                event['status'] = 'failed'
    except ValueError:
        pass
    await finish(event, pending)
    return response


async def finish(event: dict, pending: Path):
    try:
        await asyncio.to_thread(save, event, '.json')
        pending.unlink(missing_ok=True)
    except OSError:
        logger.error('Cannot save final usage; pending request retained for reconciliation')


async def flush_usage():
    if not enabled() or _flush_lock.locked():
        return
    async with _flush_lock:
        folder = directory()
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        for pending in list(folder.glob('*.pending'))[:50]:
            if time.time() - pending.stat().st_mtime < 86400:
                continue
            target = pending.with_suffix('.json')
            if not target.exists():
                save(json.loads(pending.read_text()), '.json')
            pending.unlink(missing_ok=True)
        async with httpx.AsyncClient(timeout=5) as client:
            for file in list(folder.glob('*.json'))[:50]:
                body = file.read_text()
                response = await client.post(os.environ['MAIN_APP_URL'].rstrip('/') + '/api/sso/usage',
                    headers={'content-type': 'application/json', 'x-usage-tool': os.environ['USAGE_TOOL'],
                             'x-usage-secret': os.environ['USAGE_REPORT_SECRET']}, content=body)
                if not response.is_success or response.json().get('success') is not True:
                    raise RuntimeError(f'Usage report HTTP {response.status_code}')
                if file.exists() and file.read_text() == body:
                    file.unlink(missing_ok=True)


async def usage_worker():
    while True:
        try:
            await flush_usage()
        except Exception:
            logger.warning('Usage reports retained for retry')
        await asyncio.sleep(30)
