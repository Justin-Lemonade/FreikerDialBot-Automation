# PROJECT_STATUS.md

Current snapshot of the repository as of the current main tree.

For rules and working conventions, read `AGENTS.md`.
For the user-facing overview, read `README.md`.

## What is already in the repo

- Shared backend wiring exists in `backend.py`.
- The Telegram bot, queue, session, statistics, importer, and Mini App API all share the same core data model.
- The importer pipeline covers screenshots, pasted text, JSON, and spreadsheet input.
- The queue supports deterministic next-customer selection, editing, blacklists, search, history, and admin actions.
- The Mini App frontend is a real React/TypeScript/Vite app, not a stub.
- Telegram Mini App authentication and admin authorization logic are implemented in the repo.
- The repository docs have been consolidated around `AGENTS.md`, `PROJECT_STATUS.md`, and `README.md`.

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

## What to check next

1. Re-run the backend test suite.
2. Run the frontend typecheck and build.
3. Pick the next item from the open list above.
4. Keep future documentation inside the three canonical Markdown files unless a tool explicitly requires another filename.