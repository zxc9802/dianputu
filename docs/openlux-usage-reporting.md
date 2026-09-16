# OpenLux usage reporting

Deploy the main application's `/api/sso/usage` endpoint with pending-status support first. Its `SSO_USAGE_SECRETS` entry `dianputu` must match this tool's own `USAGE_MONITOR_INTERNAL_SECRET`.

Server environment (also supported in the repository root's existing `.env`):

```dotenv
MAIN_APP_URL=https://your-main-app.example
USAGE_MONITOR_INTERNAL_SECRET=the-dianputu-specific-secret
USAGE_MONITOR_OUTBOX_DIR=/persistent-data/dianputu-usage
```

Use a persistent, non-public directory; mount/shared storage is needed across container restarts or replicas. Default: `data/usage-outbox` under the repository root. Ephemeral serverless storage cannot ensure durable delivery. No secrets, prompts, reference images, generated content or model error text are stored in this metadata outbox.

Only actual upstream hostname `api.openlux.ai` is reported with tool key `dianputu`. Existing model URLs, selection, text/image retries, alternate channels and business generation are unchanged. Yunwu and other providers remain excluded. No legacy `/api/sso/billing` flow exists here.

The async request dependency derives identity from the existing signed, unexpired SSO session. Local development identity is excluded. Background analysis, generation and edit tasks capture that server-derived identity before request context cleanup; body fields cannot change the attributed user. The backend's existing signed-session validation is retained; this change does not add a live revocation check against the main app.

Every actual text/image/edit model POST receives a separate UUID, including retry/fallback attempts. Reference downloads, image composition and polling are not model requests. OpenAI-compatible Chat/Responses/Gemini usage is parsed with missing values null and explicit zero retained. Image input/cache/reasoning details are captured where reported. Image calls without usage still report completion with null Tokens; the main app owns pricing.

Pending metadata is atomically persisted before each model POST. Delivery retries reuse the UUID; completed/failed/interrupted events are persisted separately. Queue draining runs on later authenticated project requests and after model calls, bounded to 10 events with a 2-second reporting timeout per delivery, stopping on failure. To retry an idle queue, run from the repo root:

```sh
PYTHONPATH=backend python -m app.services.usage_monitor
```

PowerShell: set `$env:PYTHONPATH='backend'`, then run `python -m app.services.usage_monitor`. Repeat until no events remain or use the deployment's existing scheduler. No persistent background worker is added. A killed process can leave pending events; these never become completed automatically. Current provider adapters consume synchronous responses; HTTP 202/queued upstream responses stay pending because these adapters have no upstream async-task polling implementation. Correct inaccessible/full outbox storage when a storage error is logged; reporting failures do not fail successful generation.

Verification (mocked requests only): `PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_usage*.py'`. Full suite baseline currently has 14 existing generation/material test failures on upstream `51ec0da`; the same failures remain after this change. No paid model or production data calls are needed.
