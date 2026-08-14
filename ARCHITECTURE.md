# ARCHITECTURE.md

Technical reference for the FreikerDialBot Automation codebase.

This file replaces the old split between a general architecture note and a separate Mini App API note. It describes how the pieces fit together and which layer owns which responsibility.

## High-level architecture

FreikerDialBot Automation is a Telegram-first debt-collection calling workflow with a shared Python backend and a React/TypeScript Mini App.

The important rule is that the Telegram bot and the Mini App share the same business logic and data model. The frontend surfaces are different, but the queue, session, statistics, import, search, edit, and security rules stay shared.

```text
Telegram client
├─ Telegram bot UI
└─ Telegram Mini App
      └─ Mini App HTTP API
            └─ Shared backend services
                  ├─ Database
                  ├─ QueueEngine
                  ├─ SessionManager
                  ├─ StatisticsEngine
                  ├─ Importer / AI parser / validation
                  └─ Security / auth helpers
```

## Main layers

### Shared backend

- `backend.py` is the shared wiring point.
- `database.py` owns SQLite persistence and migrations.
- `queue_engine.py` owns queue order, customer actions, blacklisting, and deterministic transitions.
- `session_manager.py` owns session lifecycle.
- `statistics_engine.py` owns session and customer statistics.
- `importer.py`, `ai_parser.py`, and `validation.py` own the import pipeline.

### Telegram bot

- `bot.py` is the Telegram entrypoint.
- `telegram_ui.py`, `queue_ui.py`, `stats_ui.py`, `customer_ui.py`, and `admin_commands.py` render the Telegram experience and call the shared backend.
- `telegram_formatting.py` is the centralized Telegram presentation layer: every user-facing message is built there (HTML, escaped) so formatting is not scattered through business logic. Business modules (e.g. `statistics_engine.render_statistics`) delegate their render methods to it.
- Telegram-side admin actions use the shared security rules.

### Mini App

- `mini_app_api.py` is an HTTP adapter, not a second backend.
- It translates HTTP requests into calls on the shared backend.
- The React/TypeScript app in `frontend/` is presentation only.
- The Mini App does not reimplement queue, session, or statistics logic in the frontend.

## Mini App API contract

The Mini App API exposes the same backend state to the web UI.

### Authentication and authorization

- Real Mini App requests use Telegram `initData` validation.
- The header format is `Authorization: tma <initData>`.
- `telegram_auth.py` validates the Telegram payload.
- `security.py` owns the shared admin check.
- `MINI_APP_ALLOW_ANONYMOUS=1` is a development-only escape hatch and should stay off outside local testing.
- Real API routes are listed in `_API_PATHS`; `/` and static assets stay open so the frontend can load before it has credentials.
- `mini_app_api.py` also accepts `/api/*` as an alias for the same route set.
- At the transport layer, `start_mini_app.py` applies `oauth.yml` (ngrok OAuth traffic policy, provider `google`) to the tunnel by default via `--traffic-policy-file`, so visitors must pass provider OAuth before any request reaches the API. `NGROK_TRAFFIC_POLICY_FILE=none` disables the gate.

### Current route groups

The API is organized around the same responsibilities as the backend. The current route set includes:

- `GET /session/current`
- `GET /customer/current`
- `GET /statistics`
- `POST /session/next`
- `POST /call/start`
- `POST /call/result`
- `POST /note`
- `POST /queue/pause`
- `POST /queue/resume`
- `POST /queue/call-back`
- `GET /queue/upcoming`
- `GET /customer/search`
- `GET /customer/record`
- `POST /customer/edit`
- `POST /customer/blacklist`
- `POST /phone/blacklist`
- `GET/POST /settings`
- `POST /import`
- `GET /export`

`/import` is not admin-gated (it mirrors the Telegram bot's own upload handlers); `/export` is the only admin-gated route. There is no `POST /call/return` route in the current code.

`GET /queue/upcoming` takes an optional `?count=N` query param. Omitted, it returns a single upcoming-customer object exactly as before (backward compatible). With `count`, it returns `{"upcoming": [...]}`, a list of up to `N` upcoming customers using the same deterministic ordering/blacklist-skipping as the single-customer form. This backs Settings > Queue > Pre-ready Count -- the frontend decides how many to request based on that setting; the backend does not maintain a second queue or selection rule for it.

`GET/POST /settings` also covers `primaryPhonePreference` (`"first"` | `"second"`, default `"first"`) and `preReadyCount` (`0`-`3`, default `0`). `primaryPhonePreference` reorders which stored phone number `_customer_payload` tries first when picking the auto-display/dial number, falling back through the rest (including skipping blacklisted numbers) exactly as before.

`visibleFields` (list of `"daysOverdue"` | `"monthlyPayment"` | `"balance"`, default `["daysOverdue", "monthlyPayment"]`) controls which financial fields `CustomerCard`'s info grid renders. Always stored/returned pre-ordered to the fixed `_VISIBLE_FIELD_IDS` display order regardless of what order the client sent, so frontend and backend can't drift into disagreeing about field order.

### Ownership rules

- The queue engine decides who is next.
- The session manager decides whether a session is active, paused, or complete.
- The statistics engine owns the reporting calculations.
- The database owns persistence.
- The Mini App API only adapts those services to HTTP.

## Design boundaries

Keep these boundaries stable:

- Do not duplicate queue rules between the bot and the Mini App.
- Do not duplicate auth logic between endpoints.
- Do not reassemble customer history independently in each frontend.
- Do not move business rules into the React app.
- Do not create a second import pipeline for the Mini App.

## Current architectural notes

- The Telegram bot and Mini App stay interchangeable frontends over the same data.
- The UI can change independently of the backend.
- New features should be added once in the shared backend and then surfaced to each frontend.
- If a new route or UI surface is added, it should call the shared service instead of reimplementing the rule.

## What belongs here versus elsewhere

- `AGENTS.md` — rules and working conventions.
- `PROJECT_STATUS.md` — current snapshot, open work, and user-facing decision points.
- `ARCHITECTURE.md` — system structure and API ownership.
- `SECURITY_AUDIT_REPORT.md` — security findings and risk posture.
- `README.md` — user-facing setup and overview.

If this file starts turning into a backlog or a status log, move that material back into `PROJECT_STATUS.md` instead.
