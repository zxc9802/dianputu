"""History API router for project generation history.

Provides CRUD endpoints for saving, listing, retrieving, and deleting
project history records stored in PostgreSQL.
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel, Field

    from app.dependencies.auth import require_app_user, user_snapshot_dict
    from app.services.app_session import AppSessionUserSnapshot
    from app.services.database import delete_history, get_history, list_history, save_history

    router = APIRouter(prefix="/api/history", tags=["history"])

    class SaveHistoryRequest(BaseModel):
        id: str | None = None
        product_name: str = ""
        category: str = ""
        style_id: str = ""
        style_name: str = ""
        platform_id: str = "tmall"
        thumbnail: str = ""
        image_count: int = 0
        state: dict[str, Any] = Field(default_factory=dict)

    @router.get("")
    async def list_project_history(
        limit: int = 30,
        offset: int = 0,
        current_user: AppSessionUserSnapshot = Depends(require_app_user),
    ) -> dict[str, Any]:
        """Return recent history entries (metadata only, no full project state)."""
        clamped_limit = max(1, min(limit, 100))
        clamped_offset = max(0, offset)
        items = await list_history(current_user.user_id, clamped_limit, clamped_offset)
        return {"items": items, "limit": clamped_limit, "offset": clamped_offset}

    @router.get("/{record_id}")
    async def get_project_history(
        record_id: str,
        current_user: AppSessionUserSnapshot = Depends(require_app_user),
    ) -> dict[str, Any]:
        """Return a single history entry including the full project state."""
        record = await get_history(current_user.user_id, record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="history record not found")
        return record

    @router.post("")
    async def save_project_history(
        request: SaveHistoryRequest,
        current_user: AppSessionUserSnapshot = Depends(require_app_user),
    ) -> dict[str, Any]:
        """Save or update a project history record."""
        result = await save_history(current_user.user_id, user_snapshot_dict(current_user), request.model_dump())
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @router.delete("/{record_id}")
    async def delete_project_history(
        record_id: str,
        current_user: AppSessionUserSnapshot = Depends(require_app_user),
    ) -> dict[str, Any]:
        """Delete a project history record."""
        deleted = await delete_history(current_user.user_id, record_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="history record not found or database not configured")
        return {"deleted": True, "id": record_id}

except ModuleNotFoundError:
    router = None
