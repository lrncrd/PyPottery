"""
Stops two launcher processes from running against the same data directory.

A second copy started by accident (double-clicking the icon while it's
already running, a stray shortcut, ...) would otherwise race the first one
over the same pypottery_env venv and app installs - the in-process job guards
in web_server.py only ever see one process's own threads, never a second,
independent process. Uses an OS-level advisory file lock rather than a PID
file: the OS releases it automatically the moment the holding process exits,
crash included, so there is no separate "is this lock stale?" check to get
wrong.
"""

import json
import logging
import os
import sys
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("launcher.instance_lock")

LOCK_FILENAME = ".pypottery.lock"


class InstanceLock:
    """Held for the life of the process; released on close (including a crash)."""

    def __init__(self, base_path: Path):
        self.path = Path(base_path) / LOCK_FILENAME
        self._handle = None

    def acquire(self) -> bool:
        """
        True if this process now owns the lock. On failure the caller can
        still read/probe the file - the handle just isn't held by us.
        """
        try:
            if not self.path.exists():
                self.path.touch()
            self._handle = open(self.path, "r+b")
        except OSError:
            logger.exception("Could not open the instance lock file at %s", self.path)
            return True  # A filesystem hiccup shouldn't block startup.

        try:
            if sys.platform == "win32":
                import msvcrt
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._handle.close()
            self._handle = None
            return False

        return True

    def write_info(self, port: int):
        """
        Record how to reach this instance, for the next process that finds
        the lock held.

        Windows' byte-range locking is mandatory, not just advisory: a
        separate process trying to read byte 0 while we hold a lock on it
        gets the whole read call rejected, not just that byte. So the locked
        byte (0) is left as a one-byte placeholder and the actual payload
        starts at offset 1, which a reader can access even while we're
        holding the lock, as long as it doesn't also touch offset 0.
        """
        if not self._handle:
            return
        try:
            payload = json.dumps({"pid": os.getpid(), "port": port}).encode("utf-8")
            self._handle.seek(0)
            self._handle.truncate()
            self._handle.write(b"L" + payload)
            self._handle.flush()
        except OSError:
            logger.exception("Could not write instance info to the lock file")

    def release(self):
        if not self._handle:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                try:
                    self._handle.seek(0)
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            self._handle.close()
        except OSError:
            pass
        self._handle = None


def read_existing_instance(base_path: Path) -> Optional[dict]:
    """
    Best-effort read of whoever is currently holding the lock.

    Deliberately skips byte 0 (see write_info's docstring): reading it while
    another process holds Windows' mandatory lock on that byte would fail
    the whole read, even though the payload we actually want starts at
    offset 1 and isn't locked at all.
    """
    try:
        with open(Path(base_path) / LOCK_FILENAME, "rb") as f:
            f.seek(1)
            content = f.read()
        return json.loads(content) if content else None
    except (OSError, ValueError):
        return None


def probe(port: int, timeout: float = 2.0) -> bool:
    """Is a launcher actually answering on this port right now?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False
