"""
PyPottery Suite Launcher - Entry Point
Starts the launcher's local Flask server and opens it in the default browser,
the same pattern used by the PyPottery sub-apps (PyPotteryLayout/Lens/Ink).
"""

import atexit
import os
import signal
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Add repo root to path so `launcher` is importable as a package
sys.path.insert(0, str(Path(__file__).parent.parent))

from werkzeug.serving import make_server

from launcher.web_server import LauncherState, create_app, initialize_state

DEFAULT_PORT = 5099


def _find_available_port(preferred_port: int, max_attempts: int = 20) -> int:
    """Find an available port starting from preferred_port."""
    for p in range(preferred_port, preferred_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return preferred_port


def _get_port() -> int:
    env_port = os.environ.get("PYPOTTERY_LAUNCHER_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            return DEFAULT_PORT
    return _find_available_port(DEFAULT_PORT)


def main():
    """Main entry point"""
    base_path = Path(__file__).parent.parent
    state = LauncherState(base_path)
    flask_app = create_app(state)

    port = _get_port()
    try:
        server = make_server("127.0.0.1", port, flask_app, threaded=True)
    except OSError as e:
        # Fallback to searching another available port if the specified one fails
        port = _find_available_port(port + 1)
        server = make_server("127.0.0.1", port, flask_app, threaded=True)

    state.server = server
    url = f"http://127.0.0.1:{port}/"

    def _stop_everything(*_args):
        # Sub-apps are launched detached (new console/session) so they outlive
        # the launcher process unless we stop them explicitly here.
        if state.app_manager:
            state.app_manager.stop_all_apps()

    atexit.register(_stop_everything)

    def _signal_handler(signum, frame):
        _stop_everything()
        os._exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _signal_handler)
        except (ValueError, OSError, AttributeError):
            pass  # Not available/settable on this platform - atexit still covers normal exit

    threading.Thread(target=initialize_state, args=(state,), daemon=True).start()

    def _open_browser():
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    print(f"PyPottery Suite Launcher running at {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _stop_everything()


if __name__ == "__main__":
    main()

