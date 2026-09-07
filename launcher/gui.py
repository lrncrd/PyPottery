"""
PyPottery Suite Launcher - Entry Point
Starts the launcher's local Flask server and opens it in the default browser,
the same pattern used by the PyPottery sub-apps (PyPotteryLayout/Lens/Ink).
"""

import atexit
import logging
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Add repo root to path so `launcher` is importable as a package
sys.path.insert(0, str(Path(__file__).parent.parent))

from werkzeug.serving import make_server

from launcher.instance_lock import InstanceLock, probe, read_existing_instance
from launcher.logging_setup import bind_base_path, get_log_dir, guarded, init_logging
from launcher.web_server import LauncherState, create_app, initialize_state

DEFAULT_PORT = 5099

logger = logging.getLogger("launcher.gui")


class NoFreePortError(RuntimeError):
    """Every candidate port was taken - the launcher cannot serve its UI."""


def _find_available_port(preferred_port: int, max_attempts: int = 20) -> int:
    """Find an available port starting from preferred_port."""
    for p in range(preferred_port, preferred_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise NoFreePortError(
        f"No free port found in range {preferred_port}-{preferred_port + max_attempts - 1}"
    )


def _show_fatal_dialog(message: str):
    """
    Last-resort way to tell the user something went wrong.

    Packaged builds have no console, so a crash before the browser opens is
    otherwise completely invisible - the app just never appears.
    """
    try:
        system = platform.system()
        if system == "Windows":
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, "PyPottery Launcher", 0x10)
        elif system == "Darwin":
            subprocess.run(
                ["osascript", "-e",
                 f'display alert "PyPottery Launcher" message "{message}" as critical'],
                capture_output=True, timeout=30,
            )
        else:
            for cmd in (["zenity", "--error", f"--text={message}"],
                        ["notify-send", "PyPottery Launcher", message]):
                try:
                    subprocess.run(cmd, capture_output=True, timeout=30)
                    break
                except FileNotFoundError:
                    continue
    except Exception:
        logger.exception("Could not display the error dialog")


def _get_port() -> int:
    env_port = os.environ.get("PYPOTTERY_LAUNCHER_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            return DEFAULT_PORT
    return _find_available_port(DEFAULT_PORT)


# Everything the launcher writes: the Python venv, downloaded sub-apps, the
# model cache, logs. Kept separate from the resources it only reads, because
# on macOS the two must not be the same place (see get_base_path).
_USER_DATA_DIRNAME = "pypottery"
_MIGRATED_DIRS = ("pypottery_env", "apps", "model_cache", "shared_assets", "python_runtime")


def get_resource_path() -> Path:
    """
    Where the app's own read-only files live (imgs/, icons, requirements.txt).
    Always inside the installation itself, which may be read-only.
    """
    return Path(__file__).parent.parent


def _is_macos_app_bundle(resource_dir: Path) -> bool:
    return (
        sys.platform == "darwin"
        and resource_dir.name == "Resources"
        and resource_dir.parent.name == "Contents"
    )


def _migrate_bundle_data(old_dir: Path, new_dir: Path):
    """
    One-time move of data written by older versions inside the .app bundle.

    Anything left in there would be destroyed the moment the user replaces the
    app with a newer download, so it has to come out - but a failure here must
    not stop the launcher: the environment-state check will spot whatever
    didn't make it and offer a repair.
    """
    for name in _MIGRATED_DIRS:
        source = old_dir / name
        target = new_dir / name
        if not source.exists() or target.exists():
            continue
        try:
            logger.info("Migrating %s out of the app bundle", name)
            shutil.move(str(source), str(target))
        except Exception:
            logger.exception("Could not migrate %s out of the app bundle", name)


def get_base_path() -> Path:
    """
    Get base directory for user data, virtual environments, downloaded sub-apps,
    and model caches.

    macOS: never inside the .app bundle. A bundle is replaced wholesale when the
    user installs a new version (and is read-only when run from a .dmg or under
    Gatekeeper's App Translocation), so data kept in there is lost on update.
    It goes to ~/Library/Application Support instead, the platform convention.

    AppImage: next to the .AppImage file, since the image itself is a read-only
    mount at a path that changes on every run.

    Windows/Linux otherwise: alongside the application, so the whole install
    stays portable in one folder - falling back to a user directory if that
    location turns out not to be writable.
    """
    resource_dir = get_resource_path()

    if _is_macos_app_bundle(resource_dir):
        data_dir = Path.home() / "Library" / "Application Support" / "PyPottery"
        data_dir.mkdir(parents=True, exist_ok=True)
        _migrate_bundle_data(resource_dir, data_dir)
        return data_dir

    appimage_path = os.environ.get("APPIMAGE")
    if appimage_path:
        appimage_dir = Path(appimage_path).parent
        if os.access(appimage_dir, os.W_OK):
            return appimage_dir
        user_dir = Path.home() / ".local" / "share" / _USER_DATA_DIRNAME
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    if not os.access(resource_dir, os.W_OK):
        user_dir = Path.home() / ".local" / "share" / _USER_DATA_DIRNAME
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    return resource_dir


def main():
    """Main entry point"""
    init_logging()
    try:
        _run()
    except NoFreePortError:
        logger.exception("Startup failed: no free port")
        _show_fatal_dialog(
            "PyPottery Launcher could not start because no network port was "
            "available.\n\nClose other copies of PyPottery (or restart your "
            "computer) and try again."
        )
        raise SystemExit(1)
    except Exception:
        logger.exception("Startup failed")
        log_dir = get_log_dir()
        where = f"\n\nDetails were written to:\n{log_dir}" if log_dir else ""
        _show_fatal_dialog(f"PyPottery Launcher could not start.{where}")
        raise SystemExit(1)


def _defer_to_existing_instance(base_path: Path):
    """
    Another launcher process already holds the instance lock for this
    base_path. Rather than starting a second copy that would race the first
    over the same venv and app installs, find it and hand off to it.
    """
    info = read_existing_instance(base_path)
    port = info.get("port") if info else None

    if port and probe(port):
        logger.info("Another instance is already running on port %s - opening it instead", port)
        webbrowser.open(f"http://127.0.0.1:{port}/")
        return

    # The lock is held (so some process still has the file open) but it
    # isn't answering - most likely starting up, hung, or a deadlock. A
    # crashed process would have already released the OS-level lock, so this
    # is deliberately NOT treated as "stale and safe to steal": starting a
    # second instance against a venv the first one might still be writing to
    # is exactly the failure mode this lock exists to prevent.
    logger.warning(
        "Another PyPottery Launcher process appears to be running (pid=%s) but "
        "isn't responding yet - not starting a second instance.",
        info.get("pid") if info else "unknown",
    )
    _show_fatal_dialog(
        "PyPottery Launcher is already starting or running.\n\n"
        "If you don't see it, wait a few seconds and check for an existing "
        "browser tab or taskbar icon before trying again."
    )


def _run():
    base_path = get_base_path()
    bind_base_path(base_path)
    logger.info("Base path: %s", base_path)

    lock = InstanceLock(base_path)
    if not lock.acquire():
        _defer_to_existing_instance(base_path)
        return

    # Ensure offline vendor assets (Bootstrap, Icons, Fonts) are present and synced
    try:
        from launcher.vendor_assets_manager import VendorAssetsManager
        v_mgr = VendorAssetsManager(base_path)
        v_mgr.sync_to_app(Path(__file__).parent)
    except Exception:
        logger.exception("Vendor assets setup failed - the UI may render unstyled")

    state = LauncherState(base_path)

    flask_app = create_app(state)

    port = _get_port()
    try:
        server = make_server("127.0.0.1", port, flask_app, threaded=True)
    except OSError:
        # The port was free a moment ago but isn't any more (or was forced via
        # PYPOTTERY_LAUNCHER_PORT and is taken) - look for another one.
        logger.warning("Port %s unavailable, searching for another", port, exc_info=True)
        port = _find_available_port(port + 1)
        server = make_server("127.0.0.1", port, flask_app, threaded=True)

    state.server = server
    url = f"http://127.0.0.1:{port}/"
    lock.write_info(port)

    def _stop_everything(*_args):
        # Sub-apps are launched detached (new console/session) so they outlive
        # the launcher process unless we stop them explicitly here.
        if state.app_manager:
            state.app_manager.stop_all_apps()
        lock.release()

    atexit.register(_stop_everything)

    def _signal_handler(signum, frame):
        _stop_everything()
        os._exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _signal_handler)
        except (ValueError, OSError, AttributeError):
            pass  # Not available/settable on this platform - atexit still covers normal exit

    def _init_failed(exc: Exception):
        # Without this the UI just sits on "No applications configured" with no
        # hint that startup blew up behind it.
        state.log(f"Launcher initialization failed: {exc}", "error")
        state.emit({"type": "init_failed", "message": str(exc)})

    threading.Thread(
        target=guarded(initialize_state, "initialize_state", _init_failed),
        args=(state,), daemon=True,
    ).start()

    def _open_browser():
        time.sleep(1.5)
        if webbrowser.open(url):
            return
        # No usable browser (common on a bare Linux box): the server is running
        # but the user has no way to know where. Leave the address behind.
        logger.warning("Could not open a browser automatically - open %s manually", url)
        log_dir = get_log_dir()
        if log_dir:
            try:
                (log_dir / "OPEN_ME.txt").write_text(
                    f"PyPottery Launcher is running.\nOpen this address in your browser:\n\n{url}\n",
                    encoding="utf-8",
                )
            except OSError:
                logger.exception("Could not write OPEN_ME.txt")

    threading.Thread(target=guarded(_open_browser, "open_browser"), daemon=True).start()

    logger.info("PyPottery Suite Launcher v%s running at %s", state.launcher_version, url)
    print(f"PyPottery Suite Launcher v{state.launcher_version} running at {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _stop_everything()


if __name__ == "__main__":
    main()

