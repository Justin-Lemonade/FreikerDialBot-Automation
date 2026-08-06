#!/usr/bin/env bash
# One-command setup for FreikerDialBot Automation (Linux/macOS).
#
# What this does, in order:
#   1. Verify Python 3.12+ and Node.js are available.
#   2. Create a virtual environment (.venv) if one doesn't exist.
#   3. Install backend dependencies into it.
#   4. Install frontend dependencies (npm ci).
#   5. Copy .env.example -> .env (root and frontend) if missing.
#
# After this finishes: fill in TELEGRAM_BOT_TOKEN in .env, then run
#   python doctor.py   (verify everything is actually ready)
#   python bot.py       (start the bot + Mini App stack)
#
# Safe to re-run: every step is idempotent (skips work that's already done).

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

log() { printf '[setup] %s\n' "$1"; }
fail() { printf '[setup] ERROR: %s\n' "$1" >&2; exit 1; }

# ── Python ───────────────────────────────────────────────────────────
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "python3 not found. Install Python 3.12+ from https://www.python.org/downloads/."

PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_OK="$("$PYTHON_BIN" -c 'import sys; print(1 if sys.version_info[:2] >= (3, 12) else 0)')"
if [ "$PY_OK" != "1" ]; then
    fail "Python $PY_VERSION found, but 3.12+ is required."
fi
log "Python $PY_VERSION OK"

# ── Virtual environment ─────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    log "Creating virtual environment at .venv ..."
    "$PYTHON_BIN" -m venv .venv
else
    log "Virtual environment .venv already exists, reusing it."
fi

VENV_PY=".venv/bin/python"
VENV_PIP=".venv/bin/pip"

# ── Backend dependencies ────────────────────────────────────────────
log "Installing backend dependencies (this can take a minute)..."
"$VENV_PIP" install --quiet --upgrade pip
"$VENV_PIP" install --quiet -r requirements.txt
log "Backend dependencies installed."

# ── Node / npm ───────────────────────────────────────────────────────
command -v node >/dev/null 2>&1 || fail "Node.js not found. Install a Node LTS release from https://nodejs.org/."
command -v npm >/dev/null 2>&1 || fail "npm not found (should ship with Node.js)."
log "Node $(node --version) / npm $(npm --version) OK"

# ── Frontend dependencies ───────────────────────────────────────────
log "Installing frontend dependencies (npm ci)..."
(cd frontend && npm ci --silent)
log "Frontend dependencies installed."

# ── .env files ───────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    log "Created .env from .env.example -- fill in TELEGRAM_BOT_TOKEN before running the bot."
else
    log ".env already exists, leaving it untouched."
fi

if [ ! -f "frontend/.env" ]; then
    cp frontend/.env.example frontend/.env
    log "Created frontend/.env from frontend/.env.example."
else
    log "frontend/.env already exists, leaving it untouched."
fi

echo
log "Setup complete. Next steps:"
log "  1. Edit .env and set TELEGRAM_BOT_TOKEN (get one from @BotFather)."
log "  2. Activate the virtual environment: source .venv/bin/activate"
log "  3. Verify everything: python doctor.py"
log "  4. Start the bot: python bot.py"
