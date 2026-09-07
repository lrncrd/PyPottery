"""Shared subprocess and path helpers."""

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("launcher.process")


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
