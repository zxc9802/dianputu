# SSO History Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the image generation tool to the company main site through ticket SSO and isolate project history by main-site account.

**Architecture:** The main site creates and exchanges one-time `detail-image-agent` tickets using the existing `video_sso_tickets` table. The image tool exchanges tickets in Next middleware, writes an app-local signed cookie, and FastAPI validates that same cookie for `/api/*` requests. History rows are owned by `user_id`, and all list/get/save/delete paths filter by the authenticated user.

**Tech Stack:** Next.js/React/TypeScript on both frontends, FastAPI/Python for the image backend, PostgreSQL via asyncpg, Node `node:test`, Python `unittest`.

---

### Task 1: Main-Site Detail Image Agent SSO

**Files:**
- Create: `/Users/a123/Desktop/dianshangjiqiren/frontend/app/lib/detail-image-agent-site.ts`
- Create: `/Users/a123/Desktop/dianshangjiqiren/frontend/app/lib/detail-image-agent-sso.ts`
- Create: `/Users/a123/Desktop/dianshangjiqiren/frontend/app/api/detail-image-agent-sso/start/route.ts`
- Create: `/Users/a123/Desktop/dianshangjiqiren/frontend/app/api/detail-image-agent-sso/exchange/route.ts`
- Create: `/Users/a123/Desktop/dianshangjiqiren/frontend/app/bot/detail-image-agent/page.tsx`
- Create: `/Users/a123/Desktop/dianshangjiqiren/frontend/app/bot/detail-image-agent/DetailImageAgentLaunchClient.tsx`
- Create: `/Users/a123/Desktop/dianshangjiqiren/frontend/tests/detailImageAgentSsoLauncher.test.mjs`
- Modify: `/Users/a123/Desktop/dianshangjiqiren/frontend/app/page.tsx`
- Modify: `/Users/a123/Desktop/dianshangjiqiren/frontend/.env.example`

- [ ] **Step 1: Write failing main-site SSO launcher tests**

Add `frontend/tests/detailImageAgentSsoLauncher.test.mjs` with assertions that:

- detail image agent site metadata exists with `entryPath: '/bot/detail-image-agent'`
- homepage image tool card uses `/bot/detail-image-agent?autostart=1&openMode=replace` and requires auth
- SSO helper builds a URL on `DETAIL_IMAGE_AGENT_APP_URL`
- SSO helper uses product key `detail-image-agent`
- start/exchange API route files import the new helper

- [ ] **Step 2: Verify tests fail**

Run:

```bash
cd /Users/a123/Desktop/dianshangjiqiren/frontend
node --test tests/detailImageAgentSsoLauncher.test.mjs
```

Expected: FAIL because the new files and metadata do not exist.

- [ ] **Step 3: Implement main-site SSO and launcher**

Duplicate the proven `kb-chat` pattern with product-specific names:

- `DETAIL_IMAGE_AGENT_PRODUCT = 'detail-image-agent'`
- `DETAIL_IMAGE_AGENT_APP_URL`
- `/api/detail-image-agent-sso/start`
- `/api/detail-image-agent-sso/exchange`
- `/bot/detail-image-agent` launcher

Update the homepage image tool card to open the new SSO-protected launcher.

- [ ] **Step 4: Verify main-site tests pass**

Run:

```bash
cd /Users/a123/Desktop/dianshangjiqiren/frontend
node --test tests/detailImageAgentSsoLauncher.test.mjs
```

Expected: PASS.

### Task 2: Image Tool Session Validation

**Files:**
- Create: `/Users/a123/Desktop/自动生成店铺图片/frontend/lib/server/app-session.ts`
- Create: `/Users/a123/Desktop/自动生成店铺图片/frontend/middleware.ts`
- Create: `/Users/a123/Desktop/自动生成店铺图片/backend/app/services/app_session.py`
- Create: `/Users/a123/Desktop/自动生成店铺图片/backend/app/dependencies/auth.py`
- Create: `/Users/a123/Desktop/自动生成店铺图片/backend/app/routers/session.py`
- Create: `/Users/a123/Desktop/自动生成店铺图片/backend/tests/test_app_session.py`
- Modify: `/Users/a123/Desktop/自动生成店铺图片/backend/app/main.py`
- Modify: `/Users/a123/Desktop/自动生成店铺图片/backend/app/routers/projects.py`
- Modify: `/Users/a123/Desktop/自动生成店铺图片/backend/app/routers/models.py`
- Modify: `/Users/a123/Desktop/自动生成店铺图片/.env.example`

- [ ] **Step 1: Write failing app session tests**

Add tests that create a signed session cookie, verify it reads back the user, reject tampered signatures, reject expired sessions, and return a local dev user when `REQUIRE_MAIN_APP_SSO=false`.

- [ ] **Step 2: Verify app session tests fail**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片
PYTHONPATH=backend python -m unittest backend.tests.test_app_session -v
```

Expected: FAIL because `app.services.app_session` does not exist.

- [ ] **Step 3: Implement Next and FastAPI session layers**

Add matching HMAC/base64url session helpers in Next and Python. Next middleware handles HTML redirects and ticket exchange. FastAPI exposes `/api/session` and dependency helpers for protected routes.

- [ ] **Step 4: Protect FastAPI routers**

Add the auth dependency to `/api/projects`, `/api/models/config`, and `/api/history` after Task 3. Keep `/health` public.

- [ ] **Step 5: Verify app session tests pass**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片
PYTHONPATH=backend python -m unittest backend.tests.test_app_session -v
```

Expected: PASS.

### Task 3: Per-Account Project History

**Files:**
- Modify: `/Users/a123/Desktop/自动生成店铺图片/backend/app/services/database.py`
- Modify: `/Users/a123/Desktop/自动生成店铺图片/backend/app/routers/history.py`
- Create: `/Users/a123/Desktop/自动生成店铺图片/backend/tests/test_history_isolation.py`

- [ ] **Step 1: Write failing history isolation tests**

Add tests that use a fake asyncpg pool to assert:

- `list_history('user-a')` queries with `user_id = $1`
- `get_history('user-a', 'record-1')` cannot read other users because it uses both IDs
- `save_history('user-a', snapshot, record)` inserts owner fields
- `delete_history('user-a', 'record-1')` deletes with both IDs

- [ ] **Step 2: Verify history tests fail**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片
PYTHONPATH=backend python -m unittest backend.tests.test_history_isolation -v
```

Expected: FAIL because history helpers do not accept `user_id`.

- [ ] **Step 3: Implement history schema and CRUD ownership**

Add `user_id` and `user_snapshot_json` columns, add a `(user_id, created_at DESC)` index, and update every history helper and route to use `CurrentUser`.

- [ ] **Step 4: Verify history tests pass**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片
PYTHONPATH=backend python -m unittest backend.tests.test_history_isolation -v
```

Expected: PASS.

### Task 4: Image Tool Frontend Auth-Aware Requests

**Files:**
- Create: `/Users/a123/Desktop/自动生成店铺图片/frontend/lib/client/api-response.ts`
- Create: `/Users/a123/Desktop/自动生成店铺图片/frontend/lib/client/app-session.ts`
- Modify: `/Users/a123/Desktop/自动生成店铺图片/frontend/lib/api.ts`
- Modify: `/Users/a123/Desktop/自动生成店铺图片/frontend/lib/historyApi.ts`
- Modify: `/Users/a123/Desktop/自动生成店铺图片/frontend/app/page.tsx`
- Create or modify tests under `/Users/a123/Desktop/自动生成店铺图片/frontend/tests`

- [ ] **Step 1: Write failing frontend static tests**

Extend frontend static tests to assert:

- API fetches include `credentials: "include"`
- 401 responses with `redirectUrl` trigger main-site redirect handling
- local fallback history key includes `:<userId>`
- page imports `useAppViewer` or otherwise waits for session identity before history use

- [ ] **Step 2: Verify frontend tests fail**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/frontend
npm run test:static
```

Expected: FAIL because auth-aware helpers and scoped local history are not implemented.

- [ ] **Step 3: Implement frontend auth-aware helpers**

Add the client helpers from the design, update API requests to include credentials and redirect on unauthorized, and scope local history storage by the current session user.

- [ ] **Step 4: Verify frontend tests pass**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/frontend
npm run test:static
```

Expected: PASS.

### Task 5: Full Verification

**Files:**
- Modify docs/env examples as needed.

- [ ] **Step 1: Run image backend tests**

```bash
cd /Users/a123/Desktop/自动生成店铺图片
PYTHONPATH=backend python -m unittest discover backend/tests -v
```

- [ ] **Step 2: Run image frontend tests**

```bash
cd /Users/a123/Desktop/自动生成店铺图片/frontend
npm test
```

- [ ] **Step 3: Run main-site SSO tests**

```bash
cd /Users/a123/Desktop/dianshangjiqiren/frontend
node --test tests/detailImageAgentSsoLauncher.test.mjs tests/tiktokVideoSsoLauncher.test.mjs
```
