# macOS & Linux build verification handoff

Everything below shipped and was verified on Windows this session (installer,
uninstaller, single-instance lock, icon). Both hardening passes also touched
macOS- and Linux-specific code paths - where the launcher's data directory
lives, how the AppImage's bundled Python survives a reboot, how Gatekeeper
translocation is handled - none of which can be exercised from a Windows
machine. This needs a native pass on each platform before the public release.

## macOS - `.app` + `.dmg`

Build: `python3 build_release/build_unix_release.py` (auto-detects
arm64/x86_64 from the host; needs Xcode Command Line Tools for `hdiutil`,
`sips`, `iconutil`, `osascript`)

**Data directory & migration**
- Fresh install: drag to `/Applications`, launch. `pypottery_env/`, `apps/`,
  `logs/` should appear under `~/Library/Application Support/PyPottery` -
  nothing writable should be created inside
  `PyPottery.app/Contents/Resources`. (`gui.py` - `get_base_path()`)
- Old-layout migration: manually create `pypottery_env/` inside an old
  app's `Contents/Resources` to simulate a pre-fix install, then launch the
  new build in its place. The folder should move to Application Support
  automatically, no re-install prompt. (`gui.py` - `_migrate_bundle_data()`)
- About modal -> Show Data Folder should open Finder directly on
  `~/Library/Application Support/PyPottery`.
  (`web_server.py` - `/api/data-folder/open`)

**Install & packaging**
- Environment setup shouldn't try to write into the read-only bundle -
  flask/psutil are already installed at build time, no permission errors in
  `logs/launcher.log`. (`build_unix_release.py` - `_install_launcher_deps()`)
- Mounting the `.dmg` again with a copy already at `/Applications` should
  offer "Open Existing App" / "Cancel" in English - not a silent `rm -rf` of
  the existing install.
- `plutil -p "PyPottery.app/Contents/Info.plist"`: `CFBundleVersion` /
  `CFBundleShortVersionString` should equal `LAUNCHER_VERSION` in
  `web_server.py`, not a hardcoded old value.
- Dock/Finder icon should be sharp at every size, including Quick Look (the
  source icon was regenerated this session as a true square - it previously
  carried a few stray pixels of non-square aspect ratio, which is what made
  it look soft at large sizes on Windows).

**Runtime behavior (platform-agnostic code, still worth one native pass)**
- Open the app, then launch it again: the second launch should open a
  browser tab on the already-running instance and quit - no second process,
  no port conflict. (`instance_lock.py`, `fcntl.flock` path)
- Click Quit: should show a themed confirm card (not the native browser
  popup), then a full-page "Launcher Terminated" screen using the same
  logo/gradient as the splash screen at startup.

## Linux - `.AppImage`

Build: `python3 build_release/build_unix_release.py` (auto-detects
`linux-x86_64`; needs `zip` on the build machine and `libfuse2` on the
machine that runs the resulting AppImage - most distros ship it, some newer
ones don't by default)

**AppImage runtime quirks**
- Run the AppImage, let it finish environment setup, close it, run it
  again. A `python_runtime/` folder should appear next to the `.AppImage`
  file after the first run, and the second launch should reuse the existing
  venv without re-installing anything. Before this fix the venv dangled
  because the AppImage's mount path (`/tmp/.mount_XXXX`) changes every run.
  (`environment_manager.py` - `ensure_base_python()`)
- Environment setup shouldn't try to write into the read-only squashfs
  mount - flask/psutil are already installed at build time.
- Running the bundled `install_desktop.sh` should create a working launcher
  entry in the application menu, pointing at the right `.AppImage` path.

**Runtime behavior (platform-agnostic code, still worth one native pass)**
- Same second-launch handoff test as macOS (`fcntl.flock` path).
- "Open logs folder" / "Show Data Folder" should open the distro's file
  manager on the right folder via `xdg-open`.
  (`process_utils.py` - `open_path()`)
- Full lifecycle smoke test: download a sub-app, launch it, stop it,
  uninstall it from the card menu. No leftover process (check with `ps`),
  the app folder should be gone after uninstall, the card should return to
  "Not Installed".

## Deliberately deferred

Cross-building a macOS/Linux package from a different host OS (the
`--platform` wheel-resolution fallback in `_install_launcher_deps()`) is
implemented but has never run for real. Not part of this handoff on
purpose: native builds are available on all three platforms, so nothing
currently depends on cross-building. Worth a look only if a future CI setup
wants one machine producing every package.
