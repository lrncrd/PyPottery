# Launcher release-hardening notes

Written during a pre-release audit of the PyPottery launcher (Windows /
macOS / Linux). Two lists: what was fixed, and what was deliberately left
for later so the fix didn't balloon into a rewrite of everything at once.

## Fixed in this pass

**Diagnosability**
- No log file existed anywhere; every packaged build runs without a console,
  so `print()` output and unhandled tracebacks were silently discarded.
  Added `launcher/logging_setup.py`: a rotating file log under the user's
  data directory (with a per-user fallback location so even a startup
  failure before `get_base_path()` is captured), `sys.excepthook` /
  `threading.excepthook`, a `faulthandler` dump, and a stdout/stderr shim for
  builds where those are `None`. "Open logs folder" button added to the
  console panel; `/api/logs/open` and `/api/logs/tail`.
- Sub-app output went to `DEVNULL` (Unix) or a console window nobody could
  retrieve output from (Windows). Now captured to `logs/apps/<id>.log`
  (`app_manager.py`'s `_open_app_log`/`_close_app_log`).
- Every background thread now goes through `logging_setup.guarded()`, which
  logs an unhandled exception instead of letting it die silently. This
  matters most for `initialize_state` (`web_server.py`), which previously
  left the UI on "No applications configured" with zero explanation if
  hardware detection raised.

**Installation errors reaching the user**
- `app.js`'s `handleEnvProgressEvent` checked `stage` before `is_error`;
  since backend errors always carry a stage, the error branch was
  unreachable. A failed install used to show "Installing PyTorch..."
  forever, with the Close button hidden on first run - no way out. Fixed the
  branch order; Close is now always available on error, and Retry reuses the
  PyTorch variant the user actually chose instead of silently reverting to
  "auto"/CUDA.
- `EnvironmentManager.venv_exists()` used to mean "the interpreter file
  exists," so a venv left half-installed (PyTorch download failed) reported
  "Active & Ready." Replaced with `env_state()` returning
  `absent`/`broken`/`incomplete`/`ready`, backed by a completion marker
  (`pypottery_env/.pypottery_env.json`) written only once a full install
  succeeds. The UI now shows "Incomplete - needs repair" and a **Repair
  Environment** button that rebuilds from scratch (`create_venv` no longer
  silently reuses a broken directory).
- Raw pip/uv output (sometimes hundreds of lines) used to go straight into
  the UI. `launcher/error_messages.py` maps common failure signatures
  (network, TLS/proxy interception, GitHub rate limiting, disk full,
  permissions, missing binary, timeout) to one actionable sentence; the full
  output still goes to the log file.
- Flask had no error handlers, so an unhandled route exception (e.g. a
  GitHub 403 propagating out of `/api/changelog`) returned an HTML page that
  broke the frontend's `.json()` parsing with "Unexpected token '<'". Added
  JSON 404/405/500 handlers.

**Concurrency**
- Env setup and per-app install/update had no guard: two tabs or an
  impatient double-click could run two `uv pip install` processes against
  the same site-packages at once. `LauncherState.jobs` now tracks
  in-progress work; routes return 409 while busy, and reloading the page
  reopens the installer modal against the real running job instead of
  offering to start a second one.

**Atomic sub-app installs**
- `download_app` used to delete the existing install *before* extracting,
  so a truncated download, a corrupt/empty zip, or a Windows file-lock on
  rename destroyed a working installation. Rewritten to stage into
  `apps/.staging/`, verify the download size and the extracted entry script,
  and swap only after everything checks out - the previous install is kept
  until the new one is confirmed good, with rollback on a failed swap.
- `stop_app` only terminated the direct child process; PyTorch dataloader/
  multiprocessing children were left orphaned. Now uses `psutil` (already a
  soft dependency) to terminate the whole tree, falling back to
  `taskkill /T` (Windows) / `os.killpg` (Unix).

**Cross-platform packaging**
- The AppImage installed `flask`/`psutil` at runtime into a read-only
  squashfs mount - it could never have worked. Now installed at build time
  (`build_unix_release.py`), same as the Windows WinPython package already
  did. Same fix for the macOS `.app`'s launch script.
- The AppImage's Python runs from `/tmp/.mount_XXXX/`, a path that changes
  every launch, so a venv built against it dangled on the next run.
  `EnvironmentManager.ensure_base_python()` now copies the bundled
  interpreter to a persistent `python_runtime/` next to the `.AppImage` on
  first setup and uses that as the venv base from then on.
- macOS user data (the venv, downloaded apps, model cache) lived inside the
  `.app` bundle - lost on every update (bundle replaced wholesale), broken
  when run from a mounted `.dmg` (read-only), and incompatible with future
  code-signing/notarization. Moved to
  `~/Library/Application Support/PyPottery`, with a one-time migration for
  existing installs (`gui.py`'s `get_base_path()`/`get_resource_path()`
  split). The translocation-handling script no longer `rm -rf`s an existing
  `/Applications` install - it offers to open the existing copy instead -
  and its dialogs are now in English.
- A frozen Windows exe / AppImage / `.app` cannot rewrite itself in place;
  the self-updater used to try anyway and either no-op silently or make the
  launcher vanish. `LauncherUpdater.can_self_update()` now detects this and
  `/api/launcher/update` responds with the release page URL instead.
- `updater.PRESERVED_PATHS` was missing `pypottery_env`, `python_runtime`
  and `logs` - an update could in principle have deleted the user's
  multi-GB environment. Added.

**Startup and connection robustness**
- `gui.py`: a port-search failure or a second `make_server()` failure used
  to crash with no window and no console. Now caught, logged, and shown via
  a best-effort native dialog (`MessageBoxW` / `osascript` / `zenity`).
  `webbrowser.open()`'s return value is now checked; on failure the URL is
  written to `logs/OPEN_ME.txt`.
- The SSE stream's `onerror` was an empty handler with no reconnect UX, and
  the auto-shutdown timer would tear down the launcher (and every running
  sub-app) whenever no tab was connected for 8s - including a laptop asleep
  mid-download or mid-inference. The server now sends a real `ping` event
  every 25s; the client watchdog surfaces a "Connection Lost" banner and
  forces a reconnect if the browser's own retry gives up. Auto-shutdown now
  also checks for running sub-apps, not just active installs.
- Frontend `fetch()` calls didn't check `response.ok` or catch network
  failures - clicking Launch with the port already in use showed an
  optimistic "Launching..." toast and then nothing. Added a shared `api()`
  helper used by the action buttons; failures now surface as a toast.

## Fixed in the follow-up pass

Closed out most of the previous round's "out of scope" list:

- **CUDA wheel mapping** (`hardware_detector.get_pytorch_recommendation`):
  added `cu128`, now the top preference. RTX 50-series (sm_120) GPUs get a
  wheel that actually has kernels for them instead of a cu126 build that
  installs cleanly and then fails at runtime. Verified with synthetic
  CUDA-version inputs (13.0 -> cu128, 12.6 -> cu126, 11.8 -> cu118 unaffected).
- **`HIP_PATH` false-positive on Windows** (`detect_amd_rocm`): the
  `HIP_PATH`/`/opt/rocm` fallback now only applies on non-Windows platforms -
  PyTorch ships no ROCm wheels for Windows at all, so trusting that variable
  there only ever pointed a real GPU at an install that hard-fails. Verified
  directly (`HIP_PATH` set + `platform.system()=="Windows"` -> `False`).
- **Uninstall app**: `AppManager.uninstall_app()` now goes through the same
  `_app_path()`/job-guard pattern as install/update, wired up at
  `POST /api/apps/<id>/uninstall`, with a trash-icon button on each app card
  (disabled while running) and a themed confirm dialog (the former
  `showGpuVariantModal` generalized into `showConfirmModal`, reused rather
  than duplicated). Verified live: install -> uninstall -> folder gone,
  `installed: false`; uninstalling an already-absent app cleanly 409s instead
  of erroring.
- **GitHub rate limiting**: `UpdateChecker` now recognizes a 403/429,
  remembers `X-RateLimit-Reset`, and backs off entirely (no network calls)
  until then instead of re-hitting the API - and failing - on every check.
  `_check_for_updates` logs a specific "paused until HH:MM" message and skips
  the misleading "All applications are up to date" it would otherwise log
  while actually rate-limited.
- **Wikiquote blocking `/api/state`**: the synchronous
  `fetch_live_wikiquote()` call was removed from `get_state()` - the
  frontend's existing async fallback (`fetchWikiquote()`) is now the only
  path, so a slow/unreachable wikiquote.org no longer adds latency to every
  splash load, SSE reconnect, and job-finished re-sync.
- **`requirements.txt` parsing** (`install_requirements`): lines starting
  with `-` (`-r`, `--extra-index-url`, `-e`, ...) are now collected
  separately and prepended to every batch instead of being split across
  batch boundaries or treated as package names; inline `# comments` are
  stripped per-line. Verified with a synthetic file mixing both against a
  mocked pip call.
- **Torch variant re-check**: after the dependency batches finish,
  `_reverify_pytorch_variant()` checks the CUDA build is still installed
  when it should be and reinstalls precisely `torch`/`torchvision`/
  `torchaudio` if a transitive dependency silently swapped in a CPU build.
- **Single-instance lock**: new `launcher/instance_lock.py` - an OS-level
  advisory lock (`msvcrt.locking` / `fcntl.flock`, self-releasing on crash,
  no separate staleness check needed) held for the life of the process. A
  second process finding it held reads the first instance's port from the
  lock file and opens a browser to it instead of starting a competing copy
  against the same venv. Verified live in all three scenarios: normal
  startup, second-instance deferral (confirmed it reads the right port and
  never binds one), and recovery after a hard-killed "crashed" instance
  (lock auto-released, next start is normal). Caught and fixed a real bug
  during that testing: Windows' byte-range locking is mandatory, not
  advisory, so a second process reading the locked byte from the lock file
  had its whole read rejected - fixed by keeping the locked byte (0) as a
  placeholder and starting the actual payload at offset 1.
- **macOS `Info.plist` version**: `CFBundleVersion`/`CFBundleShortVersionString`
  now read from `LAUNCHER_VERSION` via a copy of `build_windows_release.py`'s
  `_read_launcher_version()`, instead of a hardcoded `"1.0.2"`.
- **`restartPollActive` never reset**: now cleared when the restart poll
  gives up after 60 attempts, so a retried update can poll again without a
  full page reload.

## Still out of scope

- **Cross-building macOS/Linux packages from a different host OS**
  (`_install_launcher_deps`'s `--platform` wheel-resolution path) is
  implemented but untested against a real cross-build - verify before
  relying on it for a release pipeline. Low priority: native builds on all
  three platforms are available.
- Everything else previously listed here has been addressed above.
