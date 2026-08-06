# PROJECT_STATUS.md

Current snapshot of the repository as of the current main tree.

For rules and working conventions, read `AGENTS.md`.
For technical architecture and endpoint details, read `ARCHITECTURE.md`.
For security findings, read `SECURITY_AUDIT_REPORT.md`.
For user-facing overview and setup, read `README.md`.

## What is already in the repo

- Shared backend wiring exists in `backend.py`.
- The Telegram bot, queue, session, statistics, importer, and Mini App API all share the same core data model.
- The importer pipeline covers screenshots, pasted text, JSON, and spreadsheet input.
- The queue supports deterministic next-customer selection, editing, blacklists, search, history, and admin actions.
- The Mini App frontend is a real React/TypeScript/Vite app, not a stub.
- Telegram Mini App authentication and admin authorization logic are implemented in the repo.
- The repository docs are centered on `AGENTS.md`, `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `SECURITY_AUDIT_REPORT.md`, and `README.md`.

## What was folded into this file from older docs

- The old backlog file is now represented here as the open-issues list below.
- The old setup-after-Claude notes are now represented here as the security/setup recap below.
- The old delegation/task notes were removed as a separate file and folded back into this file as a reusable delegation section.

## Security and setup recap

- The data-history remediation decision is already completed and should stay treated as a completed decision, not a live task.
- Mini App auth is mandatory by default on real endpoints.
- `bot.py` is the single entry point for the stack when the Mini App is enabled.
- The launcher flag typo was fixed in the earlier setup pass.
- The dependabot configuration exists and should stay on the repo maintenance path.
- The Mini App API is still the thin adapter around the shared backend services, not a separate backend.

## Delegated work / ready-to-delegate tasks

Use this section for bounded implementation specs that can be handed to a weaker model without losing context.

What belongs here:
- tasks with a clear scope and a clear stop condition;
- work that can be verified with tests, builds, or a diff review;
- implementation tasks that do not require a product decision first;
- task specs that would otherwise get lost in a separate Markdown file.

How to use it:
- keep each item short and specific;
- name the preferred model when delegation matters;
- list the files that may change and the files that must not change;
- state the exact outcome expected;
- include the verification command or test that must pass;
- move anything that needs product judgment, security judgment, or architectural redesign into `PROJECT_STATUS.md`'s decision or open-issues sections instead.

### Ready to delegate

#### 1. Restrict CORS to the real Mini App origin

- Why: `Access-Control-Allow-Origin: *` is still wide open on Mini App responses.
- Scope: `mini_app_api.py` only, plus focused tests.
- Goal: use the resolved Mini App origin instead of `*` and keep local development workable.
- Verification: add a test that asserts the header matches the configured origin and does not fall back to `*`.

#### 2. Audit-log denied admin attempts

- Why: successful admin actions are logged, but denied attempts are still invisible.
- Scope: `admin_commands.py`, `mini_app_api.py`, and focused tests.
- Goal: record an explicit denial event when admin access is rejected, without changing successful-action logging.
- Verification: confirm both a rejected Telegram admin command and a rejected Mini App export create the denial record.

#### 3. Add `POST /queue/resume` to the Mini App API

- Why: `QueueEngine.resume()` already exists, but the Mini App has no route that exposes it.
- Scope: `mini_app_api.py`, `frontend/` API call site(s), and tests.
- Goal: expose queue resume as a real Mini App route and keep it under the same auth rules as the other real endpoints.
- Verification: the route works when authenticated and returns 401 without auth.

### Not delegated yet

These need a product decision first, so they should stay out of the ready-to-delegate list until the rule is chosen deliberately.

- **Paid write path:** decide whether it should exist in both Telegram and the Mini App, or remain disabled until the workflow is defined.
- **Fully blacklisted customers:** decide whether queue eligibility should treat them as uncallable or leave the current behavior unchanged.
- **Session timing:** decide whether to keep wall-clock timing or move to an idle-aware model.

## What is currently open

- CORS is still wide open and should be restricted to the real Mini App origin.
- Denied admin attempts are not yet audit-logged.
- `POST /queue/resume` is still not wired into the Mini App API even though the queue engine already has resume logic.
- The Mini App still has no import flow of its own; importing remains Telegram-only.
- Frontend test coverage is still sparse or absent compared with the backend tests.

## Decisions still needed

These are product decisions, not simple bugs:

- The real `Paid` write path and whether it should exist in both Telegram and the Mini App.
- What should happen to customers whose every phone number is blacklisted.
- Whether session duration should stay as wall-clock time or become idle-aware.

## User-facing prompts / options

If the next pass is meant to answer open product questions, the shortest choices are:

- **Paid:** add a real write path now, or keep it disabled until the workflow is defined.
- **Blacklist-by-phone:** keep it separate from customer-level blacklisting, or redefine queue eligibility to treat fully blacklisted customers as uncallable.
- **Session timing:** keep the current wall-clock measurement, or move to an idle-aware model.

## What to check next

1. Re-run the backend test suite.
2. Run the frontend typecheck and build.
3. Pick the next item from the open list above.
4. Keep future documentation inside the canonical Markdown files unless a tool explicitly requires another filename.
