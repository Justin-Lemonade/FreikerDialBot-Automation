# AGENTS.md

FreikerDialBot Automation is a Telegram-first debt-collection calling queue with a shared Python backend and a React/TypeScript Mini App.

## Canonical Markdown files

Keep the repository documentation to these three files:

- `AGENTS.md` — rules and working conventions for agents.
- `PROJECT_STATUS.md` — current snapshot of what is built, what is open, and what to check next.
- `README.md` — user-facing overview, setup, and quick start.

Do not add more Markdown unless you are replacing one of these files or a tool requires a separate filename.

## Source of truth

- GitHub repository contents are authoritative.
- Verify live code before claiming a function, endpoint, or feature exists.
- Documentation describes intent; code determines fact.

## Working rules

- Keep changes small and reversible.
- Do not invent business logic to fill a doc gap.
- Do not duplicate instructions across multiple Markdown files.
- Keep runtime `data/` content and generated frontend artifacts out of the repo.
- Do not edit third-party dependencies or generated files.
- Prefer the smallest correct change.

## Main code areas

- `bot.py` — Telegram entrypoint.
- `start_mini_app.py` — builds the frontend, starts the Mini App backend, and optionally opens ngrok.
- `backend.py` — shared service construction.
- `database.py`, `queue_engine.py`, `session_manager.py`, `statistics_engine.py` — data, queue, session, and stats logic.
- `importer.py`, `ai_parser.py`, `validation.py` — import pipeline.
- `telegram_ui.py`, `queue_ui.py`, `stats_ui.py`, `customer_ui.py`, `admin_commands.py` — Telegram UI and admin flows.
- `mini_app_api.py`, `telegram_auth.py`, `security.py` — Mini App API, auth, and authorization.
- `frontend/` — React/TypeScript/Vite Mini App.
- `tests/` — automated tests.

## Validation before merge

1. Backend tests: `pytest tests/ -q`
2. Frontend checks: `cd frontend && npm ci && npx tsc -b --noEmit && npm run build`
3. Check `git status` and review the diff.
4. Confirm no secrets or runtime data are staged.

## Documentation rules

- If a document becomes stale, consolidate the live information into `PROJECT_STATUS.md` or `README.md` and remove the duplicate file.
- If a rule changes, update `AGENTS.md` first.
- If current state changes, update `PROJECT_STATUS.md`.
- If user-facing setup or overview changes, update `README.md`.

## Modification rules

- Do not create temporary note files or parallel instruction files.
- Do not modify runtime data under `data/` unless a task explicitly requires it.
- Do not hand-edit generated frontend output.
- Do not commit `.pytest_cache/`, `frontend/dist/`, or `frontend/node_modules/`.

## What to preserve

- The shared backend architecture.
- The deterministic queue and single source of customer state.
- The Telegram Mini App and Telegram bot sharing the same backend.
- The rule that docs must match live code, not assumptions.