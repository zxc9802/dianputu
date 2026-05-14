# Account Saved Styles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an account-scoped saved style library so users can save, reuse, and delete Gemini-generated style structures.

**Architecture:** Store saved styles in PostgreSQL with the same SSO `user_id` isolation as project history. Expose a focused `/api/styles/saved` router, then let the existing style page load, save, select, and delete records while generation continues to use `customStyle`.

**Tech Stack:** FastAPI, asyncpg, Pydantic, Next.js React client components, TypeScript, local static Node tests, Python unittest.

---

### Task 1: Backend Saved Style Persistence

**Files:**
- Modify: `backend/app/services/database.py`
- Modify: `backend/tests/test_history_isolation.py`

- [ ] **Step 1: Write the failing database isolation tests**

Add tests to `backend/tests/test_history_isolation.py`:

```python
    async def test_list_saved_styles_filters_by_user_id(self):
        await database.list_saved_styles("user-a", 20, 5)

        method, sql, args = self.conn.calls[-1]
        self.assertEqual(method, "fetch")
        self.assertIn("FROM saved_styles", sql)
        self.assertIn("WHERE user_id = $1", sql)
        self.assertEqual(args, ("user-a", 20, 5))

    async def test_save_style_writes_owner_fields(self):
        await database.save_style(
            "user-a",
            {"user_id": "user-a", "account": "a@example.test"},
            {
                "id": "style-1",
                "name": "冷萃晶透风",
                "style": {"id": "style_reference", "name": "冷萃晶透风", "keywords": ["冷感"], "primary_color": "#A8DDE8"},
            },
        )

        method, sql, args = self.conn.calls[-1]
        self.assertEqual(method, "execute")
        self.assertIn("INSERT INTO saved_styles", sql)
        self.assertIn("user_id", sql)
        self.assertIn("user_snapshot_json", sql)
        self.assertIn("WHERE saved_styles.user_id = EXCLUDED.user_id", sql)
        self.assertEqual(args[1], "user-a")
        self.assertIn('"user_id": "user-a"', args[2])
        self.assertEqual(args[3], "冷萃晶透风")
        self.assertIn('"primary_color": "#A8DDE8"', args[4])

    async def test_delete_saved_style_filters_by_user_id_and_record_id(self):
        deleted = await database.delete_saved_style("user-a", "style-1")

        method, sql, args = self.conn.calls[-1]
        self.assertTrue(deleted)
        self.assertEqual(method, "execute")
        self.assertIn("DELETE FROM saved_styles WHERE user_id = $1 AND id = $2", sql)
        self.assertEqual(args, ("user-a", "style-1"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest backend/tests/test_history_isolation.py -q
```

Expected: FAIL because `database.list_saved_styles`, `database.save_style`, and `database.delete_saved_style` do not exist.

- [ ] **Step 3: Add minimal database implementation**

In `backend/app/services/database.py`, add the table SQL, index SQL, ensure call, and helpers:

```python
_CREATE_SAVED_STYLES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS saved_styles (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    user_snapshot_json TEXT NOT NULL DEFAULT '{}',
    name         TEXT NOT NULL DEFAULT '',
    style_json   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

_CREATE_SAVED_STYLES_USER_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_saved_styles_user_created ON saved_styles (user_id, created_at DESC);
"""
```

Add to `ensure_tables()`:

```python
        await conn.execute(_CREATE_SAVED_STYLES_TABLE_SQL)
        await conn.execute(_CREATE_SAVED_STYLES_USER_INDEX_SQL)
```

Add helper functions:

```python
async def list_saved_styles(user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    pool = await _get_pool()
    if pool is None:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, style_json, created_at, updated_at
            FROM saved_styles
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
    return [_saved_style_row_to_dict(row) for row in rows]

async def save_style(user_id: str, user_snapshot: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    pool = await _get_pool()
    if pool is None:
        return {"error": "database not configured"}
    record_id = record.get("id") or uuid4().hex
    now = datetime.now(UTC)
    name = str(record.get("name") or "").strip()
    style = dict(record.get("style") or {})
    if name:
        style["name"] = name
    else:
        name = str(style.get("name") or "未命名风格").strip() or "未命名风格"
        style["name"] = name
    style_json = json.dumps(style, ensure_ascii=False, default=str)
    user_snapshot_json = json.dumps(user_snapshot or {}, ensure_ascii=False, default=str)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO saved_styles
                (id, user_id, user_snapshot_json, name, style_json, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                user_snapshot_json = EXCLUDED.user_snapshot_json,
                name = EXCLUDED.name,
                style_json = EXCLUDED.style_json,
                updated_at = EXCLUDED.updated_at
            WHERE saved_styles.user_id = EXCLUDED.user_id
            """,
            record_id,
            user_id,
            user_snapshot_json,
            name,
            style_json,
            now,
            now,
        )
    return {"id": record_id, "name": name, "style": style, "created_at": now.isoformat(), "updated_at": now.isoformat()}

async def delete_saved_style(user_id: str, style_id: str) -> bool:
    pool = await _get_pool()
    if pool is None:
        return False
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM saved_styles WHERE user_id = $1 AND id = $2",
            user_id,
            style_id,
        )
    return result == "DELETE 1"
```

- [ ] **Step 4: Run backend isolation tests**

Run:

```powershell
python -m pytest backend/tests/test_history_isolation.py -q
```

Expected: PASS.

### Task 2: Backend Saved Style Router

**Files:**
- Create: `backend/app/routers/styles.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api_contracts.py`

- [ ] **Step 1: Write failing API contract tests**

Add a `SavedStylesContractTests` class to `backend/tests/test_api_contracts.py`:

```python
class SavedStylesContractTests(unittest.TestCase):
    def make_client(self) -> TestClient:
        from app.routers.styles import router as styles_router

        app = FastAPI()
        app.dependency_overrides[require_app_user] = lambda: AppSessionUserSnapshot(user_id="test-user")
        app.include_router(styles_router)
        return TestClient(app)

    def test_save_style_endpoint_uses_current_user(self):
        with patch("app.routers.styles.save_style", new=AsyncMock(return_value={
            "id": "style-1",
            "name": "冷萃晶透风",
            "style": {"id": "style_reference", "name": "冷萃晶透风", "keywords": ["冷感"], "primary_color": "#A8DDE8"},
            "created_at": "2026-05-14T00:00:00+00:00",
            "updated_at": "2026-05-14T00:00:00+00:00",
        })) as save_mock:
            response = self.make_client().post(
                "/api/styles/saved",
                json={"name": "冷萃晶透风", "style": {"id": "style_reference", "name": "旧名", "keywords": ["冷感"], "primary_color": "#A8DDE8"}},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["style"]["name"], "冷萃晶透风")
        self.assertEqual(save_mock.call_args.args[0], "test-user")

    def test_list_style_endpoint_returns_current_user_records(self):
        with patch("app.routers.styles.list_saved_styles", new=AsyncMock(return_value=[{
            "id": "style-1",
            "name": "冷萃晶透风",
            "style": {"id": "style_reference", "name": "冷萃晶透风", "keywords": ["冷感"], "primary_color": "#A8DDE8"},
            "created_at": "2026-05-14T00:00:00+00:00",
            "updated_at": "2026-05-14T00:00:00+00:00",
        }])) as list_mock:
            response = self.make_client().get("/api/styles/saved")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["name"], "冷萃晶透风")
        self.assertEqual(list_mock.call_args.args[0], "test-user")

    def test_delete_style_endpoint_deletes_current_user_record(self):
        with patch("app.routers.styles.delete_saved_style", new=AsyncMock(return_value=True)) as delete_mock:
            response = self.make_client().delete("/api/styles/saved/style-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": True, "id": "style-1"})
        self.assertEqual(delete_mock.call_args.args, ("test-user", "style-1"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest backend/tests/test_api_contracts.py::SavedStylesContractTests -q
```

Expected: FAIL because `app.routers.styles` does not exist.

- [ ] **Step 3: Create router and include it**

Create `backend/app/routers/styles.py` with:

```python
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
        clamped_limit = max(1, min(limit, 100))
        clamped_offset = max(0, offset)
        items = await list_saved_styles(current_user.user_id, clamped_limit, clamped_offset)
        return {"items": items, "limit": clamped_limit, "offset": clamped_offset}

    @router.post("/saved")
    async def save_account_style(
        request: SaveStyleRequest,
        current_user: AppSessionUserSnapshot = Depends(require_app_user),
    ) -> dict[str, Any]:
        result = await save_style(current_user.user_id, user_snapshot_dict(current_user), request.model_dump())
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        return result

    @router.delete("/saved/{style_id}")
    async def delete_account_saved_style(
        style_id: str,
        current_user: AppSessionUserSnapshot = Depends(require_app_user),
    ) -> dict[str, Any]:
        deleted = await delete_saved_style(current_user.user_id, style_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="saved style not found or database not configured")
        return {"deleted": True, "id": style_id}

except ModuleNotFoundError:
    router = None
```

Modify `backend/app/main.py`:

```python
from app.routers import history, models, projects, session, styles
```

and include:

```python
    if styles.router is not None:
        app.include_router(styles.router)
```

- [ ] **Step 4: Run API contract tests**

Run:

```powershell
python -m pytest backend/tests/test_api_contracts.py::SavedStylesContractTests -q
```

Expected: PASS.

### Task 3: Frontend API Helpers and Types

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/tests/static-ui-contract.test.cjs`

- [ ] **Step 1: Write failing static assertions**

Add assertions to `frontend/tests/static-ui-contract.test.cjs`:

```javascript
assertIncludes("lib/types.ts", "SavedStyleRecord", "frontend must type account saved style records");
assertIncludes("lib/api.ts", "fetchSavedStyles", "frontend API must list account saved styles");
assertIncludes("lib/api.ts", "saveSavedStyle", "frontend API must save a Gemini style to the account library");
assertIncludes("lib/api.ts", "deleteSavedStyle", "frontend API must delete an account saved style");
assertIncludes("lib/api.ts", "/api/styles/saved", "frontend API must call the account saved styles endpoint");
assertNotIncludes("lib/types.ts", "savedStyles: SavedStyleRecord[]", "project state must not persist the account saved style library");
```

- [ ] **Step 2: Run static test to verify failure**

Run:

```powershell
cd frontend; npm run test:static
```

Expected: FAIL because the saved style type and API helpers are missing.

- [ ] **Step 3: Add type and API helpers**

Add to `frontend/lib/types.ts`:

```ts
export type SavedStyleRecord = {
  id: string;
  name: string;
  style: StyleOption;
  created_at: string;
  updated_at: string;
};
```

Update `frontend/lib/api.ts` imports to include `SavedStyleRecord`, then add:

```ts
export async function fetchSavedStyles() {
  try {
    return await requestJson<{ items: SavedStyleRecord[]; limit: number; offset: number }>("/api/styles/saved", {
      timeoutMs: 15000
    });
  } catch (error) {
    rethrowMainAppRedirect(error);
    return { items: [], limit: 50, offset: 0 };
  }
}

export async function saveSavedStyle(style: StyleOption, name: string) {
  return requestJson<SavedStyleRecord>("/api/styles/saved", {
    method: "POST",
    body: JSON.stringify({ name, style }),
    timeoutMs: 15000
  });
}

export async function deleteSavedStyle(id: string) {
  return requestJson<{ deleted: boolean; id: string }>(`/api/styles/saved/${id}`, {
    method: "DELETE",
    timeoutMs: 15000
  });
}
```

- [ ] **Step 4: Run static test**

Run:

```powershell
cd frontend; npm run test:static
```

Expected: PASS.

### Task 4: Frontend Saved Style UI

**Files:**
- Modify: `frontend/components/StyleStep.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/tests/static-ui-contract.test.cjs`

- [ ] **Step 1: Write failing UI contract assertions**

Add assertions to `frontend/tests/static-ui-contract.test.cjs`:

```javascript
assertIncludes("components/StyleStep.tsx", "保存到我的风格", "AI custom style card must let users save good Gemini styles");
assertIncludes("components/StyleStep.tsx", "我的保存风格", "style step must render account saved styles");
assertIncludes("components/StyleStep.tsx", "onSelectSavedStyle", "style step must expose saved style selection");
assertIncludes("components/StyleStep.tsx", "onDeleteSavedStyle", "style step must expose saved style deletion");
assertIncludes("app/page.tsx", "fetchSavedStyles", "page must load account saved styles");
assertIncludes("app/page.tsx", "saveSavedStyle", "page must save the current Gemini style to the account library");
assertIncludes("app/page.tsx", "deleteSavedStyle", "page must delete account saved styles");
assertNotIncludes("app/page.tsx", "savedStyles,", "project state snapshots must not include account saved styles");
```

- [ ] **Step 2: Run static test to verify failure**

Run:

```powershell
cd frontend; npm run test:static
```

Expected: FAIL because UI wiring is missing.

- [ ] **Step 3: Add StyleStep props and markup**

Update `frontend/components/StyleStep.tsx` import:

```ts
import { Check, ImagePlus, Sparkles, Trash2, Wand2, X } from "lucide-react";
import type { SavedStyleRecord, StyleOption, StyleSource, UploadedFileInfo } from "@/lib/types";
```

Add props:

```ts
  savedStyles: SavedStyleRecord[];
  isLoadingSavedStyles: boolean;
  isSavingStyle: boolean;
  deletingSavedStyleId: string;
  onSaveCustomStyle: () => void;
  onSelectSavedStyle: (record: SavedStyleRecord) => void;
  onDeleteSavedStyle: (id: string) => void;
```

In the AI card, when `customStyle` exists, add a button:

```tsx
                <button className="outlineButton fullWidth" type="button" onClick={onSaveCustomStyle} disabled={isSavingStyle}>
                  {isSavingStyle ? "保存中..." : "保存到我的风格"}
                </button>
```

After preset styles, render account saved styles:

```tsx
        <div className="savedStyleLibrary">
          <div className="savedStyleHeader">
            <h3>我的保存风格</h3>
            <span>{isLoadingSavedStyles ? "读取中..." : `${savedStyles.length} 个`}</span>
          </div>
          {savedStyles.length ? (
            <div className="savedStyleGrid">
              {savedStyles.map((record) => (
                <article className="savedStyleCard" key={record.id}>
                  <h4 style={{ color: record.style.primary_color }}>{record.name}</h4>
                  <p>{record.style.keywords.slice(0, 4).join(" / ")}</p>
                  <div className="keywordRow">
                    {record.style.keywords.slice(0, 6).map((keyword) => (
                      <span key={keyword}>{keyword}</span>
                    ))}
                  </div>
                  <div className="savedStyleActions">
                    <button className="outlineButton" type="button" onClick={() => onSelectSavedStyle(record)}>
                      使用
                    </button>
                    <button className="iconButton dangerIconButton" type="button" aria-label={`删除 ${record.name}`} onClick={() => onDeleteSavedStyle(record.id)} disabled={deletingSavedStyleId === record.id}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="savedStyleEmpty">保存 Gemini 规划出的好风格后，可在这里跨项目复用。</p>
          )}
        </div>
```

- [ ] **Step 4: Wire page state and handlers**

Update imports in `frontend/app/page.tsx`:

```ts
  deleteSavedStyle,
  fetchSavedStyles,
  saveSavedStyle,
```

Add `SavedStyleRecord` to type imports.

Add state:

```ts
  const [savedStyles, setSavedStyles] = useState<SavedStyleRecord[]>([]);
  const [isLoadingSavedStyles, setIsLoadingSavedStyles] = useState(false);
  const [isSavingStyle, setIsSavingStyle] = useState(false);
  const [deletingSavedStyleId, setDeletingSavedStyleId] = useState("");
```

After defaults load, fetch saved styles:

```ts
      setIsLoadingSavedStyles(true);
      try {
        const saved = await fetchSavedStyles();
        setSavedStyles(saved.items);
      } finally {
        setIsLoadingSavedStyles(false);
      }
```

Add handlers:

```ts
  async function handleSaveCustomStyle() {
    if (!customStyle) {
      setStatusText("请先让 Gemini 规划或分析一个风格");
      return;
    }
    const name = window.prompt("保存风格名称", customStyle.name)?.trim();
    if (!name) return;
    setIsSavingStyle(true);
    try {
      const saved = await saveSavedStyle(customStyle, name);
      setSavedStyles((current) => [saved, ...current.filter((item) => item.id !== saved.id)].slice(0, 50));
      setStatusText(`已保存风格：${saved.name}`);
    } catch {
      setStatusText("保存风格失败");
    } finally {
      setIsSavingStyle(false);
    }
  }

  function selectSavedStyle(record: SavedStyleRecord) {
    setCustomStyle({ ...record.style, name: record.name });
    setStyleSource("ai_custom");
    setStatusText(`已使用保存风格：${record.name}`);
  }

  async function handleDeleteSavedStyle(id: string) {
    setDeletingSavedStyleId(id);
    try {
      await deleteSavedStyle(id);
      setSavedStyles((current) => current.filter((item) => item.id !== id));
      setStatusText("已删除保存风格");
    } catch {
      setStatusText("删除风格失败");
    } finally {
      setDeletingSavedStyleId("");
    }
  }
```

Pass props to `StyleStep`.

- [ ] **Step 5: Add focused styles**

Add to `frontend/app/globals.css`:

```css
.savedStyleLibrary {
  margin-top: 24px;
  display: grid;
  gap: 14px;
}

.savedStyleHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.savedStyleHeader h3 {
  margin: 0;
  font-size: 18px;
}

.savedStyleHeader span,
.savedStyleEmpty {
  color: var(--muted);
  font-size: 13px;
}

.savedStyleGrid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.savedStyleCard {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 14px;
  min-width: 0;
}

.savedStyleCard h4 {
  margin: 0 0 6px;
  font-size: 17px;
}

.savedStyleCard p {
  margin: 0;
  color: var(--muted);
}

.savedStyleActions {
  display: grid;
  grid-template-columns: 1fr 40px;
  gap: 8px;
  align-items: center;
}

.dangerIconButton {
  color: #a53434;
  background: #fff5f5;
}
```

- [ ] **Step 6: Run frontend static tests**

Run:

```powershell
cd frontend; npm run test:static
```

Expected: PASS.

### Task 5: Final Verification

**Files:**
- All changed files from tasks 1-4.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
python -m pytest backend/tests/test_history_isolation.py backend/tests/test_api_contracts.py::SavedStylesContractTests -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend focused tests**

Run:

```powershell
cd frontend; npm run test:static
```

Expected: PASS.

- [ ] **Step 3: Run full frontend tests**

Run:

```powershell
cd frontend; npm test
```

Expected: PASS or report pre-existing unrelated failures with exact output.

- [ ] **Step 4: Review diff**

Run:

```powershell
git diff -- backend/app/services/database.py backend/app/routers/styles.py backend/app/main.py backend/tests/test_history_isolation.py backend/tests/test_api_contracts.py frontend/lib/types.ts frontend/lib/api.ts frontend/components/StyleStep.tsx frontend/app/page.tsx frontend/app/globals.css frontend/tests/static-ui-contract.test.cjs
```

Expected: Diff only includes account saved style work.
