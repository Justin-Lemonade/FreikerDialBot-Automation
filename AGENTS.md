# AGENTS.md

Last verified against commit: f2e6acc5c5dd6e227d77fa4196f2cc7ac0906b7c
Last updated: 2026-07-23

This is the canonical instruction file for AI coding agents (Claude, Gemini,
Copilot, or others) working on this repository. If other agent-instruction
files exist (`GEMINI.md`, `.github/copilot-instructions.md`, etc.), they
point back here rather than duplicating this content — see "Instruction
file hierarchy" below.

## What this project is

FreikerDialBot Automation: a Telegram bot that turns a list of overdue-loan
customers into a calling queue. An operator works through customers one at
a time (Contacted / Didn't Answer / Wrong Number / Skip / Paid), the bot
tracks progress and statistics, and a Telegram Mini App gives the same
workflow a proper mobile UI instead of chat buttons.

## Architecture

- `bot.py` — Telegram bot entry point, registers all commands/handlers.
- `database.py` — SQLite storage: customers, sessions, events, blacklist.
- `queue_engine.py` — deterministic queue: who's next, status transitions, audit events.
- `session_manager.py` / `statistics_engine.py` — session lifecycle + daily/lifetime stats.
- `customer_ui.py` / `queue_ui.py` / `stats_ui.py` / `telegram_ui.py` — Telegram-side rendering and command handlers.
- `admin_commands.py` / `security.py` — authorization-gated admin actions (reset/clear/export).
- `mini_app_api.py` + `telegram_auth.py` — HTTP API + Telegram initData auth for the Mini App.
- `backend.py` — shared construction (`build_backend()`) so `bot.py` and `mini_app_api.py` don't duplicate wiring.
- `frontend/` — Telegram Mini App UI (React/TypeScript/Vite). **Built and typechecks clean**, but has no automated test coverage of its own yet.
- Tests live in `tests/` as `test_*.py`, run with `pytest`.

## Repository structure

```
/                    Python backend (root package, no src/ layout)
tests/               All backend tests
frontend/             React/TS Mini App
frontend/src/         App.tsx, api/, hooks/, layout/, pages/, components/
data/                 Local runtime data — see "Known issues" below
```

## Source-of-truth rule

**GitHub is the source of truth.** Not this file, not `ARCHITECTURE.md`,
not `BACKLOG.md`, not any previous session's summary. Pull `main` fresh at
the start of a session rather than trusting local/previous-session state.

## THE RULE

**Before claiming a function, endpoint, file, or feature exists, grep the
actual file. Do not trust ARCHITECTURE.md / BACKLOG.md / MINI_APP_API.md
claims without verifying against live code.**

This codebase has repeatedly had documentation describe work as "done"
that wasn't present in the actual files (confirmed multiple times — see
"Known documentation drift" below). Docs describe *intent*, not *fact*.
Verify, then act.

## Known documentation drift

- `set_active_customer` was referenced as implemented in `ARCHITECTURE.md`,
  `BACKLOG.md`, and `MINI_APP_API.md` but **does not exist** in
  `queue_engine.py`. Confirmed via direct grep, commit `f2e6acc`.
  `start_call`'s explicit-customer-id path already achieves the same
  result by calling `database.update_queue_session()` directly — no
  missing functionality, just a false doc claim. Corrected in this pass.
- `POST /call/return` was documented as implemented but **does not exist**
  as a route in `mini_app_api.py`. Corrected in this pass.
- If you find another instance of this pattern, fix the doc, don't invent
  code to match it, unless the current architecture genuinely needs the
  behavior (verify with tests, not with doc claims).

## Current project phase

Backend Mini App API and frontend are both built and wired together
(`frontend/src` is real, not scaffold — confirmed by a clean `tsc -b`
typecheck and a successful `vite build`). Full list of what's done vs.
open: see `BACKLOG.md`. Recent focus has been developer-workflow
infrastructure (this file, CI, doc reconciliation) rather than new
features — see `PROJECT_STATUS.md` for exactly where things stand.

## Instruction file hierarchy

- **`AGENTS.md` (this file)** — canonical, agent-agnostic. Read this first.
- `GEMINI.md` (root and `frontend/`) — Gemini-specific conventions/commands
  predating this file. Points here for architecture; keep Gemini-specific
  workflow notes there rather than merging everything into one file.
- No `CLAUDE.md` or `.github/copilot-instructions.md` exist. Not needed:
  this file covers what either would, and duplicating instructions across
  multiple files is how the doc-drift problem above happened in the first
  place. Add one only if a tool requires its own filename to be read at
  all (verify that before creating it).

## How to run backend tests

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="123456:test-token"
export OPENAI_API_KEY="sk-test"
pytest tests/ -q
```

Current status: 251 passed, 0 failed (verified against commit `f2e6acc`).

**Side effect to watch for:** running the suite modifies `data/bot.log`
(a tracked file the logger writes to). Run `git checkout -- data/bot.log`
afterward if you're not intentionally changing logging behavior — do not
commit that diff.

## How to run frontend checks

```bash
cd frontend
npm ci            # NOT `npm install` — ci respects the lockfile exactly
                   # and won't cause lockfile drift from a different
                   # local npm version (confirmed: npm install does
                   # regenerate metadata in package-lock.json; npm ci
                   # does not touch it)
npx tsc -b --noEmit   # typecheck
npm run build         # production build validation
```

Current status: typecheck clean, build succeeds (verified against commit
`f2e6acc`). No frontend test suite exists yet.

## Full validation suite (run before any push)

1. Backend tests (above).
2. Frontend typecheck + build (above).
3. `git status` / `git diff` — confirm no unintended files (see "Rules for
   side effects" below).
4. Confirm no secrets in the diff.

## Environment requirements

- Python 3.12+ (no `.python-version` pin currently; README states 3.12).
- Node.js — no engine pin in `frontend/package.json`; use a current LTS.
- `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` (or a dummy value) required
  just to import `config.py` / run tests — see example above.

## Rules for database/test side effects

- `data/bot.log` gets modified by running the backend test suite locally
  (confirmed, reproducible). Discard this with `git checkout -- data/bot.log`
  before committing unless the logging change is intentional.
- `frontend/package-lock.json` can drift from `npm install` on a different
  npm version. Use `npm ci` for anything read-only; if you need to add a
  dependency, regenerate deliberately with `npm install <pkg>` and review
  the resulting diff before committing.
- Never commit `frontend/dist/`, `frontend/node_modules/`, `.pytest_cache/`,
  or anything under `data/` — all are gitignored; verify `git status` is
  clean of them before committing regardless.

## Rules for modifying production code

- Don't invent new business logic (e.g. a real "Paid" flow, new statistics
  buckets) to fill a gap implied by documentation — flag it in
  `BACKLOG.md` instead and ask.
- Prefer the smallest correct change. Don't refactor unrelated code while
  fixing something else.
- Frontend and backend are separate processes on separate ports
  (`mini_app_api.py` on :8000, Vite dev server on :5173) — don't assume
  same-origin requests will work without `VITE_API_BASE_URL` being set
  correctly (see `frontend/.env.example`).

## Rules for documentation

- Keep documentation concise. Don't add a new `.md` file if an existing
  one can be extended.
- A doc claiming a function/endpoint "✅ implemented" must be re-verified
  against the actual file before you rely on it, every time — see THE RULE.
- If you find doc/code drift, fix the doc unless the architecture
  genuinely needs the missing behavior — verify with tests, not vibes.

## Rules for commits, pushes, and remote verification

- Never claim a change was pushed unless `git push` actually ran and you
  independently re-verified the remote (e.g. via `gh api` or the GitHub
  web UI) — not just trusting the local push command's exit code.
- Never claim CI passed unless you actually checked the Actions run result.
- Don't push directly to `main` for anything beyond small, low-risk
  changes (docs, CI config, this file) without saying so first. For
  feature work, prefer a branch + PR so there's a review point — ask if
  unsure which this is.

## What not to modify unnecessarily

- `python-telegram-bot` internals — this is a third-party dependency, not
  project code, even where it appears vendored/flattened in some tooling.
- `data/` contents — see `PROJECT_STATUS.md` / `SETUP_AFTER_CLAUDE.md` for
  the known issue of tracked files under this directory.
- Anything under `frontend/node_modules` or `frontend/dist` — generated,
  gitignored, never hand-edited.

## Where to find more

- `BACKLOG.md` — what's done, what's open, organized by category.
- `PROJECT_STATUS.md` — quick current-state answers for a new session
  (what's complete, what's next, last verified commit/test count).
- `ARCHITECTURE.md` — deeper design rationale for specific past decisions.
- `MINI_APP_API.md` — the Mini App HTTP API contract.
