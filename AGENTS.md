# AGENTS.md

FreikerDialBot Automation is a Telegram-first debt-collection calling queue with a shared Python backend and a React/TypeScript Mini App.

## Canonical Markdown files

Keep the repository documentation to these files:

- `AGENTS.md` — rules and working conventions for agents.
- `PROJECT_STATUS.md` — current snapshot, open issues, decisions, and recaps of completed passes.
- `ARCHITECTURE.md` — technical architecture and Mini App API contract.
- `SECURITY_AUDIT_REPORT.md` — security findings and current security posture.
- `README.md` — user-facing overview and setup.

Do not add other Markdown files unless you are replacing one of the files above or a tool explicitly requires a separate filename.
Do not recreate legacy note files such as `BACKLOG.md`, `DELEGATION_TASKS.md`, `GEMINI.md`, `MINI_APP_API.md`, or `SETUP_AFTER_CLAUDE.md`.

## When code, uploads, or repo state change

Whenever you review new code, a fresh repo push, or uploaded notes/files, first decide whether any canonical doc needs an update.

Use this rule of thumb:

- Update `AGENTS.md` if rules, workflow, validation, or doc-handling policy changes.
- Update `PROJECT_STATUS.md` if current state, open issues, next steps, or owner decisions change.
- Update `ARCHITECTURE.md` if module boundaries, API routes, auth, or ownership change.
- Update `SECURITY_AUDIT_REPORT.md` if the security posture, exposure surface, or audit findings change.
- Update `README.md` if setup, usage, or the user-facing overview changes.

Before creating a new Markdown file, first try folding the material into one of the canonical docs. Create a new file only if a tool or durable separation really requires it.
Treat `SECURITY_AUDIT_REPORT.md` as a security snapshot, not as an instruction file. Use it when working on security; otherwise prefer `AGENTS.md` and `PROJECT_STATUS.md`.

## Source of truth

- GitHub repository contents are authoritative.
- Verify live code before claiming a function, endpoint, file, or feature exists.
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
- `setup.sh` / `setup.ps1` — one-command environment setup (venv, backend deps, frontend deps, `.env` scaffolding). Idempotent -- safe to re-run.
- `doctor.py` — environment diagnostic; verifies toolchain, dependencies, `.env`, and database accessibility before startup. Run it whenever setup behavior changes to keep its checks accurate.
- `backend.py` — shared service construction.
- `database.py`, `queue_engine.py`, `session_manager.py`, `statistics_engine.py` — data, queue, session, and stats logic.
- `importer.py`, `ai_parser.py`, `validation.py` — import pipeline.
- `telegram_ui.py`, `queue_ui.py`, `stats_ui.py`, `customer_ui.py`, `admin_commands.py` — Telegram UI and admin flows.
- `mini_app_api.py`, `telegram_auth.py`, `security.py` — Mini App API, auth, and authorization.
- `frontend/` — React/TypeScript/Vite Mini App.
- `tests/` — automated tests.

## Frontend working notes

- The frontend is React/TypeScript/Vite.
- Use `cd frontend && npm ci && npx tsc -b --noEmit && npm run build` before merge.
- Prefer mobile-first UI changes and reuse existing components when possible.
- Keep `VITE_API_BASE_URL` aligned with the actual deployment path in `frontend/.env.example`.

## Validation before merge

1. Backend tests: `pytest tests/ -q`
2. Frontend checks: `cd frontend && npm ci && npx tsc -b --noEmit && npm run build`
3. If setup/startup behavior changed: `python doctor.py` and a fresh-clone run of `setup.sh` (or `setup.ps1`) followed by `python bot.py`.
4. Check `git status` and review the diff.
5. Confirm no secrets or runtime data are staged.

## Commit and push cadence

- Keep commits small and focused: one logical change per commit, with a message that says what changed and why.
- Do not leave a long session uncommitted. If you have made several related, validated changes, commit them before starting unrelated work.
- Push after a few related commits, or at a safe stopping point where the tree is validated (tests, typecheck, build) and reviewed (`git diff`).
- Always review the diff before pushing.
- Verify a push actually landed by checking the commit on GitHub (e.g. via the GitHub API), not just by trusting the `git push` exit code -- the repo may have moved since the local clone was made.

## Documentation rules

- Keep rules in `AGENTS.md`.
- Keep the current snapshot, user-facing options, and open decisions in `PROJECT_STATUS.md`.
- Keep technical architecture and endpoint contracts in `ARCHITECTURE.md`.
- Keep security findings and current risk posture in `SECURITY_AUDIT_REPORT.md`.
- Keep user-facing overview and setup in `README.md`.
- If a document becomes stale, consolidate the live information into the right file and remove the duplicate file.
- If a rule changes, update `AGENTS.md` first.

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
