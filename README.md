# FreikerDialBot Automation

FreikerDialBot Automation is a Telegram-first debt-collection calling workflow with a shared Python backend and a React/TypeScript Mini App.

## What it does

- Imports customer data from screenshots, pasted text, JSON, and Excel.
- Normalizes, validates, deduplicates, and stores customers in SQLite.
- Runs a deterministic calling queue with call outcomes, editing, search, blacklists, history, sessions, and statistics.
- Exposes the same backend through the Telegram bot and the Mini App.

## Setup

### Requirements

- Python 3.12+
- Node.js LTS for frontend development
- A Telegram bot token
- At least one AI provider key if you want screenshot OCR

### Backend

```bash
pip install -r requirements.txt
python bot.py
```

### Frontend development

```bash
cd frontend
npm ci
npx tsc -b --noEmit
npm run build
```

## Documentation

- `AGENTS.md` — rules and working conventions.
- `PROJECT_STATUS.md` — current snapshot of what is built and what remains open.

## Repository layout

- `bot.py` — Telegram entrypoint.
- `backend.py` — shared backend construction.
- `database.py`, `queue_engine.py`, `session_manager.py`, `statistics_engine.py` — queue and data logic.
- `importer.py`, `ai_parser.py`, `validation.py` — import pipeline.
- `telegram_ui.py`, `queue_ui.py`, `stats_ui.py`, `customer_ui.py`, `admin_commands.py` — Telegram UI.
- `mini_app_api.py`, `telegram_auth.py`, `security.py` — Mini App API and security.
- `frontend/` — React/TypeScript/Vite Mini App.
- `tests/` — automated tests.