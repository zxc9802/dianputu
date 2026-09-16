from __future__ import annotations

from dataclasses import asdict

from fastapi import Request

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
