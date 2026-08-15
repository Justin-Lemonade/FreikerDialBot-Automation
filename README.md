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
- Node.js LTS (frontend dependencies are required even to run the bot --
  `python bot.py` builds the Mini App frontend itself on startup)
- A Telegram bot token
- At least one AI provider key if you want screenshot OCR

### Quick start (one command)

```bash
./setup.sh          # macOS/Linux
# or
.\setup.ps1          # Windows PowerShell
```

This creates a virtual environment, installs backend and frontend
dependencies, and copies `.env.example` to `.env` (root and `frontend/`)
if they don't already exist. It's safe to re-run at any time.

Then:

1. Edit `.env` and set `TELEGRAM_BOT_TOKEN` (get one from
   [@BotFather](https://t.me/BotFather)).
2. Activate the virtual environment: `source .venv/bin/activate`
   (or `.venv\Scripts\Activate.ps1` on Windows).
3. Verify the environment: `python doctor.py` -- checks Python/Node
   versions, installed dependencies, `.env` contents, database
   accessibility, and more, with a remediation step for anything
   that's wrong.
4. Start the bot: `python bot.py` -- this single command builds the
   frontend, starts the Mini App API, opens an ngrok tunnel if ngrok is
   installed, and starts the Telegram bot. There is no separate
   frontend server to run in normal development.

The ngrok tunnel is edge-authenticated by default: `start_mini_app.py`
applies the `oauth.yml` traffic policy (Google OAuth), so every visitor
must sign in before the Mini App loads. Set `NGROK_TRAFFIC_POLICY_FILE=none`
to disable the gate, or edit `oauth.yml` (e.g. to restrict by email).

### Manual setup

If you'd rather not use the setup script:

```bash
python3 -m venv .venv
source .venv/bin/activate          # .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
cd frontend && npm ci && cd ..
cp .env.example .env               # then fill in TELEGRAM_BOT_TOKEN
python doctor.py                   # optional but recommended sanity check
python bot.py
```

### Frontend-only development

If you're iterating on the UI and don't want a live bot connected, run
the Mini App stack (frontend build + backend API + ngrok) without the
bot:

```bash
python start_mini_app.py
```

For frontend lint/typecheck/build in isolation (e.g. before opening a
PR):

```bash
cd frontend
npm ci
npm run test
npx tsc -b --noEmit
npm run build
```

## Documentation

- `AGENTS.md` — rules and working conventions.
- `ARCHITECTURE.md` — technical architecture and Mini App API contract.
- `PROJECT_STATUS.md` — current snapshot, open issues, and owner decisions.
- `SECURITY_AUDIT_REPORT.md` — security findings and current security posture.

This README is the single source for setup instructions -- other docs
link back here rather than repeating install steps.

## Repository layout

- `bot.py` — Telegram entrypoint; also the single command that starts the whole stack.
- `start_mini_app.py` — Mini App stack only (frontend build + backend API + ngrok), no bot.
- `setup.sh` / `setup.ps1` — one-command environment setup.
- `doctor.py` — environment diagnostic; run before startup to catch setup problems early.
- `backend.py` — shared backend construction.
- `database.py`, `queue_engine.py`, `session_manager.py`, `statistics_engine.py` — queue and data logic.
- `importer.py`, `ai_parser.py`, `validation.py` — import pipeline.
- `telegram_ui.py`, `queue_ui.py`, `stats_ui.py`, `customer_ui.py`, `admin_commands.py` — Telegram UI.
- `mini_app_api.py`, `telegram_auth.py`, `security.py` — Mini App API and security.
- `frontend/` — React/TypeScript/Vite Mini App.
- `tests/` — automated tests.
