"""Shared subprocess helpers."""

import subprocess
import sys


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
