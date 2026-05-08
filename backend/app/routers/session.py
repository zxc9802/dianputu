from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.app_session import (
    AppSessionUnauthorizedError,
    app_session_error_payload,
    assert_app_session_from_cookie_header,
    build_public_session_data,
    is_main_app_sso_required,
)

router = APIRouter(prefix="/api", tags=["session"])


@router.get("/session")
async def get_app_session(request: Request) -> JSONResponse:
    try:
        session = assert_app_session_from_cookie_header(
            request.headers.get("cookie", ""),
            str(request.url),
        )
    except AppSessionUnauthorizedError as error:
        return JSONResponse(app_session_error_payload(error), status_code=error.status_code)

    return JSONResponse(
        {
            "success": True,
            "data": {
                "requiresSso": is_main_app_sso_required(),
                "session": build_public_session_data(session),
            },
        }
    )
