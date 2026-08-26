"""
PyPottery Suite Launcher - Web Backend
Flask application exposing the launcher's hardware/environment/app-management
logic over HTTP + Server-Sent Events, for the browser-based launcher UI.
"""

import collections
import dataclasses
import json
import os
import queue
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from .app_manager import AppInfo, AppManager, DownloadProgress
from .environment_manager import EnvironmentManager, InstallProgress
from .hardware_detector import HardwareInfo, detect_hardware
from .update_checker import UpdateChecker
from .updater import LauncherProgress, LauncherUpdater
from .wikiquote_fetcher import fetch_live_wikiquote

try:
    # Gitignored, local-only switch - see dev_config.example.py. Missing on a
    # fresh clone, which is the normal (non-developer) case.
    from .dev_config import DEVELOPER_MODE
except ImportError:
    DEVELOPER_MODE = False

LAUNCHER_VERSION = "1.1.0"

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
        req = self.base_path / "requirements.txt"
        bundle_req = Path(__file__).parent.parent / "requirements.txt"
        self.requirements_file = bundle_req if (not req.exists() and bundle_req.exists()) else req
        self.launcher_version = LAUNCHER_VERSION

        self.event_bus = EventBus()
        self.console_log = collections.deque(maxlen=500)
        self.stop_event = threading.Event()

        # Guards the "shut down when the last browser tab disconnects" timer.
        self.auto_shutdown_timer: Optional[threading.Timer] = None
        self.auto_shutdown_lock = threading.Lock()

        self.hardware_info: Optional[HardwareInfo] = None
        self.env_manager: Optional[EnvironmentManager] = None
        self.app_manager: Optional[AppManager] = None
        self.update_checker = UpdateChecker()
        self.updater = LauncherUpdater(self.base_path)

        # Set by gui.py once the werkzeug server is created, so /api/shutdown
        # can stop it from a background thread (never from the serving thread).
        self.server = None

    def log(self, message: str, tag: str = "info"):
        entry = {
            "type": "console",
            "message": message,
            "tag": tag,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        self.console_log.append(entry)
        self.event_bus.publish(entry)

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
        "developer_mode": DEVELOPER_MODE,
    }


def initialize_state(state: LauncherState):
    """Detect hardware, wire up managers, start app monitoring. Run on a background thread."""
    state.log("Initializing PyPottery Suite Launcher...", "info")

    if DEVELOPER_MODE:
        state.log("Developer mode ON - sub-apps run from their local git checkouts", "warning")

    state.env_manager = EnvironmentManager(state.base_path)
    state.env_manager.set_progress_callback(lambda p: _on_env_progress(state, p))

    python_exe = state.env_manager.python_executable if state.env_manager.venv_exists() else None
    state.hardware_info = detect_hardware(python_exe)
    state.log("Hardware detection complete", "success")
    state.emit({"type": "hardware", "hardware": state.hardware_info.to_dict()})

    if not state.hardware_info.cuda_compatible and state.hardware_info.driver_warning:
        state.log("Incompatible NVIDIA driver detected", "warning")
        state.emit({"type": "driver_warning", "message": state.hardware_info.driver_warning})

    if state.env_manager.venv_exists():
        state.log("Python environment found", "success")
        state.log(f"Using Python: {state.env_manager.python_executable}", "info")
    else:
        state.log("Python environment not found - please run Setup", "warning")
        python_exe = Path(sys.executable)

    state.app_manager = AppManager(state.base_path, python_exe, developer_mode=DEVELOPER_MODE)
    state.app_manager.set_status_callback(lambda app_id, message: _on_app_status(state, app_id, message))
    state.app_manager.set_download_callback(lambda progress: _on_download_progress(state, progress))

    state.emit({"type": "env_status", "exists": state.env_manager.venv_exists()})
    state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})

    threading.Thread(target=_monitor_apps, args=(state,), daemon=True).start()

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
        python_exe = state.env_manager.python_executable if state.env_manager and state.env_manager.venv_exists() else None
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
        state.log(f"Failed to check launcher updates: {e}", "error")

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

    threading.Thread(target=worker, daemon=True).start()


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
        print("No browser tab connected - shutting down launcher and all running apps")
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
            python_exe = state.env_manager.python_executable if state.env_manager and state.env_manager.venv_exists() else None
            state.hardware_info = detect_hardware(python_exe)
        return jsonify({
            "launcher_version": state.launcher_version,
            "developer_mode": DEVELOPER_MODE,
            "hardware": state.hardware_info.to_dict(),
            "pop_quote": fetch_live_wikiquote(),
            "env": {
                "exists": bool(state.env_manager and state.env_manager.venv_exists()),
                "python_executable": (
                    str(state.env_manager.python_executable) if state.env_manager else None
                ),
            },
            "apps": state.apps_snapshot(),
            "console": list(state.console_log),
            "models": model_cache_snapshot(state),
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
            "icon": "🏺",
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
                releases_data[app_id] = {
                    "name": app.name,
                    "icon": app.icon,
                    "current_version": curr_v,
                    "latest_version": latest_v,
                    "release_notes": rel.body if rel and rel.body else "No release notes available for this release.",
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

        def worker():
            state.log(f"Installing {app_info.name}...", "info")
            state.app_manager.download_app(app_id, version)
            state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})

        threading.Thread(target=worker, daemon=True).start()
        return jsonify(success=True), 202

    @app.route("/api/apps/<app_id>/update", methods=["POST"])
    def update_app(app_id):
        if not state.app_manager or app_id not in state.app_manager.apps:
            return jsonify(success=False, error="Unknown application"), 404

        app_info = state.app_manager.apps[app_id]
        if not app_info.update_available:
            return jsonify(success=False, error="No update available"), 409

        def worker():
            clean_v = str(app_info.latest_version).lstrip("v")
            state.log(f"Updating {app_info.name} to v{clean_v}...", "info")
            success = state.app_manager.download_app(app_id, app_info.latest_version)
            if success:
                state.log(f"{app_info.name} updated successfully!", "success")
            state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})

        threading.Thread(target=worker, daemon=True).start()
        return jsonify(success=True), 202

    @app.route("/api/apps/<app_id>/launch", methods=["POST"])
    def launch_app(app_id):
        if not state.env_manager or not state.env_manager.venv_exists():
            state.log("Please set up environment first", "error")
            return jsonify(success=False, error="Environment not set up"), 409
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409

        ok = state.app_manager.launch_app(app_id)
        app_info = state.app_manager.apps.get(app_id)
        return jsonify(success=ok, app=serialize_app(app_info) if app_info else None)

    @app.route("/api/apps/<app_id>/stop", methods=["POST"])
    def stop_app(app_id):
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        ok = state.app_manager.stop_app(app_id)
        app_info = state.app_manager.apps.get(app_id)
        return jsonify(success=ok, app=serialize_app(app_info) if app_info else None)

    @app.route("/api/apps/<app_id>/folder", methods=["POST"])
    def open_folder(app_id):
        if not state.app_manager:
            return jsonify(success=False, error="Not initialized"), 409
        ok = state.app_manager.open_app_folder(app_id)
        return jsonify(success=ok)

    @app.route("/api/env/status")
    def env_status():
        return jsonify({
            "exists": bool(state.env_manager and state.env_manager.venv_exists()),
            "python_executable": (
                str(state.env_manager.python_executable) if state.env_manager else None
            ),
        })

    @app.route("/api/env/setup", methods=["POST"])
    def env_setup():
        if not state.env_manager:
            return jsonify(success=False, error="Not initialized"), 409
        if not state.requirements_file.exists():
            state.log(f"Requirements file not found: {state.requirements_file}", "error")
            return jsonify(success=False, error="Requirements file not found"), 400

        def worker():
            state.log("Starting environment setup...", "info")
            success = state.env_manager.full_install(state.hardware_info, state.requirements_file)
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
            state.emit({"type": "env_status", "exists": state.env_manager.venv_exists()})
            state.emit({"type": "apps_refresh", "apps": state.apps_snapshot()})

        threading.Thread(target=worker, daemon=True).start()
        return jsonify(success=True), 202

    @app.route("/api/env/verify", methods=["POST"])
    def env_verify():
        if not state.env_manager or not state.env_manager.venv_exists():
            state.log("Environment not set up", "error")
            return jsonify(success=False, error="Environment not set up"), 409

        state.log("Verifying PyTorch installation...", "info")
        success, message = state.env_manager.verify_pytorch_installation()
        if success:
            state.log("PyTorch verification passed!", "success")
            for line in message.strip().split("\n"):
                state.log(f"  {line}", "info")
        else:
            state.log(f"PyTorch verification failed: {message}", "error")
        return jsonify(success=success, message=message)

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
        threading.Thread(target=_check_for_updates, args=(state,), kwargs={"force_refresh": True}, daemon=True).start()
        return jsonify(success=True), 202

    @app.route("/api/launcher/update", methods=["POST"])
    def launcher_update():
        body = request.get_json(silent=True) or {}
        version = body.get("version")
        if not version:
            return jsonify(success=False, error="version required"), 400

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
                    if (state.env_manager and state.env_manager.venv_exists())
                    else None
                )

                # Spawn new launcher instance
                state.updater.spawn_new_instance(python_executable=python_exe)

                # Cleanly shut down current server
                state.stop_event.set()
                if state.server is not None:
                    state.server.shutdown()
            else:
                state.log("Launcher update failed", "error")
                state.emit({
                    "type": "launcher_update_progress",
                    "stage": "error",
                    "message": "Launcher update failed. Check console log for details.",
                    "percent": 0,
                    "error": True,
                })

        threading.Thread(target=worker, daemon=True).start()
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
                        yield ": keepalive\n\n"
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

        full_path = (state.base_path / filename).resolve()
        try:
            full_path.relative_to(state.base_path.resolve())
        except ValueError:
            abort(404)

        if not full_path.exists():
            abort(404)

        return send_from_directory(state.base_path, filename)

    return app
