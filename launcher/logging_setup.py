"""
Central logging for the PyPottery launcher.

Every shipped build runs without a console - pythonw.exe (WinPython package),
PyInstaller --windowed, the macOS .app bundle, a Terminal=false .desktop entry.
In all of those `sys.stdout`/`sys.stderr` are None, so plain print() output and,
far worse, unhandled tracebacks are lost. This module gives the launcher a real
log file so a user who reports "it doesn't work" has something to send.

Two handlers are attached, on purpose:

  * a bootstrap file in a per-user location that is always writable, installed
    before anything else runs - it captures failures that happen while working
    out where the app's own data lives (which can itself raise);
  * the app's own logs/launcher.log next to the rest of the user's data, added
    as soon as that path is known.
"""

import faulthandler
import io
import logging
import logging.handlers
import os
import platform
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

_LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s: %(message)s"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 5

_initialized = False
_bootstrap_dir: Optional[Path] = None
_base_dir: Optional[Path] = None
# faulthandler needs a real file descriptor for the lifetime of the process,
# so the handle is parked here rather than being garbage collected.
_faulthandler_file = None


def _fallback_log_dir() -> Path:
    """A per-user location that is writable even when the app directory isn't."""
    system = platform.system()
    if system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return root / "PyPottery" / "logs"
    if system == "Darwin":
        return Path.home() / "Library" / "Logs" / "PyPottery"
    state_home = os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state")
    return Path(state_home) / "pypottery" / "logs"


class _StreamToLogger(io.TextIOBase):
    """
    Stand-in for sys.stdout/sys.stderr that turns writes into log records.

    Lets the ~60 existing print() calls keep working (and start being useful)
    on builds where the real streams are None, without touching them.
    """

    def __init__(self, logger: logging.Logger, level: int):
        self._logger = logger
        self._level = level
        self._buffer = ""

    def write(self, text) -> int:
        if not isinstance(text, str):
            text = str(text)
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self._logger.log(self._level, line.rstrip())
        return len(text)

    def flush(self):
        if self._buffer.strip():
            self._logger.log(self._level, self._buffer.rstrip())
        self._buffer = ""

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


def _make_file_handler(directory: Path, filename: str) -> logging.Handler:
    directory.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        directory / filename,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler.setLevel(logging.DEBUG)
    return handler


def _install_excepthooks():
    logger = logging.getLogger("launcher.crash")

    def _hook(exc_type, exc_value, exc_tb):
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _hook

    def _thread_hook(args):
        logger.critical(
            "Unhandled exception in thread %s",
            getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_hook


def init_logging() -> Optional[Path]:
    """
    Set up logging. Must be the first thing main() does - later steps
    (working out the data directory, binding a port) can fail, and without
    this their tracebacks go nowhere on a windowless build.

    Never raises: logging must not be the reason the app won't start.
    """
    global _initialized, _bootstrap_dir, _faulthandler_file

    if _initialized:
        return _bootstrap_dir

    try:
        # Handler errors print to stderr, which may itself be a shim writing
        # back into logging - silence them rather than risk recursion.
        logging.raiseExceptions = False

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)

        _bootstrap_dir = _fallback_log_dir()
        root.addHandler(_make_file_handler(_bootstrap_dir, "launcher.log"))

        # Werkzeug logs one line per request; the UI polls /api/state every few
        # seconds, which would crowd out everything worth reading.
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

        if sys.stdout is None:
            sys.stdout = _StreamToLogger(logging.getLogger("stdout"), logging.INFO)
        if sys.stderr is None:
            sys.stderr = _StreamToLogger(logging.getLogger("stderr"), logging.ERROR)

        try:
            _faulthandler_file = open(_bootstrap_dir / "faulthandler.log", "a", buffering=1)
            faulthandler.enable(file=_faulthandler_file)
        except Exception:
            pass  # A hard-crash dump is a bonus, not a requirement.

        _install_excepthooks()
        _initialized = True

        logging.getLogger("launcher").info(
            "=== PyPottery launcher starting (python %s, %s %s) ===",
            platform.python_version(), platform.system(), platform.release(),
        )
    except Exception:
        # Deliberately swallowed - see the docstring.
        pass

    return _bootstrap_dir


def bind_base_path(base_path: Path) -> Optional[Path]:
    """
    Start logging into the user's own data directory as well, once it's known.
    The bootstrap handler stays attached so nothing is lost in between.
    """
    global _base_dir

    try:
        log_dir = Path(base_path) / "logs"
        if _base_dir == log_dir:
            return _base_dir
        logging.getLogger().addHandler(_make_file_handler(log_dir, "launcher.log"))
        _base_dir = log_dir
        logging.getLogger("launcher").info("Logging to %s", log_dir)
    except Exception:
        logging.getLogger("launcher").exception("Could not open a log file under %s", base_path)

    return _base_dir


def get_log_dir() -> Optional[Path]:
    """The directory to point the user at - the app's own if it was usable."""
    return _base_dir or _bootstrap_dir


def app_log_dir() -> Optional[Path]:
    """Where per-sub-app output is captured."""
    root = get_log_dir()
    if root is None:
        return None
    try:
        path = root / "apps"
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        return None


def guarded(fn: Callable, name: str = "", on_error: Optional[Callable] = None) -> Callable:
    """
    Wrap a thread target so an unhandled exception is logged and reported
    instead of silently killing the feature it was running.
    """
    label = name or getattr(fn, "__name__", "thread")

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            logging.getLogger("launcher.thread").exception("Unhandled exception in %s", label)
            if on_error is not None:
                try:
                    on_error(exc)
                except Exception:
                    logging.getLogger("launcher.thread").exception(
                        "Error handler for %s failed too", label
                    )

    wrapper.__name__ = f"guarded_{label}"
    return wrapper
