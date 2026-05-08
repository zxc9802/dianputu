# SSO And Per-Account History Isolation Design

## Context

The image generation tool in `/Users/a123/Desktop/自动生成店铺图片` currently runs as a standalone Next.js frontend plus FastAPI backend. It stores generation history in `project_history`, but the table has no account owner column, so all backend history is shared.

The company main site in `/Users/a123/Desktop/dianshangjiqiren` already has a ticket-based SSO pattern for external tools:

- `video-sso` stores one-time tickets in `video_sso_tickets`.
- `kb-chat-sso` reuses that table with a distinct `product = 'kb-chat'`.
- The main site start endpoint requires the logged-in main-site JWT, creates a short-lived ticket, and returns the external app URL with `ticket` and `mainApp`.
- The external app exchanges the ticket, receives `token`, `user`, and `redirectPath`, then creates its own app-local session.

The new image tool integration should follow this same pattern so it behaves consistently with `kb-chat`.

## Goals

- Users enter the image tool through the company main site after logging in.
- Direct visits to the image tool redirect back to the main-site entry.
- The image tool stores a signed, HTTP-only app session cookie after exchanging a one-time ticket.
- Every protected frontend/backend request can resolve the current main-site user.
- Image generation history is isolated by main-site account.
- Different accounts on the same browser do not see each other's local fallback history.
- Existing unauthenticated local development remains possible when SSO is explicitly disabled.

## Non-Goals

- Replace the main site's existing login method.
- Introduce OAuth/OIDC providers.
- Merge image tool history into the main site's existing image-generation tables.
- Change the image generation workflow, prompts, model configuration, or UI layout beyond login/history identity needs.

## Recommended Approach

Use the existing main-site ticket SSO architecture and add a new product integration named `detail-image-agent`.

Main site responsibilities:

- Add metadata for the external image tool: product key, display name, entry path, and app URL.
- Add a launcher page, likely `/bot/detail-image-agent`, matching the `kb-chat` launcher behavior.
- Add `POST /api/detail-image-agent-sso/start`.
- Add `POST /api/detail-image-agent-sso/exchange`.
- Store tickets in the existing `video_sso_tickets` table with `product = 'detail-image-agent'`.

Image tool responsibilities:

- Add Next.js SSO/session helpers adapted from `kb-chat/lib/server/app-session.ts`.
- Add a Next middleware/proxy that protects HTML routes and handles ticket exchange.
- Exchange `ticket` with the main site's `detail-image-agent-sso/exchange` endpoint.
- Store an app-local signed cookie containing `token`, `user`, `mainAppUrl`, and `expiresAt`.
- Add FastAPI `/api/session` for frontend session display and client-side 401 redirect behavior.
- Keep production API calls same-origin through the existing nginx `/api/` route so the browser sends the app session cookie to FastAPI.
- Add FastAPI session validation so backend endpoints can derive `current_user`.
- Scope project history by `current_user.user_id`.

## SSO Flow

1. User clicks the image tool entry on the main site.
2. If the main-site JWT is missing, the main site sends the user to `/login?redirect=/bot/detail-image-agent?autostart=1`.
3. The launcher calls `POST /api/detail-image-agent-sso/start` with the main-site Bearer token.
4. The main site creates a one-time ticket with a short expiry and returns the image tool URL:
   `/ ?ticket=<ticket>&mainApp=<main-site-origin>`.
5. The image tool middleware sees `ticket`, calls `MAIN_APP_DETAIL_IMAGE_AGENT_SSO_EXCHANGE_PATH`, and receives:
   - `token`
   - `user.id`
   - optional `user.account`, `user.email`, `user.nickname`, `user.groupName`, `user.role`
   - `redirectPath`
6. The image tool writes its own signed HTTP-only cookie and redirects to `redirectPath` without the ticket.
7. Later unauthorized requests return `401` with `redirectUrl`; the frontend redirects back to the main-site entry.

## Main Site Changes

Add a sibling implementation to `frontend/app/lib/kb-chat-sso.ts`, for example `frontend/app/lib/detail-image-agent-sso.ts`:

- `DETAIL_IMAGE_AGENT_PRODUCT = 'detail-image-agent'`
- `DETAIL_IMAGE_AGENT_SSO_TICKET_TTL_MS = 60_000`
- `getDetailImageAgentAppUrl()`
- `getMainAppDetailImageAgentEntryUrl()`
- `buildDetailImageAgentSsoUrl(ticketId, options)`
- `createDetailImageAgentSsoTicket(userId, redirectPath)`
- `consumeDetailImageAgentSsoTicket(ticketId)`

The consume function should match `kb-chat` access rules:

- Ticket must exist.
- Ticket product must match `detail-image-agent`.
- Ticket must be unused and unexpired.
- User must exist.
- User must be admin or have `accessGrantedAt`.
- Ticket is marked used in the same transaction.
- Response includes `redirectPath` and a public user object.

Add API routes:

- `frontend/app/api/detail-image-agent-sso/start/route.ts`
- `frontend/app/api/detail-image-agent-sso/exchange/route.ts`

Add launcher:

- `frontend/app/bot/detail-image-agent/page.tsx`
- client component modeled after `KbChatLaunchClient`

Add homepage bot entry:

- Replace or augment the existing local `/bot/image-generator` card depending on deployment.
- The SSO-protected external tool entry should point to `/bot/detail-image-agent?autostart=1&openMode=replace`.

Environment variables:

- `DETAIL_IMAGE_AGENT_APP_URL`
- optional fallback aliases only if needed for deployment compatibility

## Image Tool Session Changes

Add frontend session helpers under the image tool's `frontend/lib` tree:

- `frontend/lib/server/app-session.ts`
- `frontend/lib/client/api-response.ts`
- `frontend/lib/client/app-session.ts`
- Next middleware/proxy file, adapted to the installed Next version.

Do not add a Next `/api/session` route for the deployed app. The current Docker/nginx setup sends `/api/` directly to FastAPI, so `/api/session` must be implemented by FastAPI instead.

Configuration should mirror `kb-chat` with product-specific names:

- `MAIN_APP_URL`
- `MAIN_APP_DETAIL_IMAGE_AGENT_ENTRY_PATH=/bot/detail-image-agent`
- `MAIN_APP_DETAIL_IMAGE_AGENT_SSO_EXCHANGE_PATH=/api/detail-image-agent-sso/exchange`
- `REQUIRE_MAIN_APP_SSO=true`
- `DETAIL_IMAGE_AGENT_SESSION_SECRET`
- `DETAIL_IMAGE_AGENT_SESSION_COOKIE_NAME=detail_image_agent_session`
- `DETAIL_IMAGE_AGENT_SESSION_TTL_MINUTES=720`

Local development behavior:

- If `REQUIRE_MAIN_APP_SSO=false`, the app returns a deterministic local dev user and does not redirect.
- In production, SSO defaults to required.

## FastAPI Auth Changes

The FastAPI backend needs to trust the same app session identity used by the Next frontend. Production requests already reach FastAPI through same-origin nginx routing at `/api/`, so the browser will include the image tool session cookie on API requests. Add a Python session validator equivalent to the Next signer:

- Parse the `detail_image_agent_session` cookie.
- Split payload and HMAC signature.
- Verify HMAC-SHA256 using `DETAIL_IMAGE_AGENT_SESSION_SECRET`.
- Decode the base64url JSON payload.
- Reject missing, malformed, tampered, or expired sessions.
- Extract `user.id` as `current_user.user_id`.

Add an auth dependency, for example:

- `backend/app/services/app_session.py`
- `backend/app/dependencies/auth.py`

Add a FastAPI session route:

- `GET /api/session`
- Returns `{ success: true, data: { requiresSso, session } }` when authorized.
- Returns `401` with `redirectUrl` when the user must re-enter through the main site.

Protected routers should use the dependency for all state-changing or user-data endpoints:

- `/api/projects/*`
- `/api/history/*`
- `/api/models/config` can remain public if desired, but keeping it protected is consistent with the tool being private.
- `/health` remains public.

If SSO is disabled locally, the dependency returns a deterministic local user such as `detail-image-agent-local-dev-user`.

## History Isolation

The current `project_history` table must gain ownership fields:

- `user_id TEXT NOT NULL DEFAULT 'legacy-shared-user'`
- `user_snapshot_json TEXT NOT NULL DEFAULT '{}'`

Indexes:

- Replace or supplement `idx_history_created` with `idx_history_user_created ON project_history (user_id, created_at DESC)`.

Primary key strategy:

- Keep `id TEXT PRIMARY KEY` for compatibility.
- Every read, update, and delete must include `user_id = current_user.user_id`.
- This prevents cross-account access even if a user knows another record ID.

CRUD behavior:

- `list_history(user_id, limit, offset)` returns only that user's metadata.
- `get_history(user_id, record_id)` returns only that user's record or `None`.
- `save_history(user_id, user_snapshot, record)` inserts with owner fields.
- `save_history` updates only when the existing row belongs to the same user.
- `delete_history(user_id, record_id)` deletes only that user's record.

Legacy data:

- Existing records without a real user owner should be assigned to `legacy-shared-user`.
- Authenticated users should not see `legacy-shared-user` records by default.
- Local development with SSO disabled can keep using the local dev user. If preserving old shared history in local dev is important, that can be added as a temporary import path rather than mixing it into production accounts.

## Frontend History Behavior

Current frontend fallback history uses one shared localStorage key:

- `detail-image-agent-history`

Change it to be account-scoped:

- `detail-image-agent-history:<userId>`

The frontend should load `/api/session` first, resolve `viewer.id`, then pass that user ID into history helpers or initialize a small history client with the scoped key.

When a request receives `401` plus `redirectUrl`, frontend helpers should redirect to the main-site entry rather than silently falling back to shared local history.

Fallback history remains useful when:

- database is unavailable
- local development is running without SSO

It must not merge records across different authenticated users.

## API Data Flow

For generation endpoints:

- Browser calls same-origin `/api/projects/*`.
- The request includes the app session cookie.
- FastAPI validates the session and proceeds.
- Generated images and edits behave as before.

For history endpoints:

- Browser calls same-origin `/api/history/*`.
- FastAPI validates the session.
- History database queries are scoped by `current_user.user_id`.
- Response shape remains compatible with existing frontend types.

## Error Handling

- Missing or invalid app session returns `401` with `redirectUrl`.
- Expired SSO ticket exchange clears the image tool session cookie and redirects to the main-site entry.
- Invalid `mainApp` query values are ignored unless they match the configured main-site origin or a local dev origin.
- History record not found returns `404` whether it does not exist or belongs to another user.
- Database unavailable can still use local fallback history, but the fallback key must include the current user ID.

## Testing

Image tool tests:

- Session cookie accepts valid HMAC payload.
- Session cookie rejects tampered payload.
- Expired session returns unauthorized.
- History list filters by user ID.
- History detail cannot read another user's record.
- History update/delete cannot affect another user's record.
- Local fallback history key includes user ID.

Main site tests:

- Detail image agent SSO creates tickets with `product = 'detail-image-agent'`.
- Exchange rejects tickets for other products.
- Exchange rejects expired or used tickets.
- Launcher redirects unauthenticated users to login with the original launcher path.

Manual verification:

- Account A enters from main site, saves history, sees only A records.
- Account B enters from main site in the same browser after logout/login, sees only B records.
- Direct visit to image tool while unauthenticated redirects to the main-site entry.
- Expired image tool session redirects back to the main-site entry.

## Rollout

1. Add main-site SSO routes and launcher for `detail-image-agent`.
2. Add image tool SSO session and middleware.
3. Add FastAPI session validation dependency.
4. Migrate `project_history` schema with `user_id` and `user_snapshot_json`.
5. Scope all history service and router calls by current user.
6. Scope frontend local fallback history by current user.
7. Update `.env.example` and deployment docs for both projects.
8. Run tests and manual account-switch verification.
