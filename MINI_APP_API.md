# Telegram Mini App — Backend API Contract

The backend is the single source of truth. Every endpoint below is a thin
HTTP wrapper around `QueueEngine`, `SessionManager`, or `StatisticsEngine`
— none of them contain business logic of their own, and none of them
duplicate what those classes already do. `mini_app_api.py`'s
`MiniAppService` is the only thing that translates between HTTP JSON and
the existing Python service objects.

Base URL: no fixed prefix required -- routes are called as-is (e.g.
`/session/current`), and this is what `client.ts` actually uses. An
`/api/*` prefix is ALSO accepted as an alias (`_dispatch()` strips a
leading `/api` and retries the match) -- confirmed by direct inspection
of `mini_app_api.py`'s `_dispatch()`, correcting a previous, incomplete
note here that called the `/api` prefix nonexistent; it exists as an
accepted alias, just isn't the one the frontend uses.

`client.ts`'s `VITE_API_BASE_URL` now defaults to `''` (relative,
same-origin) rather than an absolute URL -- this matches the project's
actual deployment path (`start_mini_app.py` builds the frontend and
points `mini_app_api.py` at it via `MINI_APP_STATIC_DIR`, so both are
served from the same origin/port and relative paths resolve correctly
through the ngrok tunnel). Only set `VITE_API_BASE_URL` explicitly if
running the frontend as a separate `npm run dev` process against a
different-origin backend.
Server: `mini_app_api.py`, runs as its own process (`python mini_app_api.py`,
default port 8000), separate from the Telegram bot process. Both share the
same SQLite database file.

## Ownership model

This mirrors exactly how the existing backend is already structured — no
new components were introduced, only clarified:

| Owns | Class | Notes |
|---|---|---|
| Queue, current customer, status transitions | `QueueEngine` | The Mini App never writes customer status directly; it calls `apply_action`, `next_customer`, `peek_next_customer`, `pause`, `restart_call_later`. One exception: `start_call`'s explicit-customer-id path writes `queue_session` directly via `database.update_queue_session()` rather than through a `QueueEngine` method — see `BACKLOG.md` item on this. |
| Active session, progress, resume, completion | `SessionManager` | `MiniAppService` calls `start_current_session` / `complete_current_session`, never touches the `sessions` table directly. |
| Analytics, history, exports | `StatisticsEngine` / `export_engine` | All event recording goes through `StatisticsEngine.record_event`; exports go through `export_engine.export_customers`. |
| Presentation only | Mini App frontend | Receives JSON, renders it, sends user intent back as HTTP calls. It should never need to know queue/session/statistics business rules to function correctly. |

`MiniAppService` itself is not "the frontend" — it's a backend adapter
(like `telegram_ui.py`/`queue_ui.py` are for the bot). It owns HTTP
JSON shaping only.

## Authentication

Uses Telegram's official [Mini App initData validation](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)
algorithm — implemented in `telegram_auth.py`, no custom auth system.

**How to send it:** `Authorization: tma <initData>` header (Telegram's
recommended scheme). Confirmed by direct inspection of `_authenticate()`
in `mini_app_api.py`: only the `Authorization` header is checked -- there
is no `X-Telegram-Init-Data` fallback despite a previous version of this
doc claiming one existed. `initData` is the raw string Telegram's WebApp
JS SDK exposes as `window.Telegram.WebApp.initData`.

**Current enforcement (fixed as of the 2026-07-29 security remediation pass):**
- No `Authorization` header at all → **401** on every endpoint in
  `_API_PATHS` (everything except `/` and static assets, which must stay
  reachable without credentials -- that's how the frontend's own JS gets
  loaded before it has anything to authenticate with).
- An `Authorization` header **is** present but fails validation (bad
  signature, expired `auth_date`, malformed) → **401**, as before.
- A **validated, signature-checked** initData payload with no `user`
  field (a legitimate startup-context init, see `extract_user_id`) is
  still let through -- it proved Telegram origin, it just isn't
  attributable to a specific user. This is a distinct case from "no
  header at all" and is tracked separately (`self._auth_verified` in
  `mini_app_api.py`), not conflated with it.
- `MINI_APP_ALLOW_ANONYMOUS=1` (env var, `Settings.mini_app_allow_anonymous`,
  **off by default**) is an explicit opt-in escape hatch for local
  browser testing outside a real Telegram client, where no `initData`
  exists at all. Do not set this outside local dev.

This was previously deferred pending two things, both since confirmed:
the frontend now sends the header on every request unconditionally when
available (`frontend/src/api/client.ts`), and the "might fire before
Telegram's WebApp script finishes initializing" race turned out not to
apply given `frontend/index.html`'s script ordering (`telegram-web-app.js`
loads synchronously in `<head>`, before the app's own module script) --
by the time any app code runs, `initData` is already populated.

`auth_date` freshness window: `MINI_APP_AUTH_MAX_AGE_SECONDS` env var
(default 86400 = 24h).

## Endpoints

### `GET /session/current`
- **Purpose:** Full dashboard state — session info, progress, current customer, today's stats.
- **Request:** none.
- **Response:**
  ```json
  {
    "sessionId": 12,
    "currentCustomerIndex": 4,
    "customerCount": 20,
    "answeredToday": 9,
    "estimatedRemaining": 16,
    "averageCallTime": "2m 18s",
    "completed": false,
    "currentCustomer": { "...": "see /customer/current shape" },
    "progress": { "remaining": 16, "contacted": 3, "didNotAnswer": 1, "percent": 20 }
  }
  ```
- **Errors:** none (always 200; empty/zero state if nothing imported).
- **Caller:** Mini App, on load and after most actions.
- **Status:** ✅ implemented. Side-effect-free (peeks, never advances the
  queue). Also the one place that finalizes a session once it's fully
  handled (see "Session Finished" below).

### `GET /customer/current`
- **Purpose:** Just the current (or next-up) customer, without the full session envelope.
- **Response:** `{"id": "5", "name": "...", "loanNumber": "...", "balance": "...", "daysLate": "...", "phone": "...", "notes": [...], "status": "waiting", "isBlacklisted": false}` or `{}` if none.
- **Status:** ✅ implemented. Side-effect-free (peek only).

### `GET /customer/search?q=<query>`
- **Purpose:** Search by name, loan number, or phone number substring. Mirrors Telegram's `/customer <query>`.
- **Response:** `{"results": [ {...same shape as /customer/current...}, ... ]}` (up to 20).
- **Status:** ✅ implemented (customer-history pass). Searches every customer regardless of status.

### `GET /customer/record?id=<id>`
- **Purpose:** The full customer view — Phase 2's shared record: identity, blacklist state (customer- and phone-level), notes, and full event history. This is `Database.get_customer_record()` verbatim — the exact same method Telegram's `/customer` and "More Info" use, not a separate assembly.
- **Response:** base customer fields (snake_case, unlike the camelCase `/customer/current` shape — this is the raw repository record) plus `"notes": [{"text", "telegram_user_id", "timestamp"}, ...]`, `"history": [{"event_type", "telegram_user_id", "event_timestamp", "notes", ...}, ...]`, `"blacklisted_phones": [...]`, `"is_blacklisted": bool`.
- **Errors:** `404 {"error": "Customer not found"}`; `400` if `id` missing.
- **Status:** ✅ implemented.

### `POST /customer/edit`
- **Purpose:** Edit a customer's own fields. Mirrors Telegram's `/edit`.
- **Request:** `{"customerId": 5, "fields": {"balance": "500", "phone_numbers": ["+15551234567"]}}`. Editable: `first_name`, `last_name`, `balance`, `days_overdue`, `phone_numbers` (already-normalized list — the Mini App frontend, when built, should run values through the same normalization `validation.normalize_phone_number` does before sending, same as Telegram's `/edit` does). **Not editable:** `loan_number` (the import-time unique key) or `status` (that's `/call/result`'s job).
- **Response:** `{"ok": true, "customer": {...}}` or `{"ok": false, "error": "Customer not found"}`.
- **Status:** ✅ implemented. Delegates to `QueueEngine.edit_customer`, which audits exactly what changed.

### `POST /customer/blacklist`
- **Purpose:** Blacklist or un-blacklist a whole customer. Mirrors Telegram's `/blacklist` / `/unblacklist`.
- **Request:** `{"customerId": 5, "blacklisted": true}`
- **Response:** `{"ok": true, "customer": {...}}`
- **Status:** ✅ implemented. State + audit trail only — does **not** auto-skip blacklisted customers in the calling queue (deliberate, see `BACKLOG.md`).

### `POST /phone/blacklist`
- **Purpose:** Blacklist or un-blacklist a single phone number, independent of any customer record. Mirrors Telegram's `/blacklist_phone` / `/unblacklist_phone`.
- **Request:** `{"phone": "+15551234567", "blacklisted": true, "reason": "abuse"}`
- **Response:** `{"ok": true, "phone": "...", "blacklisted": true}`
- **Status:** ✅ implemented.

### `POST /call/start`
- **Purpose:** "Call Started" event. Marks a customer as the active one and starts the session if needed.
- **Request:** `{"customerId": "5"}` (optional — omit to let the engine pick the next customer).
- **Response:** `{"ok": true, "customerId": 5, "startedAt": "2026-07-13T..."}`
- **Errors:** `{"ok": false, "error": "No customer available"}` if the queue is empty and no id was given.
- **Caller:** Mini App, when the operator taps "Call".
- **Status:** ✅ implemented. Explicit-id path writes `queue_session`
  directly via `database.update_queue_session()` (not through a
  `QueueEngine` method — see `BACKLOG.md`).

> **Note:** `POST /call/return` was previously documented here as
> implemented. It does not exist in `mini_app_api.py` — confirmed by
> direct route inspection. See `BACKLOG.md` item on this. Not adding it
> speculatively; nothing currently needs it.

### `POST /call/result`
- **Purpose:** "Outcome Selected" event. Applies the outcome and advances the queue in one committed step.
- **Request:** `{"customerId": "5", "outcome": "answered", "duration": 132}`. Outcomes: `answered`/`contacted` → warned, `did_not_answer`/`call_again` → call_later, `wrong_number` → invalid_number, `skip` → skip, `paid` → paid.
- **Response:**
  ```json
  {
    "ok": true, "customerId": 5, "outcome": "answered", "status": "warned", "duration": 132,
    "nextCustomer": { "...": "customer payload, or null if queue is empty" },
    "session": { "...": "same shape as GET /session/current" }
  }
  ```
  The response already includes the next customer/session — the frontend
  should use these directly rather than calling `/session/next`
  afterward, which would advance the queue a **second** time.
- **Status:** ✅ implemented. Delegates to `QueueEngine.apply_action`, so it gets the same validity guards Telegram has (e.g. a `needs_review` customer can only be skipped/marked invalid). Persists `duration` to `customer_events.duration_seconds`.

### `POST /session/next`
- **Purpose:** "Next Customer Requested" — explicitly advance the queue without submitting an outcome (e.g. operator taps "Skip" without an outcome flow, or manually re-syncs).
- **Response:** `{"customer": {...}, "session": {...}}`
- **Status:** ✅ implemented. This is the one endpoint that intentionally commits a queue advance from a client-initiated action outside of `/call/result`. **Do not call this after `/call/result`** — see note above.

### `POST /note`
- **Purpose:** Save an operator note against a customer, without submitting a call outcome.
- **Request:** `{"customerId": "5", "note": "Wife answered, call back after 4pm"}`
- **Response:** `{"ok": true, "customerId": 5, "note": "..."}`
- **Status:** ✅ implemented. Recorded as `customer_note_added` (fixed this pass — previously miscounted as `customer_warned`, which inflated daily "contacted" stats).

### `POST /queue/pause`
- **Purpose:** Pause the queue (mirrors Telegram's `/pause`).
- **Response:** `{"ok": true, "paused": true}`
- **Status:** ✅ implemented. No explicit `/queue/resume` yet — resuming currently only happens as a side effect of `/call/start` or `/call/result` calling `SessionManager.start_current_session`. Add `POST /queue/resume` → `QueueEngine.resume()` if the Mini App needs an explicit un-pause button.

### `POST /queue/call-back`
- **Purpose:** Requeue every `call_later` customer back to `waiting` (mirrors Telegram's "Call Back" button).
- **Response:** `{"ok": true, "customer": {...}, "session": {...}, "complete": false}`
- **Status:** ✅ implemented.

### `GET /export?format=csv|json|xlsx`
- **Purpose:** Download all customer records (mirrors Telegram's `/export` admin command).
- **Auth required:** yes. `Authorization: tma <initData>` with a Telegram user id in `ADMIN_TELEGRAM_USER_IDS`. Missing or non-admin credentials → `403`.
- **Response:** Binary file stream, `Content-Disposition: attachment`.
- **Errors:** `403 {"error": "Admin authorization required for export."}` if not an admin; `400 {"error": "No customers to export."}` if nothing to export.
- **Status:** ✅ implemented, including the authorization gate (added in the architecture consolidation pass — see `ARCHITECTURE.md`). Matches Telegram's `/export` exactly via the shared `security.is_admin()`. Successful exports are audit-logged (`admin_action` event in `customer_events`), same as Telegram's.

### `GET /statistics`
- **Purpose:** "Statistics Updated" read — today's and lifetime numbers.
- **Response:** `{"today": {...}, "lifetime": {...}, "averageContactsPerSession": N, "averageSecondsPerCustomer": N, "todaysCalls": N, "answered": N, "didntAnswer": N, "wrongNumber": 0, "averageCallTime": "...", "successRate": "67%", "lifetimeCalls": N, "sessions": N, "customersContacted": N, "bestDay": "N/A"}`
- **Status:** ✅ implemented. `wrongNumber` and `bestDay` are always placeholder values (`0` / `"N/A"`) — `StatisticsEngine` doesn't currently break out "invalid_number" as its own daily-tracked bucket or track per-day volume for a "best day" comparison. Not fixed here since it would mean extending `StatisticsEngine`'s schema/logic, which is out of scope for "expose what exists."

## Session Finished (backend event)

There's no separate `POST /session/complete` endpoint. Instead,
`GET /session/current` (called by the frontend on basically every screen)
detects when `progress.remaining == 0` and `total_customers > 0`, and
calls `SessionManager.complete_current_session()` as a side effect —
finalizing `duration_seconds`, `finished_at`, and firing the
`queue_completed` daily stat. This is idempotent and safe to poll
repeatedly. It intentionally does **not** create a new session just
because customers still exist in the database — see the code comment in
`get_current_session()` for the specific bug this avoids (re-polling a
completed queue would otherwise spawn a fresh session every time).

## Telegram Mini App launch

- `MINI_APP_URL` env var (must be `https://`) — if set, the bot's
  persistent menu button becomes a "Open App" Web App button
  (`bot.py::_post_init`), and `/app` sends an inline Web App button too.
  If unset, both fall back to the normal command menu / a text message
  telling the operator it isn't configured yet — nothing crashes either way.
- No frontend exists at that URL yet. This is prep work only, per the brief.

## Areas that will move from Telegram chat into the Mini App

Marked here, left fully functional in Telegram for now — nothing removed:

- `queue_ui.py`'s inline-keyboard call actions (Contacted / Didn't Answer
  / Wrong Number / Skip / Delete) — functionally duplicated by
  `/call/result`, `/note` in the Mini App. Telegram's buttons stay as
  the fallback/secondary surface.
- `stats_ui.py`'s `/stats`, `/session` — duplicated by `/statistics`,
  `/session/current`.
- `admin_commands.py`'s `/export` — duplicated by `GET /export`, both
  now gated by the same shared `security.is_admin()` rule (see
  `ARCHITECTURE.md`). Telegram's stays the authorization-checked
  fallback surface, same as the others above.

## Known gaps / not done in this pass

- **CORS is wide open** (`Access-Control-Allow-Origin: *`) on every
  response. Fine for local development, should be restricted to the
  real Mini App origin once one exists.
- **No `POST /queue/resume`** (see above).
- Full list of related but out-of-scope items: see `BACKLOG.md`.
