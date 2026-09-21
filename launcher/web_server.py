"""
PyPottery Suite Launcher - Web Backend
Flask application exposing the launcher's hardware/environment/app-management
logic over HTTP + Server-Sent Events, for the browser-based launcher UI.
"""

import collections
import dataclasses
import json
import logging
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory

from .app_manager import AppInfo, AppManager, DownloadProgress
from .environment_manager import EnvironmentManager, InstallProgress
from .error_messages import classify
from .hardware_detector import HardwareInfo, detect_hardware
from .logging_setup import app_log_dir, get_log_dir, guarded
from . import project_backup
from .process_utils import open_path, resource_path
from .update_checker import UpdateChecker
from .updater import LauncherProgress, LauncherUpdater
from .wikiquote_fetcher import fetch_live_wikiquote

try:
    # Gitignored, local-only switch - see dev_config.example.py. Missing on a
    # fresh clone, which is the normal (non-developer) case.
    from .dev_config import DEVELOPER_MODE
except ImportError:
    DEVELOPER_MODE = False

LAUNCHER_VERSION = "1.2.0"

# How long to wait after the last browser tab disconnects from /api/events
# before treating the launcher as closed. A page reload drops the old
# EventSource and opens a new one almost immediately, well within this
# window; an actual tab close never reconnects, so the grace period expires
# and triggers a full shutdown (launcher + every running sub-app).
AUTO_SHUTDOWN_GRACE_SECONDS = 8

# Shared AI-model cache dir (see PYPOTTERY_MODEL_CACHE): every sub-app that
# respects it downloads models here instead of into its own folder, keyed by a
# per-app subfolder name.
MODEL_CACHE_DIRNAME = "model_cache"

# Internal HF hub-cache housekeeping dirs - never a model unit on their own.
_HF_INTERNAL_DIRS = {"blobs", "snapshots", "refs", ".locks", ".no_exist"}
_MODEL_FILE_EXTS = {".pt", ".pth", ".safetensors", ".bin", ".onnx", ".ckpt", ".gguf"}

# Purely cosmetic: which sub-app's model-loading code writes into each
# per-app subfolder, so the UI can show "used by X" (see PyPotteryInk/models.py,
# PyPotteryLens/app.py, PyPotteryScan/app/config.py, PyPotteryTrace/sam2_handler.py).
CACHE_CATEGORY_APPS = {
    "huggingface": "PyPottery Ink",
    "transformers": "PyPottery Lens",
    "scan": "PyPottery Scan",
    "sam2": "PyPottery Trace",
    "yolo": "PyPottery Lens",
    "classifier": "PyPottery Lens",
}

logger = logging.getLogger("launcher.web")

# Console tags -> log levels, so everything the user sees in the UI console
# also lands in the log file at a sensible severity.
_TAG_LEVELS = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "success": logging.INFO,
    "info": logging.INFO,
    "progress": logging.INFO,
}


class EventBus:
    """Fans out published events to every subscribed SSE connection."""

    def __init__(self):
        self._subscribers = []
        self._lock = threading.Lock()

    def subscribe(self) -> "queue.Queue":
        q = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue"):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def publish(self, event: dict):
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass


class LauncherState:
    """Holds all launcher managers and shared runtime state for the web app."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path).resolve()
        self.resource_path = resource_path().resolve()
        req = self.base_path / "requirements.txt"
        bundle_req = self.resource_path / "requirements.txt"
        self.requirements_file = bundle_req if (not req.exists() and bundle_req.exists()) else req
        self.launcher_version = LAUNCHER_VERSION

        self.event_bus = EventBus()
        self.console_log = collections.deque(maxlen=500)
        self.stop_event = threading.Event()

        # Guards the "shut down when the last browser tab disconnects" timer.
        self.auto_shutdown_timer: Optional[threading.Timer] = None
        self.auto_shutdown_lock = threading.Lock()

        # Long-running work, keyed by "env" / "app:<id>" / "launcher_update".
        # Serves three purposes: it stops the same install being started twice
        # (two tabs, an impatient double-click), it keeps the auto-shutdown
        # timer from killing the launcher mid-install, and it lets a reloaded
        # page pick the running job back up instead of offering to start it
        # again.
        self.jobs = {}
        self.jobs_lock = threading.Lock()

        self.hardware_info: Optional[HardwareInfo] = None
        self.env_manager: Optional[EnvironmentManager] = None
        self.app_manager: Optional[AppManager] = None
        self.update_checker = UpdateChecker()
        self.updater = LauncherUpdater(self.base_path)
        # Uploaded backup zips waiting for the user to confirm an import.
        self.pending_imports = project_backup.PendingImports()

        # Set by gui.py once the werkzeug server is created, so /api/shutdown
        # can stop it from a background thread (never from the serving thread).
        self.server = None

    # ---- Job tracking -------------------------------------------------

    @property
    def install_in_progress(self) -> bool:
        with self.jobs_lock:
            return bool(self.jobs)

    def try_start_job(self, key: str, kind: str, label: str) -> bool:
        """Claim the slot for this piece of work. False if it's already taken."""
        with self.jobs_lock:
            if key in self.jobs:
                return False
            self.jobs[key] = {
                "key": key, "kind": kind, "label": label,
                "started_at": time.time(), "progress": None,
            }
        self.emit({"type": "job_started", "job": {"key": key, "kind": kind, "label": label}})
        return True

    def update_job(self, key: str, progress: dict):
        """Remember the latest progress so a reloaded tab can catch up."""
        with self.jobs_lock:
            job = self.jobs.get(key)
            if job is not None:
                job["progress"] = progress

    def finish_job(self, key: str):
        with self.jobs_lock:
            self.jobs.pop(key, None)
        self.emit({"type": "job_finished", "job": {"key": key}})

    def jobs_snapshot(self) -> list:
        with self.jobs_lock:
            return [dict(job) for job in self.jobs.values()]

    def busy_response(self, key: str):
        """409 payload for a request that collided with running work."""
        with self.jobs_lock:
            job = self.jobs.get(key)
            label = job["label"] if job else "Another operation"
        return {
            "success": False,
            "code": "busy",
            "error": f"{label} is already running. Wait for it to finish.",
        }

    def log(self, message: str, tag: str = "info"):
        entry = {
            "type": "console",
            "message": message,
            "tag": tag,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        self.console_log.append(entry)
        self.event_bus.publish(entry)
        logger.log(_TAG_LEVELS.get(tag, logging.INFO), "%s", message)

    def emit(self, event: dict):
        self.event_bus.publish(event)

    def apps_snapshot(self) -> list:
        if not self.app_manager:
            return []
        return [serialize_app(a) for a in self.app_manager.get_app_list()]


def serialize_app(app: AppInfo) -> dict:
    """AppInfo as JSON - excludes the non-serializable `process` handle."""
    return {
        "id": app.id,
        "name": app.name,
        "description": app.description,
        "repo_owner": app.repo_owner,
        "repo_name": app.repo_name,
        "port": app.port,
        "default_port": getattr(app, "default_port", app.port),
        "min_ram_gb": app.min_ram_gb,
        "recommended_ram_gb": app.recommended_ram_gb,
        "requires_gpu": app.requires_gpu,
        "icon": app.icon,
        "logo_path": app.logo_path,
        "installed": app.installed,
        "installed_version": app.installed_version,
        "latest_version": app.latest_version,
        "update_available": app.update_available,
        "is_running": app.is_running,
        "is_starting": getattr(app, "is_starting", False),
        "last_error": getattr(app, "last_error", None),
        "developer_mode": DEVELOPER_MODE,
    }


def initialize_state(state: LauncherState):
    """Detect hardware, wire up managers, start app monitoring. Run on a background thread."""
    state.log("Initializing PyPottery Suite Launcher...", "info")

    if DEVELOPER_MODE:
        state.log("Developer mode ON - sub-apps run from local git checkouts with active terminal Python", "warning")

    state.env_manager = EnvironmentManager(state.base_path, developer_mode=DEVELOPER_MODE)
    state.env_manager.set_progress_callback(lambda p: _on_env_progress(state, p))

    # python_available(), not venv_exists(): even a half-installed environment
    # can tell us which PyTorch build is in there.
    python_exe = state.env_manager.python_executable if state.env_manager.python_available() else None
    state.hardware_info = detect_hardware(python_exe)
    state.log("Hardware detection complete", "success")
    state.emit({"type": "hardware", "hardware": state.hardware_info.to_dict()})

    if not state.hardware_info.cuda_compatible and state.hardware_info.driver_warning:
        state.log("Incompatible NVIDIA driver detected", "warning")
        state.emit({"type": "driver_warning", "message": state.hardware_info.driver_warning})

    env_state = state.env_manager.env_state()
    if env_state["status"] == "ready":
        if DEVELOPER_MODE:
            state.log(f"Developer Mode: Using active terminal Python environment", "success")
        else:
            state.log("Python environment found", "success")
        state.log(f"Using Python: {state.env_manager.python_executable}", "info")
    else:
        if env_state["status"] == "absent":
            state.log("Python environment not found - please run Setup", "warning")
        else:
            state.log(f"{env_state['reason']} - use Repair Environment", "warning")
        # Placeholder until Setup creates pypottery_env - AppManager won't
        # actually launch anything with this before then. Route through
        # env_manager.base_python() rather than sys.executable directly:
        # in the frozen exe, sys.executable is PyPottery.exe itself, and
        # handing that to a subprocess.Popen() call would relaunch the
        # whole app instead of failing cleanly.
        try:
            python_exe = Path(state.env_manager.base_python())
        except RuntimeError:
            python_exe = Path(sys.executable)

    state.app_manager = AppManager(state.base_path, python_exe, developer_mode=DEVELOPER_MODE)
    state.app_manager.set_status_callback(lambda app_id, message: _on_app_status(state, app_id, message))
    state.app_manager.set_download_callback(lambda progress: _on_download_progress(state, progress))

    state.emit({"type": "env_status", **env_state})
    state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})

    threading.Thread(
        target=guarded(_monitor_apps, "monitor_apps"), args=(state,), daemon=True
    ).start()

    _check_for_updates(state)


def _monitor_apps(state: LauncherState):
    """Periodically detect sub-apps that stopped on their own (crash, closed by user, etc.)."""
    while not state.stop_event.wait(3):
        if not state.app_manager:
            continue
        for app_id in list(state.app_manager._processes.keys()):
            status = state.app_manager.get_app_status(app_id)
            if not status.is_running:
                app = state.app_manager.apps.get(app_id)
                if app:
                    app.is_running = False
                    state.log(f"{app.name} has stopped", "info")
                    state.emit({"type": "app_status", "app": serialize_app(app)})


def _on_env_progress(state: LauncherState, progress: InstallProgress):
    state.emit({"type": "env_progress", **dataclasses.asdict(progress)})
    state.log(progress.message, "error" if progress.is_error else "progress")

    if progress.stage == "complete" or progress.percent >= 100:
        python_exe = state.env_manager.python_executable if state.env_manager and state.env_manager.python_available() else None
        state.hardware_info = detect_hardware(python_exe)
        state.emit({"type": "hardware", "hardware": state.hardware_info.to_dict()})


def _on_app_status(state: LauncherState, app_id: str, message: str):
    state.log(f"[{app_id}] {message}", "info")
    app = state.app_manager.apps.get(app_id) if state.app_manager else None
    if app:
        state.emit({"type": "app_status", "app": serialize_app(app)})


def _on_download_progress(state: LauncherState, progress: DownloadProgress):
    state.emit({"type": "download_progress", **dataclasses.asdict(progress)})


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def _friendly_model_name(dirname: str) -> str:
    """'models--stabilityai--sd-turbo' (HF hub cache format) -> 'stabilityai/sd-turbo'."""
    if dirname.startswith("models--"):
        return dirname[len("models--"):].replace("--", "/")
    return dirname


def scan_model_cache(cache_root: Path) -> list:
    """
    Find downloadable model units under the shared model cache. Each sub-app
    stores models differently (HF_HOME hub cache, a custom `cache_dir=`,
    `snapshot_download(local_dir=...)`, or raw checkpoint files) - this walks
    every per-app subfolder and normalizes whatever it finds into one flat,
    deletable list instead of assuming a single on-disk layout.
    """
    entries = []
    if not cache_root.exists():
        return entries

    def walk(node: Path, category: str):
        try:
            children = sorted(node.iterdir())
        except OSError:
            return
        for child in children:
            if child.name in _HF_INTERNAL_DIRS or child.name.startswith("."):
                continue
            if child.is_dir():
                if child.name.startswith("models--"):
                    entries.append({
                        "path": str(child.relative_to(cache_root)),
                        "category": category,
                        "name": _friendly_model_name(child.name),
                        "size_bytes": _dir_size(child),
                        "kind": "huggingface-model",
                    })
                elif child.name == "hub":
                    # HF_HOME-style caches nest the actual models under hub/ -
                    # descend transparently rather than treating hub/ itself as a unit.
                    walk(child, category)
                else:
                    entries.append({
                        "path": str(child.relative_to(cache_root)),
                        "category": category,
                        "name": child.name,
                        "size_bytes": _dir_size(child),
                        "kind": "model-dir",
                    })
            else:
                if child.suffix.lower() in _MODEL_FILE_EXTS:
                    try:
                        size = child.stat().st_size
                    except OSError:
                        size = 0
                    entries.append({
                        "path": str(child.relative_to(cache_root)),
                        "category": category,
                        "name": child.name,
                        "size_bytes": size,
                        "kind": "checkpoint-file",
                    })

    try:
        top_level = sorted(cache_root.iterdir())
    except OSError:
        return entries

    for category_dir in top_level:
        if category_dir.is_dir():
            walk(category_dir, category_dir.name)

    for entry in entries:
        entry["used_by"] = CACHE_CATEGORY_APPS.get(entry["category"])
    entries.sort(key=lambda e: e["size_bytes"], reverse=True)
    return entries


def model_cache_snapshot(state: LauncherState) -> dict:
    cache_root = state.base_path / MODEL_CACHE_DIRNAME
    entries = scan_model_cache(cache_root)
    return {
        "cache_root": str(cache_root),
        "total_size_bytes": sum(e["size_bytes"] for e in entries),
        "entries": entries,
    }


def _check_for_updates(state: LauncherState, force_refresh: bool = False):
    """
    Check launcher + app updates. Launcher check is quick and runs inline; app
    checks run on a thread.

    force_refresh bypasses UpdateChecker's 2-hour cache: the automatic check at
    launcher startup leaves it on (avoids hammering GitHub's unauthenticated
    rate limit on every restart), but an explicit "Check Updates" click must
    always hit the live API - a stale cached answer would silently defeat the
    one thing the user just asked for.
    """
    if not state.app_manager:
        return

    if DEVELOPER_MODE:
        # Dev checkouts track their own git remote directly - a GitHub-release
        # comparison would only produce a meaningless "update available"
        # badge. Instead, re-scan each checkout's local VERSION file: the
        # launcher only detects it once at startup, so a `git pull` that
        # bumps VERSION (e.g. the auto-release bot's version-bump commit)
        # otherwise stays invisible until the launcher itself is restarted.
        state.log("Developer mode: re-scanning local checkouts for version changes", "info")
        state.app_manager.refresh_installed_status()
        state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})
        return

    state.log("Checking for updates...", "info")

    try:
        launcher_update = state.update_checker.check_for_update(
            "lrncrd", "PyPottery", state.launcher_version, force_refresh=force_refresh
        )
        if launcher_update.update_available:
            clean_lv = str(launcher_update.latest_version).lstrip("v")
            state.log(f"Launcher update available: v{clean_lv}", "warning")
            state.emit({
                "type": "launcher_update_available",
                "update": dataclasses.asdict(launcher_update),
            })
    except Exception as e:
        state.log(f"Failed to check launcher updates: {classify(e).message}", "error")

    # _make_request() swallows a 403/429 and returns None rather than raising
    # (see UpdateChecker), so a rate limit doesn't show up as an exception -
    # without this check, check_all_updates() below would just come back
    # empty and log the misleading "All applications are up to date".
    reset_at = state.update_checker.rate_limit_reset_at()
    if reset_at is not None:
        when = datetime.fromtimestamp(reset_at).strftime("%H:%M")
        state.log(
            f"GitHub has temporarily rate-limited update checks from this computer - "
            f"will try again after {when}.",
            "warning",
        )
        return

    def worker():
        apps = {
            app_id: (app.repo_owner, app.repo_name, app.installed_version)
            for app_id, app in state.app_manager.apps.items()
        }
        results = state.update_checker.check_all_updates(apps, force_refresh=force_refresh)

        updates_available = 0
        for app_id, update_info in results.items():
            app = state.app_manager.apps.get(app_id)
            if not app:
                continue
            app.latest_version = update_info.latest_version
            app.update_available = update_info.update_available
            if update_info.update_available:
                updates_available += 1
                clean_v = str(update_info.latest_version).lstrip("v")
                state.log(f"{app.name}: Update available v{clean_v}", "warning")

        if updates_available == 0:
            state.log("All applications are up to date", "success")
        else:
            state.log(f"{updates_available} update(s) available", "warning")

        state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})

    def _failed(exc: Exception):
        state.log(f"Update check failed: {classify(exc).message}", "error")

    threading.Thread(
        target=guarded(worker, "update_check", _failed), daemon=True
    ).start()


def _cancel_auto_shutdown(state: LauncherState):
    with state.auto_shutdown_lock:
        if state.auto_shutdown_timer is not None:
            state.auto_shutdown_timer.cancel()
            state.auto_shutdown_timer = None


def _schedule_auto_shutdown(state: LauncherState):
    def _fire():
        # A new tab may have connected during the grace window (e.g. a
        # reload) - only shut down if the launcher is still tab-less.
        if state.event_bus.subscriber_count() > 0:
            return
        # Work in progress outranks a missing tab. The disconnect may be a
        # laptop waking up, a proxy's idle timeout or a throttled background
        # tab - none of which are a reason to abort an install or kill a
        # sub-app that's in the middle of a job. Re-check after another grace
        # window instead of shutting down.
        if state.install_in_progress:
            _schedule_auto_shutdown(state)
            return
        if state.app_manager and state.app_manager.get_running_apps():
            _schedule_auto_shutdown(state)
            return
        state.log("No browser tab connected - shutting down launcher and all running apps", "warning")
        if state.app_manager:
            state.app_manager.stop_all_apps()
        state.stop_event.set()
        if state.server is not None:
            state.server.shutdown()

    with state.auto_shutdown_lock:
        if state.auto_shutdown_timer is not None:
            state.auto_shutdown_timer.cancel()
        state.auto_shutdown_timer = threading.Timer(AUTO_SHUTDOWN_GRACE_SECONDS, _fire)
        state.auto_shutdown_timer.daemon = True
        state.auto_shutdown_timer.start()


def create_app(state: LauncherState) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )

    @app.route("/")
    def index():
        from flask import render_template
        return render_template("index.html")

    @app.route("/api/state")
    def get_state():
        if state.hardware_info is None:
            python_exe = state.env_manager.python_executable if state.env_manager and state.env_manager.python_available() else None
            state.hardware_info = detect_hardware(python_exe)
        return jsonify({
            "launcher_version": state.launcher_version,
            "developer_mode": DEVELOPER_MODE,
            "hardware": state.hardware_info.to_dict(),
            # Deliberately not fetched here: this route is hit on every
            # splash-screen load, SSE reconnect and job-finished re-sync, and
            # wikiquote.org can be slow or unreachable - the frontend already
            # falls back to its own async /api/quote/wikiquote call when
            # pop_quote is absent, so blocking every /api/state on it just
            # to save that one extra request was pure latency for nothing.
            "env": (
                state.env_manager.env_state() if state.env_manager
                else {"status": "absent", "ready": False, "exists": False,
                      "reason": "Launcher still initializing", "python_executable": None}
            ),
            "apps": state.apps_snapshot(),
            "console": list(state.console_log),
            "models": model_cache_snapshot(state),
            # Lets a reloaded tab rejoin work that's already running instead of
            # offering to start it a second time.
            "jobs": state.jobs_snapshot(),
        })

    @app.route("/api/quote/wikiquote")
    @app.route("/api/quote/pop")
    def get_wikiquote_route():
        force_refresh = request.args.get("refresh") in ("1", "true")
        return jsonify(fetch_live_wikiquote(force_refresh=force_refresh))

    @app.route("/api/hardware")
    def get_hardware():
        if state.hardware_info is None:
            state.hardware_info = detect_hardware()
        return jsonify(state.hardware_info.to_dict())

    @app.route("/api/apps")
    def list_apps():
        return jsonify(state.apps_snapshot())

    @app.route("/api/changelog")
    def get_changelog():
        releases_data = {}
        # 1. Launcher release info
        launcher_release = state.update_checker.get_latest_release("lrncrd", "PyPottery")
        releases_data["launcher"] = {
            "name": "PyPottery Launcher",
            "icon": "bi-collection",
            "logo_path": "imgs/Logo.png",
            "current_version": str(state.launcher_version).lstrip("v"),
            "latest_version": str(launcher_release.tag_name).lstrip("v") if launcher_release else str(state.launcher_version).lstrip("v"),
            "release_notes": launcher_release.body if launcher_release and launcher_release.body else "PyPottery Suite unified launcher.",
            "published_at": launcher_release.published_at if launcher_release else "",
            "html_url": launcher_release.html_url if launcher_release else "https://github.com/lrncrd/PyPottery",
        }
        # 2. Sub-apps release info
        if state.app_manager:
            for app_id, app in state.app_manager.apps.items():
                rel = state.update_checker.get_latest_release(app.repo_owner, app.repo_name)
                curr_v = str(app.installed_version).lstrip("v") if app.installed_version else "Not installed"
                latest_v = str(rel.tag_name).lstrip("v") if rel and rel.tag_name else "unknown"
                docs_notes = (state.update_checker.get_docs_release_notes(app_id, rel.tag_name)
                              if rel and rel.tag_name else None)
                releases_data[app_id] = {
                    "name": app.name,
                    "icon": app.icon,
                    "logo_path": app.logo_path or f"imgs/Logo{app_id.replace('PyPottery', '')}.png",
                    "current_version": curr_v,
                    "latest_version": latest_v,
                    "release_notes": docs_notes or (rel.body if rel and rel.body else "No release notes available for this release."),
                    "published_at": rel.published_at if rel else "",
                    "html_url": rel.html_url if rel else f"https://github.com/{app.repo_owner}/{app.repo_name}",
                }
        return jsonify(releases_data)

    @app.route("/api/apps/<app_id>/install", methods=["POST"])
    def install_app(app_id):
        if not state.app_manager or app_id not in state.app_manager.apps:
            return jsonify(success=False, error="Unknown application"), 404

        app_info = state.app_manager.apps[app_id]
        body = request.get_json(silent=True) or {}
        version = body.get("version")
        if not version:
            version = (
                app_info.latest_version
                if app_info.latest_version and app_info.latest_version != "unknown"
                else None
            )

        job_key = f"app:{app_id}"
        if not state.try_start_job(job_key, "app_install", f"Installing {app_info.name}"):
            return jsonify(**state.busy_response(job_key)), 409

        def worker():
            try:
                state.log(f"Installing {app_info.name}...", "info")
                if not state.app_manager.download_app(app_id, version):
                    state.log(f"{app_info.name} installation failed", "error")
                state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})
            finally:
                state.finish_job(job_key)

        def _failed(exc: Exception):
            state.log(f"Installing {app_info.name}: {classify(exc).message}", "error")

        threading.Thread(
            target=guarded(worker, f"install:{app_id}", _failed), daemon=True
        ).start()
        return jsonify(success=True), 202

    @app.route("/api/apps/<app_id>/update", methods=["POST"])
    def update_app(app_id):
        if not state.app_manager or app_id not in state.app_manager.apps:
            return jsonify(success=False, error="Unknown application"), 404

        app_info = state.app_manager.apps[app_id]
        if not app_info.update_available:
            return jsonify(success=False, error="No update available"), 409

        job_key = f"app:{app_id}"
        if not state.try_start_job(job_key, "app_update", f"Updating {app_info.name}"):
            return jsonify(**state.busy_response(job_key)), 409

        def worker():
            try:
                clean_v = str(app_info.latest_version).lstrip("v")
                state.log(f"Updating {app_info.name} to v{clean_v}...", "info")
                success = state.app_manager.download_app(app_id, app_info.latest_version)
                if success:
                    state.log(f"{app_info.name} updated successfully!", "success")
                else:
                    state.log(f"{app_info.name} update failed - the previous version is untouched", "error")
                state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})
            finally:
                state.finish_job(job_key)

        def _failed(exc: Exception):
            state.log(f"Updating {app_info.name}: {classify(exc).message}", "error")

        threading.Thread(
            target=guarded(worker, f"update:{app_id}", _failed), daemon=True
        ).start()
        return jsonify(success=True), 202

    @app.route("/api/apps/<app_id>/uninstall", methods=["POST"])
    def uninstall_app(app_id):
        if not state.app_manager or app_id not in state.app_manager.apps:
            return jsonify(success=False, error="Unknown application"), 404

        app_info = state.app_manager.apps[app_id]
        if not app_info.installed:
            return jsonify(success=False, error="Not installed"), 409

        job_key = f"app:{app_id}"
        if not state.try_start_job(job_key, "app_uninstall", f"Uninstalling {app_info.name}"):
            return jsonify(**state.busy_response(job_key)), 409

        def worker():
            try:
                success = state.app_manager.uninstall_app(app_id)
                if not success:
                    state.log(f"{app_info.name} could not be fully removed", "error")
                state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})
            finally:
                state.finish_job(job_key)

        def _failed(exc: Exception):
            state.log(f"Uninstalling {app_info.name}: {classify(exc).message}", "error")

        threading.Thread(
            target=guarded(worker, f"uninstall:{app_id}", _failed), daemon=True
        ).start()
        return jsonify(success=True), 202

    @app.route("/api/apps/<app_id>/launch", methods=["POST"])
    def launch_app(app_id):
        if not state.env_manager:
            return jsonify(success=False, error="Not initialized"), 409
        env = state.env_manager.env_state()
        if not env["ready"]:
            state.log(env["reason"], "error")
            return jsonify(success=False, code=env["status"], error=env["reason"]), 409
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        job_key = f"app:{app_id}"
        if state.jobs.get(job_key):
            return jsonify(**state.busy_response(job_key)), 409

        ok = state.app_manager.launch_app(app_id)
        app_info = state.app_manager.apps.get(app_id)
        if not ok:
            err = (app_info.last_error if app_info else None) or "Failed to start application"
            return jsonify(success=False, error=err, app=serialize_app(app_info) if app_info else None), 409
        return jsonify(success=True, app=serialize_app(app_info) if app_info else None)

    @app.route("/api/apps/<app_id>/stop", methods=["POST"])
    def stop_app(app_id):
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        ok = state.app_manager.stop_app(app_id)
        app_info = state.app_manager.apps.get(app_id)
        if not ok:
            err = (app_info.last_error if app_info else None) or f"Failed to stop {app_id}"
            return jsonify(success=False, error=err, app=serialize_app(app_info) if app_info else None), 409
        return jsonify(success=True, app=serialize_app(app_info) if app_info else None)

    @app.route("/api/apps/<app_id>/folder", methods=["POST"])
    def open_folder(app_id):
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        ok = state.app_manager.open_app_folder(app_id)
        return jsonify(success=ok)

    # ---- Project backup (export / import) ----------------------------------

    def _backup_app_paths(installed_only: bool = True) -> dict:
        manager = state.app_manager
        return {
            app_id: manager._app_path(app_id)
            for app_id, info in manager.apps.items()
            if info.installed or not installed_only
        }

    def _app_is_busy(app_id: str) -> Optional[str]:
        """Why projects of this app can't be written to right now, if they can't."""
        manager = state.app_manager
        if manager.get_app_status(app_id).is_running:
            return f"{manager.apps[app_id].name} is running - stop it first."
        if state.jobs.get(f"app:{app_id}"):
            return f"{manager.apps[app_id].name} is being installed or updated - try again in a moment."
        return None

    @app.route("/api/projects")
    def list_backup_projects():
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        projects = project_backup.list_projects(_backup_app_paths())
        for project in projects:
            project["app_name"] = state.app_manager.apps[project["app_id"]].name
        return jsonify(success=True, projects=projects)

    @app.route("/api/projects/export", methods=["POST"])
    def export_backup():
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        body = request.get_json(silent=True) or {}
        selection = body.get("selection")
        if not isinstance(selection, dict) or not any(selection.values()):
            return jsonify(success=False, error="Select at least one project to export."), 400
        selection = {a: list(ids) for a, ids in selection.items() if isinstance(ids, list) and ids}

        manager = state.app_manager
        handle, tmp_name = tempfile.mkstemp(prefix="pypottery_backup_", suffix=".zip")
        os.close(handle)
        tmp_path = Path(tmp_name)
        try:
            project_backup.export_projects(
                _backup_app_paths(),
                selection,
                tmp_path,
                launcher_version=state.launcher_version,
                app_versions={a: (i.installed_version or "") for a, i in manager.apps.items()},
            )
        except project_backup.BackupError as exc:
            tmp_path.unlink(missing_ok=True)
            return jsonify(success=False, error=str(exc)), 400
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        count = sum(len(ids) for ids in selection.values())
        state.log(f"Exported {count} project{'s' if count != 1 else ''} to a backup file", "success")
        response = send_file(
            tmp_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"PyPottery-backup-{datetime.now().strftime('%Y%m%d-%H%M')}.zip",
        )
        response.call_on_close(lambda: tmp_path.unlink(missing_ok=True))
        return response

    @app.route("/api/projects/import/inspect", methods=["POST"])
    def inspect_backup():
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify(success=False, error="Choose a backup file first."), 400

        token, path = state.pending_imports.new_path()
        try:
            upload.save(path)
            info = project_backup.inspect_backup(path, _backup_app_paths(installed_only=False))
        except project_backup.BackupError as exc:
            state.pending_imports.discard(token)
            return jsonify(success=False, error=str(exc)), 400
        except Exception:
            state.pending_imports.discard(token)
            raise

        installed = _backup_app_paths()
        for project in info["projects"]:
            project["app_name"] = state.app_manager.apps[project["app_id"]].name
            project["installed"] = project["app_id"] in installed
            project["busy"] = _app_is_busy(project["app_id"]) if project["installed"] else None
        return jsonify(success=True, token=token, **info)

    @app.route("/api/projects/import/apply", methods=["POST"])
    def apply_backup():
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        body = request.get_json(silent=True) or {}
        token = body.get("token") or ""
        path = state.pending_imports.get(token)
        if path is None:
            return jsonify(success=False, error="The uploaded backup expired - choose the file again."), 410
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return jsonify(success=False, error="Select at least one project to import."), 400

        installed = _backup_app_paths()
        usable, refused = [], []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            app_id = choice.get("app_id")
            if app_id not in state.app_manager.apps:
                problem = "Unknown application."
            elif app_id not in installed:
                problem = f"{state.app_manager.apps[app_id].name} is not installed - install it first."
            else:
                problem = _app_is_busy(app_id)
            if problem:
                refused.append({"app_id": app_id, "project_id": choice.get("project_id"),
                                "status": "error", "message": problem})
            else:
                usable.append(choice)

        try:
            results = (
                project_backup.apply_backup(path, _backup_app_paths(installed_only=False), usable)
                if usable else []
            )
        except project_backup.BackupError as exc:
            return jsonify(success=False, error=str(exc)), 400
        results += refused

        state.pending_imports.discard(token)
        done = sum(1 for r in results if r["status"] in ("imported", "renamed"))
        state.log(f"Imported {done} project{'s' if done != 1 else ''} from a backup file",
                  "success" if done else "warning")
        return jsonify(success=True, results=results)

    @app.route("/api/projects/import/cancel", methods=["POST"])
    def cancel_backup_import():
        body = request.get_json(silent=True) or {}
        state.pending_imports.discard(body.get("token") or "")
        return jsonify(success=True)

    @app.route("/api/env/status")
    def env_status():
        if not state.env_manager:
            return jsonify({"status": "absent", "ready": False, "exists": False,
                            "reason": "Launcher still initializing", "python_executable": None})
        return jsonify(state.env_manager.env_state())

    @app.route("/api/env/setup", methods=["POST"])
    def env_setup():
        if DEVELOPER_MODE:
            state.log("Setup skipped: Developer mode is active and using terminal Python", "info")
            return jsonify(success=True, message="Developer mode is active; using terminal Python", env=state.env_manager.env_state() if state.env_manager else None)
        if not state.env_manager:
            return jsonify(success=False, error="Not initialized"), 409
        if not state.hardware_info:
            return jsonify(success=False, error="Hardware detection still in progress - try again in a moment"), 409
        if not state.requirements_file.exists():
            state.log(f"Requirements file not found: {state.requirements_file}", "error")
            return jsonify(success=False, error="Requirements file not found"), 400

        # Optional override: {"pytorch_variant": "cpu"} forces a CPU-only
        # install regardless of what auto-detection recommended (Windows UI
        # toggle). Anything else (missing body, "auto", ...) keeps today's
        # fully-automatic behavior. state.hardware_info itself is left
        # untouched - it stays the source of truth for detected hardware.
        body = request.get_json(silent=True) or {}
        pytorch_variant = body.get("pytorch_variant", "auto")
        effective_hw = (
            dataclasses.replace(state.hardware_info, recommended_pytorch_variant="cpu", pytorch_index_url=None)
            if pytorch_variant == "cpu"
            else state.hardware_info
        )

        # A venv that exists but isn't usable (interpreter missing, a dangling
        # symlink left by an AppImage's temporary mount, an install that died
        # halfway) has to be torn down first: creating "over" it silently
        # keeps the broken parts.
        env_state = state.env_manager.env_state()
        force_recreate = bool(body.get("repair")) or env_state["status"] in ("broken", "incomplete")

        if not state.try_start_job("env", "env_setup", "Environment setup"):
            return jsonify(**state.busy_response("env")), 409

        def worker():
            try:
                state.log("Starting environment setup...", "info")
                if force_recreate and env_state["status"] != "absent":
                    state.log("Existing environment is incomplete - rebuilding it from scratch", "warning")
                success = state.env_manager.full_install(
                    effective_hw, state.requirements_file, force_recreate=force_recreate
                )
                if success:
                    state.log("Environment setup complete!", "success")
                    state.app_manager = AppManager(
                        state.base_path, state.env_manager.python_executable, developer_mode=DEVELOPER_MODE
                    )
                    state.app_manager.set_status_callback(
                        lambda app_id, message: _on_app_status(state, app_id, message)
                    )
                    state.app_manager.set_download_callback(
                        lambda progress: _on_download_progress(state, progress)
                    )
                else:
                    state.log("Environment setup failed", "error")
                state.emit({"type": "env_status", **state.env_manager.env_state()})
                state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})
            finally:
                state.finish_job("env")

        def _failed(exc: Exception):
            # full_install itself catches most things; this covers the rest so
            # the modal doesn't spin forever on an unexpected crash.
            state.env_manager._report_progress(
                "dependencies", classify(exc).message, 0, is_error=True
            )

        threading.Thread(
            target=guarded(worker, "env_setup", _failed), daemon=True
        ).start()
        return jsonify(success=True), 202

    @app.route("/api/env/verify", methods=["POST"])
    def env_verify():
        # python_available(), not venv_exists(): verifying a suspect
        # environment is precisely what this is for.
        if not state.env_manager or not state.env_manager.python_available():
            state.log("Environment not set up", "error")
            return jsonify(success=False, error="Environment not set up"), 409

        state.log("Verifying PyTorch installation...", "info")
        success, message = state.env_manager.verify_pytorch_installation()
        if success:
            state.log("PyTorch verification passed!", "success")
            for line in message.strip().split("\n"):
                state.log(f"  {line}", "info")
        else:
            # The raw output here is a Python traceback - useful in the log,
            # unreadable in the UI.
            logger.error("PyTorch verification failed:\n%s", message)
            state.log(
                "PyTorch verification failed - the environment looks incomplete. "
                "Try Repair Environment (details in the log file).",
                "error",
            )
        return jsonify(success=success, message=message)

    @app.route("/api/logs/open", methods=["POST"])
    def open_logs():
        log_dir = get_log_dir()
        if not log_dir:
            return jsonify(success=False, error="No log directory available"), 404
        return jsonify(success=open_path(log_dir), path=str(log_dir))

    @app.route("/api/data-folder/open", methods=["POST"])
    def open_data_folder():
        return jsonify(success=open_path(state.base_path), path=str(state.base_path))

    @app.route("/api/logs/tail")
    def tail_logs():
        """Last lines of the log, for when the user can't reach the folder."""
        log_dir = get_log_dir()
        log_file = (log_dir / "launcher.log") if log_dir else None
        if not log_file or not log_file.exists():
            return jsonify(success=False, error="No log file yet"), 404
        try:
            limit = max(1, min(int(request.args.get("n", 300)), 2000))
        except ValueError:
            limit = 300
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as handle:
                lines = collections.deque(handle, maxlen=limit)
        except OSError as e:
            return jsonify(success=False, error=str(e)), 500
        return jsonify(success=True, path=str(log_file), lines=[line.rstrip() for line in lines])

    @app.route("/api/models")
    def list_models():
        return jsonify(model_cache_snapshot(state))

    @app.route("/api/models/delete", methods=["POST"])
    def delete_model():
        body = request.get_json(silent=True) or {}
        rel_path = body.get("path")
        if not rel_path:
            return jsonify(success=False, error="path required"), 400

        cache_root = (state.base_path / MODEL_CACHE_DIRNAME).resolve()
        target = (cache_root / rel_path).resolve()
        try:
            target.relative_to(cache_root)
        except ValueError:
            return jsonify(success=False, error="invalid path"), 400

        if not target.exists():
            return jsonify(success=False, error="not found"), 404

        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        except OSError as e:
            state.log(f"Failed to delete cached model {rel_path}: {e}", "error")
            return jsonify(success=False, error=str(e)), 500

        state.log(f"Deleted cached model: {rel_path}", "success")
        snapshot = model_cache_snapshot(state)
        state.emit({"type": "models_refresh", **snapshot})
        return jsonify(success=True, **snapshot)

    @app.route("/api/updates/check", methods=["POST"])
    def updates_check():
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        threading.Thread(
            target=guarded(_check_for_updates, "updates_check"),
            args=(state,), kwargs={"force_refresh": True}, daemon=True,
        ).start()
        return jsonify(success=True), 202

    @app.route("/api/launcher/update", methods=["POST"])
    def launcher_update():
        body = request.get_json(silent=True) or {}
        version = body.get("version")
        if not version:
            return jsonify(success=False, error="version required"), 400

        # A frozen exe, an AppImage or a .app bundle can't rewrite itself from
        # the inside: the old code would keep running and the "update" would
        # silently do nothing (or make the launcher vanish). Say so instead.
        if not state.updater.can_self_update():
            return jsonify(
                success=False,
                code="manual_update",
                error="This build updates by downloading the new version.",
                release_url=state.updater.release_page_url(),
            ), 409

        if not state.try_start_job("launcher_update", "launcher_update", "Launcher update"):
            return jsonify(**state.busy_response("launcher_update")), 409

        def worker():
            clean_v = str(version).lstrip("v")
            state.log(f"Updating launcher to v{clean_v}...", "info")

            def progress_cb(prog: LauncherProgress):
                state.emit({
                    "type": "launcher_update_progress",
                    "stage": prog.stage,
                    "message": prog.message,
                    "bytes_downloaded": prog.bytes_downloaded,
                    "bytes_total": prog.bytes_total,
                    "percent": prog.percent,
                    "error": prog.error,
                })
                state.log(prog.message, "error" if prog.error else "info")

            success = state.updater.update(version, progress_callback=progress_cb)

            if success:
                state.log("Launcher update successful! Preparing to restart...", "success")
                state.emit({
                    "type": "launcher_update_progress",
                    "stage": "restarting",
                    "message": "Update complete! Restarting launcher...",
                    "percent": 100,
                    "error": False,
                })

                # Give frontend a moment to receive SSE event and initiate polling
                time.sleep(1.5)

                # Stop all sub-apps gracefully before restarting
                if state.app_manager:
                    state.app_manager.stop_all_apps()

                python_exe = (
                    state.env_manager.python_executable
                    if (state.env_manager and state.env_manager.python_available())
                    else None
                )

                # Only shut ourselves down once the replacement is actually
                # running - otherwise the launcher just disappears and the
                # user is left staring at "Restart complete, reload the page".
                if state.updater.spawn_new_instance(python_executable=python_exe):
                    state.finish_job("launcher_update")
                    state.stop_event.set()
                    if state.server is not None:
                        state.server.shutdown()
                    return

                state.log(
                    "Update installed, but the launcher could not restart itself - "
                    "close this window and start PyPottery again.",
                    "warning",
                )
                state.emit({
                    "type": "launcher_update_progress",
                    "stage": "error",
                    "message": "Update installed. Please close and reopen PyPottery to finish.",
                    "percent": 100,
                    "error": True,
                })
            else:
                state.log("Launcher update failed", "error")
                state.emit({
                    "type": "launcher_update_progress",
                    "stage": "error",
                    "message": "Launcher update failed. Check console log for details.",
                    "percent": 0,
                    "error": True,
                })
            state.finish_job("launcher_update")

        def _failed(exc: Exception):
            state.finish_job("launcher_update")
            state.emit({
                "type": "launcher_update_progress",
                "stage": "error",
                "message": classify(exc).message,
                "percent": 0,
                "error": True,
            })

        threading.Thread(
            target=guarded(worker, "launcher_update", _failed), daemon=True
        ).start()
        return jsonify(success=True), 202

    @app.route("/api/shutdown", methods=["POST"])
    def shutdown():
        if state.app_manager:
            state.app_manager.stop_all_apps()
        state.stop_event.set()

        def do_shutdown():
            time.sleep(0.3)
            if state.server is not None:
                state.server.shutdown()

        threading.Thread(target=do_shutdown, daemon=True).start()
        return jsonify(success=True)

    @app.route("/api/events")
    def sse_events():
        def generate():
            q = state.event_bus.subscribe()
            # A tab (re)connected - if a shutdown was pending from a
            # previously-last tab closing, call it off.
            _cancel_auto_shutdown(state)
            try:
                while True:
                    try:
                        event = q.get(timeout=25)
                        yield f"data: {json.dumps(event)}\n\n"
                    except queue.Empty:
                        # A real event, not an SSE comment: the browser can
                        # time it and tell "quiet" apart from "the launcher
                        # died" - a comment reaches no JS handler.
                        yield f"data: {json.dumps({'type': 'ping'})}\n\n"
            except GeneratorExit:
                pass
            finally:
                state.event_bus.unsubscribe(q)
                if state.event_bus.subscriber_count() == 0:
                    _schedule_auto_shutdown(state)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.route("/assets/<path:filename>")
    def assets(filename):
        allowed = (
            filename.startswith("imgs/")
            or (filename.startswith("apps/") and "/imgs/" in filename)
            or filename in ("icon_app.png", "icon_app.ico")
        )
        if not allowed:
            abort(404)

        # Sub-app logos live with the downloaded apps (writable data); the
        # launcher's own images ship with the application itself. On macOS
        # those are now two different directories.
        roots = (
            [state.base_path] if filename.startswith("apps/")
            else [state.resource_path, state.base_path]
        )

        for root in roots:
            root = Path(root).resolve()
            full_path = (root / filename).resolve()
            try:
                full_path.relative_to(root)
            except ValueError:
                continue
            if full_path.exists():
                return send_from_directory(root, filename)

        abort(404)

    @app.errorhandler(404)
    def handle_404(_error):
        return jsonify(success=False, code="not_found", error="Not found"), 404

    @app.errorhandler(405)
    def handle_405(_error):
        return jsonify(success=False, code="method_not_allowed", error="Method not allowed"), 405

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        # Without this Flask returns an HTML error page, which the frontend
        # then fails to parse as JSON - turning any backend bug into a
        # baffling "Unexpected token '<'" in the UI.
        logger.exception("Unhandled error serving %s", request.path)
        failure = classify(error)
        return jsonify(success=False, code=failure.code, error=failure.message), 500

    return app
