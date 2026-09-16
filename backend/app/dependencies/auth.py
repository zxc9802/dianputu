from __future__ import annotations

from dataclasses import asdict

from fastapi import Depends, Request

from app.services.usage_monitor import drain_usage_outbox, usage_user

from app.services.app_session import (
    AppSession,
    AppSessionUnauthorizedError,
    AppSessionUserSnapshot,
    assert_app_session_from_cookie_header,
    get_app_session_user_snapshot,
)


def require_app_session(request: Request) -> AppSession:
    return assert_app_session_from_cookie_header(
        request.headers.get("cookie", ""),
        str(request.url),
    )


def require_app_user(request: Request) -> AppSessionUserSnapshot:
    session = require_app_session(request)
    user = get_app_session_user_snapshot(session)
    if user is not None:
        return user

    raise AppSessionUnauthorizedError(
        redirect_url=session.main_app_url,
        message="主站会话缺少有效的用户信息，请重新从官网进入图片生成工具。",
    )


def user_snapshot_dict(user: AppSessionUserSnapshot) -> dict[str, str]:
    return {key: value for key, value in asdict(user).items() if value}


async def require_usage_context(user: AppSessionUserSnapshot = Depends(require_app_user)):
    # Async dependency keeps ContextVar state in the request task, not the sync dependency threadpool.
    with usage_user(user.user_id):
        await drain_usage_outbox()
        yield user
