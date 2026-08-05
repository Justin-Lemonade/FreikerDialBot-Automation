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
- The repository docs are now centered on `AGENTS.md`, `PROJECT_STATUS.md`, `ARCHITECTURE.md`, `SECURITY_AUDIT_REPORT.md`, and `README.md`.

## What was folded into this file from older docs

- The old backlog file is now represented here as the open-issues list below.
- The old setup-after-Claude notes are now represented here as the security/setup recap below.
- The old delegation/task notes were not needed once the priority pass was completed, so they were removed instead of being kept as another parallel Markdown file.

## Security and setup recap

- The data-history remediation pass was completed earlier and should stay treated as a completed decision, not a live task.
- Mini App auth is mandatory by default on real endpoints.
- `bot.py` is the single entry point for the stack when the Mini App is enabled.
- The launcher flag typo was fixed in the earlier setup pass.
- The dependabot configuration exists and should stay on the repo maintenance path.

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