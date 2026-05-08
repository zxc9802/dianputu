from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlparse


DEFAULT_MAIN_APP_ENTRY_PATH = "/bot/detail-image-agent"
DEFAULT_SESSION_COOKIE_NAME = "detail_image_agent_session"
DEFAULT_SESSION_TTL_MINUTES = 720
DEFAULT_UNAUTHORIZED_MESSAGE = "请先从主官网登录后再进入图片生成工具。"
LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "0.0.0.0"}
LOCAL_DEV_USER_ID = "detail-image-agent-local-dev-user"


@dataclass(frozen=True)
class AppSession:
    token: str
    user: dict[str, Any]
    main_app_url: str
    expires_at: int


@dataclass(frozen=True)
class AppSessionUserSnapshot:
    user_id: str
    account: str = ""
    nickname: str = ""
    role: str = ""
    group_name: str = ""


class AppSessionUnauthorizedError(Exception):
    def __init__(self, redirect_url: str, message: str = DEFAULT_UNAUTHORIZED_MESSAGE, status_code: int = 401) -> None:
        super().__init__(message)
        self.redirect_url = redirect_url
        self.message = message
        self.status_code = status_code


def _project_env_path() -> Path:
    return Path(__file__).resolve().parents[3] / ".env"


def _read_env_file(path: Path | str | None) -> dict[str, str]:
    if path is None:
        return {}

    env_path = Path(path)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _source(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> dict[str, str]:
    source = _read_env_file(_project_env_path() if env is None and env_file is None else env_file)
    source.update({key: value for key, value in (environ if env is None else env).items() if value not in (None, "")})
    return source


def _read(source: Mapping[str, str], key: str, default: str = "") -> str:
    value = source.get(key)
    return value if value not in (None, "") else default


def _read_bool(value: str | None, fallback: bool) -> bool:
    if not value:
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _strip_trailing_slash(value: str) -> str:
    return value.strip().rstrip("/")


def _normalize_path(value: str | None, fallback: str) -> str:
    candidate = (value or "").strip()
    if not candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return fallback
    return candidate


def _is_production(source: Mapping[str, str]) -> bool:
    return _read(source, "NODE_ENV") == "production" or _read(source, "ENVIRONMENT") == "production"


def is_main_app_sso_required(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> bool:
    source = _source(env, env_file)
    return _read_bool(source.get("REQUIRE_MAIN_APP_SSO"), _is_production(source))


def get_session_cookie_name(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> str:
    source = _source(env, env_file)
    return _read(source, "DETAIL_IMAGE_AGENT_SESSION_COOKIE_NAME", DEFAULT_SESSION_COOKIE_NAME)


def get_session_secret(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> str:
    source = _source(env, env_file)
    secret = _read(source, "DETAIL_IMAGE_AGENT_SESSION_SECRET") or _read(source, "DETAIL_IMAGE_AGENT_SSO_SECRET")
    if secret:
        return secret
    if not _is_production(source):
        return "detail-image-agent-dev-session-secret"
    raise RuntimeError("DETAIL_IMAGE_AGENT_SESSION_SECRET is required when SSO is enabled in production.")


def get_session_ttl_ms(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> int:
    source = _source(env, env_file)
    try:
        minutes = int(_read(source, "DETAIL_IMAGE_AGENT_SESSION_TTL_MINUTES", str(DEFAULT_SESSION_TTL_MINUTES)))
    except ValueError:
        minutes = DEFAULT_SESSION_TTL_MINUTES
    return max(5, minutes) * 60 * 1000


def get_main_app_entry_path(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> str:
    source = _source(env, env_file)
    return _normalize_path(
        _read(source, "MAIN_APP_DETAIL_IMAGE_AGENT_ENTRY_PATH") or _read(source, "MAIN_APP_BOT_ENTRY_PATH"),
        DEFAULT_MAIN_APP_ENTRY_PATH,
    )


def get_configured_main_app_url(env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> str:
    source = _source(env, env_file)
    main_app_url = _strip_trailing_slash(_read(source, "MAIN_APP_URL"))
    if main_app_url:
        return main_app_url
    if is_main_app_sso_required(source):
        raise RuntimeError("MAIN_APP_URL is required when main-site SSO is enabled.")
    return ""


def build_main_app_entry_url(base_url: str | None = None, env: Mapping[str, str] | None = None, env_file: Path | str | None = None) -> str:
    source = _source(env, env_file)
    resolved_base_url = _strip_trailing_slash(base_url or get_configured_main_app_url(source))
    if not resolved_base_url:
        raise RuntimeError("MAIN_APP_URL is required to build the main-site entry URL.")
    return f"{resolved_base_url}{get_main_app_entry_path(source)}"


def _sanitize_main_app_url(value: str | None, env: Mapping[str, str] | None = None) -> str | None:
    candidate = (value or "").strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    source = _source(env)
    configured = get_configured_main_app_url(source)
    if configured:
        configured_url = urlparse(configured)
        if (parsed.scheme, parsed.netloc) == (configured_url.scheme, configured_url.netloc):
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    if not _is_production(source) and parsed.hostname in LOCAL_HOSTNAMES:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    return None


def resolve_requested_main_app_url(request_url: str, env: Mapping[str, str] | None = None) -> str:
    parsed = urlparse(request_url)
    query = parse_qs(parsed.query)
    requested = query.get("mainApp", [None])[0]
    return _sanitize_main_app_url(requested, env) or get_configured_main_app_url(env)


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign_payload(payload: str, env: Mapping[str, str] | None = None) -> str:
    digest = hmac.new(
        get_session_secret(env).encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(digest)


def build_session_cookie_value(
    *,
    token: str,
    user: Mapping[str, Any],
    main_app_url: str,
    expires_at_ms: int | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    expires_at = expires_at_ms if expires_at_ms is not None else int(time.time() * 1000) + get_session_ttl_ms(env)
    payload = _base64url_encode(
        json.dumps(
            {
                "token": token,
                "user": dict(user),
                "mainAppUrl": main_app_url,
                "expiresAt": expires_at,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return f"{payload}.{_sign_payload(payload, env)}"


def _parse_cookie_header(cookie_header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for item in cookie_header.split(";"):
        part = item.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = unquote(value.strip())
    return cookies


def read_app_session_from_cookie_header(
    cookie_header: str,
    env: Mapping[str, str] | None = None,
) -> AppSession | None:
    raw_value = _parse_cookie_header(cookie_header).get(get_session_cookie_name(env))
    if not raw_value:
        return None

    payload, separator, signature = raw_value.partition(".")
    if not payload or not separator or not signature:
        return None

    expected = _sign_payload(payload, env)
    if not hmac.compare_digest(expected.encode("utf-8"), signature.encode("utf-8")):
        return None

    try:
        parsed = json.loads(_base64url_decode(payload).decode("utf-8"))
    except (json.JSONDecodeError, ValueError):
        return None

    user = parsed.get("user")
    token = parsed.get("token")
    expires_at = parsed.get("expiresAt")
    main_app_url = parsed.get("mainAppUrl")
    if not isinstance(user, dict) or not isinstance(token, str) or not isinstance(expires_at, int):
        return None
    if not isinstance(main_app_url, str):
        return None
    if expires_at <= int(time.time() * 1000):
        return None

    return AppSession(token=token, user=user, main_app_url=main_app_url, expires_at=expires_at)


def build_local_dev_session(env: Mapping[str, str] | None = None) -> AppSession:
    return AppSession(
        token="detail-image-agent-local-dev-token",
        user={
            "id": LOCAL_DEV_USER_ID,
            "account": "local-admin@localhost",
            "nickname": "本地调试管理员",
            "role": "admin",
        },
        main_app_url=get_configured_main_app_url(env) or "http://localhost:3000",
        expires_at=int(time.time() * 1000) + get_session_ttl_ms(env),
    )


def assert_app_session_from_cookie_header(
    cookie_header: str,
    request_url: str,
    env: Mapping[str, str] | None = None,
) -> AppSession:
    if not is_main_app_sso_required(env):
        return read_app_session_from_cookie_header(cookie_header, env) or build_local_dev_session(env)

    session = read_app_session_from_cookie_header(cookie_header, env)
    if session is not None:
        return session

    raise AppSessionUnauthorizedError(build_main_app_entry_url(resolve_requested_main_app_url(request_url, env), env=env))


def get_app_session_user_snapshot(session: AppSession) -> AppSessionUserSnapshot | None:
    user_id = session.user.get("id")
    if not isinstance(user_id, str) or not user_id.strip():
        return None

    account = session.user.get("account") if isinstance(session.user.get("account"), str) else session.user.get("email")
    return AppSessionUserSnapshot(
        user_id=user_id.strip(),
        account=account.strip() if isinstance(account, str) else "",
        nickname=session.user.get("nickname", "").strip() if isinstance(session.user.get("nickname"), str) else "",
        role=session.user.get("role", "").strip() if isinstance(session.user.get("role"), str) else "",
        group_name=session.user.get("groupName", "").strip() if isinstance(session.user.get("groupName"), str) else "",
    )


def build_public_session_data(session: AppSession) -> dict[str, Any]:
    return {
        "user": session.user,
        "mainAppUrl": session.main_app_url,
        "expiresAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(session.expires_at / 1000)),
    }


def app_session_error_payload(error: AppSessionUnauthorizedError) -> dict[str, Any]:
    return {
        "success": False,
        "message": error.message,
        "redirectUrl": error.redirect_url,
    }
