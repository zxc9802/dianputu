"""Account saved style API router."""

from __future__ import annotations

from typing import Any

try:
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel, Field

    from app.dependencies.auth import require_app_user, user_snapshot_dict
    from app.services.app_session import AppSessionUserSnapshot
    from app.services.database import delete_saved_style, list_saved_styles, save_style

    router = APIRouter(prefix="/api/styles", tags=["styles"])

    class SaveStyleRequest(BaseModel):
        id: str | None = None
        name: str = ""
        style: dict[str, Any] = Field(default_factory=dict)

    @router.get("/saved")
    async def list_account_saved_styles(
        limit: int = 50,
        offset: int = 0,
        current_user: AppSessionUserSnapshot = Depends(require_app_user),
    ) -> dict[str, Any]:
        """Return saved Gemini style records for the current account."""
        clamped_limit = max(1, min(limit, 100))
        clamped_offset = max(0, offset)
        items = await list_saved_styles(current_user.user_id, clamped_limit, clamped_offset)
        return {"items": items, "limit": clamped_limit, "offset": clamped_offset}

    @router.post("/saved")
    async def save_account_style(
        request: SaveStyleRequest,
        current_user: AppSessionUserSnapshot = Depends(require_app_user),
    ) -> dict[str, Any]:
        """Save or update a Gemini style for the current account."""
        result = await save_style(current_user.user_id, user_snapshot_dict(current_user), request.model_dump())
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @router.delete("/saved/{style_id}")
    async def delete_account_saved_style(
        style_id: str,
        current_user: AppSessionUserSnapshot = Depends(require_app_user),
    ) -> dict[str, Any]:
        """Delete one saved style from the current account."""
        deleted = await delete_saved_style(current_user.user_id, style_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="saved style not found or database not configured")
        return {"deleted": True, "id": style_id}

except ModuleNotFoundError:
    router = None
