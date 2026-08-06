"""Environment diagnostic utility.

Run this before starting the bot to catch setup problems early, with a
clear remediation step for each one, instead of hitting them later as a
confusing runtime crash (missing frontend build, missing token, etc.).

Usage:
    python doctor.py

Exits 0 if everything required is fine (warnings are OK), 1 if any
required check fails.

Design notes:
- Every check is isolated in its own try/except so one failing check
  (e.g. an import error) never stops the rest of the report from
  printing -- the whole point of this script is to show the full
  picture in one run instead of a single stack trace.
- Checks are split into required (fail the run) and optional/advisory
  (ngrok, .env values) so "python doctor.py" gives an accurate signal
  for "can I actually run this" vs. "here's something to be aware of".
"""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

MIN_PYTHON = (3, 12)
MIN_NODE_MAJOR = 18

# Package name (importable) -> what it's needed for. Matches requirements.txt.
REQUIRED_PACKAGES = {
    "telegram": "python-telegram-bot",
    "dotenv": "python-dotenv",
    "openai": "openai",
    "openpyxl": "openpyxl",
}

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
_RESULTS: list[tuple[str, str, str]] = []  # (status, label, detail)


def check(label: str):
    """Decorator: run a check function, catch any exception, and record
    a FAIL with the exception text instead of letting doctor.py itself
    crash on a broken environment -- a diagnostic tool that crashes on
    the exact conditions it exists to diagnose is not useful."""

    def wrapper(fn):
        try:
            status, detail = fn()
        except Exception as exc:  # noqa: BLE001 -- intentionally broad, see docstring
            status, detail = FAIL, f"Check raised an exception: {exc}"
        _RESULTS.append((status, label, detail))
        return fn

    return wrapper


def _run(cmd: list[str]) -> tuple[bool, str]:
    """Run a command and return (ok, stdout_or_error)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False, (result.stderr or result.stdout).strip()
        return True, result.stdout.strip()
    except FileNotFoundError:
        return False, "not found on PATH"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


# ── Toolchain ────────────────────────────────────────────────────────


@check("Python version")
def _python_version():
    current = sys.version_info[:2]
    version_str = platform.python_version()
    if current >= MIN_PYTHON:
        return PASS, f"{version_str} (>= {'.'.join(map(str, MIN_PYTHON))} required)"
    return FAIL, (
        f"{version_str} found, but {'.'.join(map(str, MIN_PYTHON))}+ is required. "
        "Install a newer Python from https://www.python.org/downloads/."
    )


@check("pip")
def _pip():
    ok, out = _run([sys.executable, "-m", "pip", "--version"])
    if ok:
        return PASS, out
    return FAIL, "pip is not available for this Python interpreter. Reinstall Python with pip included."


@check("Virtual environment")
def _venv():
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if in_venv:
        return PASS, f"active ({sys.prefix})"
    return WARN, (
        "Not running inside a virtual environment. Recommended: "
        "python3 -m venv .venv && then activate it, or just run setup.sh / setup.ps1."
    )


@check("Node.js")
def _node():
    ok, out = _run(["node", "--version"])
    if not ok:
        return FAIL, "Node.js not found on PATH. Install a Node LTS release from https://nodejs.org/."
    version = out.lstrip("v")
    try:
        major = int(version.split(".")[0])
    except ValueError:
        return WARN, f"Could not parse Node version from '{out}'."
    if major >= MIN_NODE_MAJOR:
        return PASS, out
    return WARN, f"{out} found; {MIN_NODE_MAJOR}+ recommended for the frontend toolchain."


@check("npm")
def _npm():
    npm_executable = "npm.cmd" if sys.platform == "win32" else "npm"
    ok, out = _run([npm_executable, "--version"])
    if ok:
        return PASS, out
    return FAIL, "npm not found on PATH. It ships with Node.js -- reinstall Node from https://nodejs.org/."


@check("git")
def _git():
    ok, out = _run(["git", "--version"])
    if ok:
        return PASS, out
    return FAIL, "git not found on PATH. Install it from https://git-scm.com/downloads."


@check("ngrok (optional)")
def _ngrok():
    if shutil.which("ngrok"):
        return PASS, "found on PATH"
    return WARN, (
        "Not found. The Mini App will still run locally, but Telegram won't be able to "
        "reach it without a public URL. Install from https://ngrok.com/download and run "
        "'ngrok config add-authtoken <token>' once, or set MINI_APP_URL manually in .env."
    )


# ── Dependencies ─────────────────────────────────────────────────────


@check("Backend dependencies")
def _backend_deps():
    missing = [
        dist_name
        for module_name, dist_name in REQUIRED_PACKAGES.items()
        if importlib.util.find_spec(module_name) is None
    ]
    if not missing:
        return PASS, "all importable"
    return FAIL, f"Missing: {', '.join(missing)}. Run: pip install -r requirements.txt"


@check("Frontend dependencies")
def _frontend_deps():
    node_modules = FRONTEND_DIR / "node_modules"
    if node_modules.is_dir() and any(node_modules.iterdir()):
        return PASS, "frontend/node_modules present"
    return FAIL, "frontend/node_modules missing. Run: cd frontend && npm ci"


# ── Configuration ────────────────────────────────────────────────────


@check(".env file")
def _env_file():
    env_path = BASE_DIR / ".env"
    if not env_path.is_file():
        return FAIL, "Missing. Run: cp .env.example .env, then fill in TELEGRAM_BOT_TOKEN."
    return PASS, str(env_path)


@check("TELEGRAM_BOT_TOKEN")
def _telegram_token():
    env_path = BASE_DIR / ".env"
    if not env_path.is_file():
        return WARN, "Skipped -- no .env file yet."
    text = env_path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            value = line.split("=", 1)[1].strip()
            if value:
                return PASS, "set"
            return FAIL, "TELEGRAM_BOT_TOKEN is present but empty in .env. Add a real bot token from @BotFather."
    return FAIL, "TELEGRAM_BOT_TOKEN not found in .env. Add a real bot token from @BotFather."


# ── Filesystem / database ───────────────────────────────────────────


@check("Writable data directory")
def _writable_data_dir():
    data_dir = BASE_DIR / "data"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return PASS, str(data_dir)
    except OSError as exc:
        return FAIL, f"Cannot write to {data_dir}: {exc}"


@check("SQLite database accessibility")
def _sqlite_accessible():
    data_dir = BASE_DIR / "data"
    db_path = data_dir / "session.db"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("SELECT 1")
        conn.close()
        return PASS, str(db_path)
    except sqlite3.Error as exc:
        return FAIL, f"Cannot open {db_path}: {exc}"


# ── Frontend build readiness ────────────────────────────────────────


@check("Frontend build output")
def _frontend_build():
    dist_dir = FRONTEND_DIR / "dist"
    if dist_dir.is_dir() and any(dist_dir.iterdir()):
        return PASS, "frontend/dist present (bot.py will still rebuild it on startup)"
    return WARN, (
        "frontend/dist not built yet -- not a problem, bot.py builds it automatically on "
        "startup as long as frontend dependencies are installed."
    )


# ── Network sanity (best-effort, never fails the run) ───────────────


@check("Network reachability (api.telegram.org)")
def _network():
    try:
        socket.create_connection(("api.telegram.org", 443), timeout=5).close()
        return PASS, "reachable"
    except OSError as exc:
        return WARN, f"Could not reach api.telegram.org: {exc}. Check firewall/proxy settings if the bot fails to start."


# ── Report ───────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 60)
    print("  FreikerDialBot -- Environment Doctor")
    print("=" * 60)
    print()

    symbol = {PASS: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}
    for status, label, detail in _RESULTS:
        print(f"{symbol[status]} {label}: {detail}")

    fails = [r for r in _RESULTS if r[0] == FAIL]
    warns = [r for r in _RESULTS if r[0] == WARN]

    print()
    print(f"{len(_RESULTS) - len(fails) - len(warns)} passed, {len(warns)} warning(s), {len(fails)} failed.")

    if fails:
        print()
        print("Fix the FAIL items above, then re-run: python doctor.py")
        return 1

    print()
    print("Environment looks ready. Next step: python bot.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
