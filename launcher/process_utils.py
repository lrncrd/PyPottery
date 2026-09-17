"""Shared subprocess and path helpers."""

import logging
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("launcher.process")

# Reserved ports for the PyPottery suite to avoid claiming another sub-app's default port
RESERVED_SUITE_PORTS = {5001, 5002, 5003, 5004, 5005, 5099}


def is_port_available(port: int) -> bool:
    """Check if a TCP port on localhost can be bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def find_available_port_for_app(default_port: int, max_attempts: int = 50) -> int:
    """
    Find an available TCP port for a sub-app.
    Prioritizes default_port if free. If taken, tries standard offsets
    (e.g., default_port + 10, + 20...) while avoiding other apps' reserved ports,
    then scans incrementally.
    """
    if is_port_available(default_port):
        return default_port

    # Try predictable offsets: e.g. 5002 -> 5012, 5022, 5032...
    candidates = [default_port + 10 * i for i in range(1, 10)]
    for p in candidates:
        if p in RESERVED_SUITE_PORTS:
            continue
        if is_port_available(p):
            return p

    # Fallback to general range 5010+
    for p in range(5010, 5010 + max_attempts):
        if p in RESERVED_SUITE_PORTS or p == default_port:
            continue
        if is_port_available(p):
            return p

    raise RuntimeError(f"No available port found for application (default: {default_port})")


def find_port_owner(port: int) -> Optional[str]:
    """Identify which process is holding a port, if possible."""
    try:
        if sys.platform != "win32":
            res = subprocess.run(
                ["lsof", f"-iTCP:{port}", "-sTCP:LISTEN", "-P", "-n"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            for line in res.stdout.strip().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    proc_name = parts[0].replace(r"\x20", " ")
                    pid = parts[1]
                    if "Code" in proc_name:
                        return f"VS Code / IDE helper (PID {pid})"
                    return f"'{proc_name}' (PID {pid})"
        else:
            res = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                timeout=2,
                **no_window_kwargs(),
            )
            for line in res.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid = parts[-1]
                    return f"process PID {pid}"
    except Exception:
        pass
    return None


def resource_path() -> Path:
    """
    Root of the installed application - the files it only ever reads (imgs/,
    icons, requirements.txt, the launcher package itself).

    Kept separate from the base path the launcher *writes* to, because on
    macOS the application bundle is replaced wholesale on update and can be
    mounted read-only. See gui.get_base_path().
    """
    return Path(__file__).parent.parent


def open_path(path) -> bool:
    """Reveal a file or folder in the platform's file manager."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(path)], check=False, timeout=30)
        else:
            subprocess.run(["xdg-open", str(path)], check=False, timeout=30)
        return True
    except Exception:
        logger.exception("Could not open %s in the file manager", path)
        return False


def no_window_kwargs() -> dict:
    """
    Extra subprocess.run/Popen kwargs that suppress the console window each
    child process would otherwise flash open on Windows.

    The launcher itself runs with no console of its own (pythonw.exe in the
    WinPython package, --windowed in the PyInstaller exe), so every spawned
    pip/uv/python/nvidia-smi call gets a brand new conhost window unless told
    not to - an install alone runs dozens of these (venv creation, uninstall,
    PyTorch install, one call per requirements.txt batch...).
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
