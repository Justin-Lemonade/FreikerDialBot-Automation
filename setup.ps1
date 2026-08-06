# One-command setup for FreikerDialBot Automation (Windows / PowerShell).
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
#
# This replaces the old feikerApp.ps1, which was just a one-line
# `python bot.py` wrapper that did no setup of its own -- an
# undocumented, unreferenced duplicate of the documented startup
# command. `python bot.py` remains the actual way to run the app;
# this script only handles getting the environment ready for it.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Write-Log($Message) {
    Write-Host "[setup] $Message"
}

function Fail($Message) {
    Write-Error "[setup] ERROR: $Message"
    exit 1
}

# ── Python ───────────────────────────────────────────────────────────
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Fail "python not found. Install Python 3.12+ from https://www.python.org/downloads/."
}

$pyVersion = (python -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
$pyOk = (python -c "import sys; print(1 if sys.version_info[:2] >= (3, 12) else 0)").Trim()
if ($pyOk -ne "1") {
    Fail "Python $pyVersion found, but 3.12+ is required."
}
Write-Log "Python $pyVersion OK"

# ── Virtual environment ─────────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Log "Creating virtual environment at .venv ..."
    python -m venv .venv
} else {
    Write-Log "Virtual environment .venv already exists, reusing it."
}

$venvPython = ".venv\Scripts\python.exe"
$venvPip = ".venv\Scripts\pip.exe"

# ── Backend dependencies ────────────────────────────────────────────
Write-Log "Installing backend dependencies (this can take a minute)..."
& $venvPip install --quiet --upgrade pip
& $venvPip install --quiet -r requirements.txt
Write-Log "Backend dependencies installed."

# ── Node / npm ───────────────────────────────────────────────────────
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Fail "Node.js not found. Install a Node LTS release from https://nodejs.org/."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Fail "npm not found (should ship with Node.js)."
}
Write-Log "Node $(node --version) / npm $(npm --version) OK"

# ── Frontend dependencies ───────────────────────────────────────────
Write-Log "Installing frontend dependencies (npm ci)..."
Push-Location frontend
npm ci --silent
Pop-Location
Write-Log "Frontend dependencies installed."

# ── .env files ───────────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Log "Created .env from .env.example -- fill in TELEGRAM_BOT_TOKEN before running the bot."
} else {
    Write-Log ".env already exists, leaving it untouched."
}

if (-not (Test-Path "frontend\.env")) {
    Copy-Item "frontend\.env.example" "frontend\.env"
    Write-Log "Created frontend\.env from frontend\.env.example."
} else {
    Write-Log "frontend\.env already exists, leaving it untouched."
}

Write-Host ""
Write-Log "Setup complete. Next steps:"
Write-Log "  1. Edit .env and set TELEGRAM_BOT_TOKEN (get one from @BotFather)."
Write-Log "  2. Activate the virtual environment: .venv\Scripts\Activate.ps1"
Write-Log "  3. Verify everything: python doctor.py"
Write-Log "  4. Start the bot: python bot.py"
