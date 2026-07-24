"""Mini App stack launcher: frontend build, backend API, ngrok tunnel.

launch_mini_app_stack() is the reusable entry point -- bot.py calls this
directly (in-process, not as a subprocess) so `python bot.py` alone can
bring up the entire stack: frontend build, Mini App backend, and the
ngrok tunnel, before starting the Telegram bot itself with the
discovered MINI_APP_URL already configured.

Running this file directly (`python start_mini_app.py`) still works
exactly as before, for anyone who wants only the Mini App stack (backend
+ frontend + tunnel) without also starting the bot -- e.g. a frontend
developer iterating on the UI who doesn't want a live bot connected.
That standalone mode is main(), below, which calls the same function
this file exposes for bot.py, then additionally starts bot.py as a
subprocess to preserve its previous "one command starts literally
everything" behavior unchanged.
"""

from __future__ import annotations

import os
import shutil
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


def launch_mini_app_stack(
    base_dir: Path | None = None,
) -> tuple[subprocess.Popen | None, subprocess.Popen | None, str | None]:
    """Builds the frontend, starts the Mini App backend (statically
    serving that build), and starts an ngrok tunnel to it if ngrok is
    available.

    Returns (backend_proc, ngrok_proc, mini_app_url). ngrok_proc and
    mini_app_url are None if ngrok isn't installed or no tunnel could be
    established -- callers should treat that as "Mini App not
    externally reachable yet" and degrade gracefully (see bot.py's
    _post_init, which already falls back to MenuButtonCommands when
    mini_app_url is falsy).

    Raises SystemExit(1) if the frontend build itself fails -- that one
    failure IS fatal, since there is nothing to serve without it.
    """
    base_dir = base_dir or BASE_DIR
    frontend_dir = base_dir / "frontend"

    # ── Kill any existing ngrok tunnels ──────────────────────────────
    # Guarded: `ngrok kill` unconditionally previously raised an
    # uncaught FileNotFoundError and crashed the entire launch sequence
    # -- before the frontend was even built -- if ngrok wasn't installed
    # or wasn't on PATH. Neither the frontend build nor the backend
    # start actually depend on ngrok, so a missing ngrok binary should
    # degrade gracefully, not take down everything else with it.
    ngrok_available = shutil.which("ngrok") is not None
    if ngrok_available:
        _log("ngrok", "Stopping any existing ngrok tunnels...")
        subprocess.run(["ngrok", "kill"], check=False)
        time.sleep(1)
    else:
        _log(
            "ngrok",
            "ngrok not found on PATH -- skipping tunnel setup. "
            "Install ngrok (https://ngrok.com/download) and run "
            "'ngrok config add-authtoken <token>' once, or set MINI_APP_URL "
            "manually in .env if you're exposing the Mini App another way.",
        )

    # ── Build the frontend ───────────────────────────────────────────
    # mini_app_api.py serves the built frontend as static files from
    # MINI_APP_STATIC_DIR (see mini_app_api.py's _serve_static) -- one
    # origin serves both the UI and the API, so there's no separate
    # frontend process/port/CORS concern and only one URL for Telegram
    # to open.
    dist_dir = frontend_dir / "dist"
    _log("frontend", "Building frontend (npm run build)...")
    build_result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(frontend_dir),
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

    # ── Start the backend API ────────────────────────────────────────
    _log("backend", "Starting Mini App API on http://0.0.0.0:8000 ...")
    env = os.environ.copy()
    env["MINI_APP_STATIC_DIR"] = str(dist_dir)
    backend_proc = _start_process(
        [sys.executable, "mini_app_api.py"],
        "backend",
        cwd=str(base_dir),
        env=env,
    )
    time.sleep(2)  # brief pause to let it bind

    # ── Start ngrok tunnel to backend ────────────────────────────────
    mini_app_url = None
    ngrok_proc = None
    if ngrok_available:
        _log("ngrok", "Starting ngrok tunnel to http://localhost:8000 ...")
        ngrok_proc = _start_process(
            ["ngrok", "http", "8000", "--log=stdout"],
            "ngrok",
        )
        try:
            mini_app_url = _wait_for_ngrok()
        except RuntimeError as e:
            _log("launcher", f"ERROR: {e}")
            _log("launcher", "Falling back -- set MINI_APP_URL manually in .env if needed")
            mini_app_url = None
    else:
        _log("launcher", "Skipping ngrok tunnel (not installed) — set MINI_APP_URL manually in .env if needed")

    return backend_proc, ngrok_proc, mini_app_url


def main() -> None:
    """Standalone CLI: brings up the full stack (frontend, backend,
    ngrok, AND the bot) as four separate processes. Kept for anyone
    used to running this file directly. The single-command entry point
    bot.py now uses is launch_mini_app_stack() above, called in-process
    (see bot.py's main()) -- this function is a thin wrapper around the
    same logic plus spawning bot.py as an additional subprocess, so
    there's exactly one place the actual stack-launching logic lives.
    """
    print("=" * 60)
    print("  FreikerDialBot — Mini App Development Launcher")
    print("=" * 60)
    print()

    backend_proc, ngrok_proc, mini_app_url = launch_mini_app_stack(BASE_DIR)

    env = os.environ.copy()
    if mini_app_url:
        env["MINI_APP_URL"] = mini_app_url
        _log("launcher", f"MINI_APP_URL set to: {mini_app_url}")
    else:
        _log("launcher", "MINI_APP_URL not set — bot will show MenuButtonCommands")

    _log("bot", "Starting Telegram bot...")
    bot_proc = subprocess.Popen(
        [sys.executable, "bot.py", "--no-mini-app"],
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
            if proc is not None and proc.poll() is None:
                proc.terminate()
        _log("launcher", "All services stopped.")


if __name__ == "__main__":
    main()