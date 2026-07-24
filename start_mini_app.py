"""One-command launcher for the Telegram Mini App development stack.

Starts all three services (backend API, frontend dev server, ngrok tunnel),
auto-discovers the ngrok HTTPS URL, sets MINI_APP_URL, and starts the bot
with the correct configuration — no manual URL copying needed.
"""

from __future__ import annotations

import os
import sys
import time
import json
import subprocess
import threading
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
NGROK_API_URL = "http://127.0.0.1:4040/api/tunnels"
POLL_INTERVAL = 1.0
MAX_WAIT_SECONDS = 30


def _log(service: str, message: str) -> None:
    print(f"[{service}] {message}", flush=True)


def _read_stream(stream, service: str) -> None:
    """Read lines from a subprocess stream and print them with a prefix."""
    for line in iter(stream.readline, ""):
        if line:
            _log(service, line.rstrip("\n\r"))
    stream.close()


def _start_process(
    cmd: list[str], service: str, cwd: str | None = None, env: dict[str, str] | None = None
) -> subprocess.Popen:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
        env=env,
    )
    thread = threading.Thread(target=_read_stream, args=(proc.stdout, service), daemon=True)
    thread.start()
    return proc


def _get_ngrok_url() -> str | None:
    """Fetch the public HTTPS URL from ngrok's local API."""
    try:
        req = urllib.request.Request(NGROK_API_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tunnels = data.get("tunnels", [])
        for tunnel in tunnels:
            if tunnel.get("proto") == "https":
                return tunnel["public_url"]
        # Fallback: return the first tunnel
        if tunnels:
            return tunnels[0]["public_url"]
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError, OSError):
        pass
    return None


def _wait_for_ngrok() -> str:
    """Poll ngrok API until a tunnel is available, then return the URL."""
    _log("ngrok", "Waiting for tunnel to become available...")
    for _ in range(int(MAX_WAIT_SECONDS / POLL_INTERVAL)):
        url = _get_ngrok_url()
        if url:
            _log("ngrok", f"Tunnel ready: {url}")
            return url
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(
        "ngrok did not become available. "
        "Make sure ngrok is installed and you've run 'ngrok config add-authtoken <token>' once."
    )


def main() -> None:
    print("=" * 60)
    print("  FreikerDialBot — Mini App Development Launcher")
    print("=" * 60)
    print()

    # ── Step 1: Kill any existing ngrok tunnels ──────────────────────
    _log("ngrok", "Stopping any existing ngrok tunnels...")
    subprocess.run(["ngrok", "kill"], check=False)
    time.sleep(1)

    # ── Step 2: Build the frontend ──────────────────────────────────
    # mini_app_api.py serves the built frontend as static files from
    # MINI_APP_STATIC_DIR (see mini_app_api.py's _serve_static) -- this
    # is what makes the single ngrok tunnel to the backend actually
    # work as a Mini App: one origin serves both the UI and the API, so
    # there's no separate frontend process/port/CORS concern. Previously
    # this launcher never built the frontend or set this variable at
    # all, so opening the "Mini App" URL would 404 against a backend
    # with nothing to serve.
    dist_dir = FRONTEND_DIR / "dist"
    _log("frontend", "Building frontend (npm run build)...")
    build_result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(FRONTEND_DIR),
        capture_output=True,
        text=True,
    )
    if build_result.returncode != 0:
        _log("frontend", "ERROR: frontend build failed:")
        print(build_result.stdout)
        print(build_result.stderr)
        _log("launcher", "Aborting -- cannot serve a Mini App with no built frontend.")
        sys.exit(1)
    if not dist_dir.is_dir():
        _log("frontend", f"ERROR: build succeeded but {dist_dir} does not exist.")
        sys.exit(1)
    _log("frontend", f"Build complete: {dist_dir}")

    # ── Step 3: Start the backend API ──────────────────────────────────
    _log("backend", "Starting Mini App API on http://0.0.0.0:8000 ...")
    env = os.environ.copy()
    env["MINI_APP_STATIC_DIR"] = str(dist_dir)
    backend_proc = _start_process(
        [sys.executable, "mini_app_api.py"],
        "backend",
        cwd=str(BASE_DIR),
        env=env,
    )
    time.sleep(2)  # brief pause to let it bind

    # ── Step 4: Start ngrok tunnel to backend ──────────────────────────
    _log("ngrok", "Starting ngrok tunnel to http://localhost:8000 ...")
    ngrok_proc = _start_process(
        ["ngrok", "http", "8000", "--log=stdout"],
        "ngrok",
    )

    # ── Step 5: Wait for ngrok and get URL ────────────────────────────
    try:
        mini_app_url = _wait_for_ngrok()
    except RuntimeError as e:
        _log("launcher", f"ERROR: {e}")
        _log("launcher", "Falling back — set MINI_APP_URL manually in .env and restart bot.py")
        mini_app_url = None

    # ── Step 6: Start the bot with MINI_APP_URL set ──────────────────
    if mini_app_url:
        env["MINI_APP_URL"] = mini_app_url
        _log("launcher", f"MINI_APP_URL set to: {mini_app_url}")
    else:
        _log("launcher", "MINI_APP_URL not set — bot will show MenuButtonCommands")

    _log("bot", "Starting Telegram bot...")
    bot_proc = subprocess.Popen(
        [sys.executable, "bot.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(BASE_DIR),
        env=env,
    )
    threading.Thread(target=_read_stream, args=(bot_proc.stdout, "bot"), daemon=True).start()

    print()
    if mini_app_url:
        print(f"  Mini App URL: {mini_app_url}")
    print("  Press Ctrl+C to stop all services.")
    print()

    try:
        # Wait for any process to exit
        while True:
            time.sleep(1)
            for name, proc in [("backend", backend_proc), ("bot", bot_proc)]:
                if proc.poll() is not None:
                    _log("launcher", f"{name} exited unexpectedly (code {proc.returncode})")
                    raise SystemExit(1)
            # ngrok may restart; just keep polling
    except KeyboardInterrupt:
        _log("launcher", "Shutting down all services...")
    finally:
        for proc in [backend_proc, ngrok_proc, bot_proc]:
            if proc.poll() is None:
                proc.terminate()
        _log("launcher", "All services stopped.")


if __name__ == "__main__":
    main()