"""
Utilities for managing background processes.
"""
from __future__ import annotations

import subprocess
import threading

def log_message(service: str, message: str) -> None:
    """Prints a formatted message with a service prefix."""
    print(f"[{service}] {message}", flush=True)

def _read_stream(stream, service: str) -> None:
    """
    Reads lines from a subprocess's stream and logs them with a service prefix.
    This function is intended to be run in a separate thread.
    """
    for line in iter(stream.readline, ""):
        if line:
            log_message(service, line.strip())
    stream.close()

def start_process(
    cmd: list[str],
    service_name: str,
    cwd: str | None = None,
    env: dict | None = None,
) -> subprocess.Popen:
    """
    Starts a new process, captures its output, and logs it in a separate thread.

    Args:
        cmd: The command to execute as a list of strings.
        service_name: A short name for the service being started (for logging).
        cwd: The working directory for the new process.
        env: A dictionary of environment variables for the new process.

    Returns:
        The Popen object for the newly started process.
    """
    log_message("launcher", f"Starting {service_name}...")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
        env=env,
    )

    thread = threading.Thread(
        target=_read_stream,
        args=(process.stdout, service_name),
        daemon=True,
    )
    thread.start()

    log_message("launcher", f"{service_name} started (PID: {process.pid}).")
    return process
