# Native window roadmap

## Current status (2026-09-09)

The launcher is **back to opening in the system browser** (the original
behavior). A working native-window implementation using `pywebview` was
built and fully tested this session, but was reverted before shipping: the
native window uses the plain OS title bar (blue, generic - just the Windows
accent color), which doesn't match the app's own dark header at all. Rather
than ship that mismatch, the decision was to hold off, keep the browser-tab
UI for now, and come back to this with a **fully custom title bar** instead
of just re-coloring the native one.

This doc exists so that work isn't lost: everything below was actually
built and verified working on Windows this session, just not activated.

## The decision: custom frameless title bar, not a recolored native one

Two options were considered:

1. **Recolor the native title bar** via the Windows 11 DWM API
   (`DwmSetWindowAttribute` with `DWMWA_CAPTION_COLOR`/`DWMWA_TEXT_COLOR`).
   Low effort, keeps every native behavior (resize, snap, drag, Alt+Tab
   thumbnail) for free. Rejected for the long term: only works on Windows 11
   22000+ (silently no-ops on Windows 10), and it only tints a bar shaped
   like Windows' own - it doesn't actually merge with the app's UI.
2. **Frameless window with a custom title bar built into the app's own
   header** (the existing `.app-header` in `index.html` becomes the title
   bar - draggable, with custom minimize/maximize/close buttons styled like
   the rest of the app). This is the direction to build toward - genuinely
   "merges with the software" the way Spotify/Discord/VS Code do it. More
   work: needs a JS<->Python bridge for window controls, and frameless mode
   needs care to not lose resize-by-edge/snap.

**Chosen: option 2, for later.** Not implemented yet - this doc is the plan.

## What was already built and verified this session (and reverted)

Everything below actually ran, including live end-to-end tests (window
opens, second-instance handoff opens a window too, Quit button and the
native "X" both close cleanly, process exits, lock released). It was
reverted out of `launcher/gui.py` and
`build_release/build_windows_release.py` via `git checkout` after this
decision - re-applying it is straightforward, not a from-scratch rebuild.

### Dependency

`pywebview>=6.2.1` specifically - **not 6.1**. On Windows, 6.1's WinForms
backend ignores the `icon=` argument to `webview.start()` entirely and
always tries to grab an icon from `sys.executable` via `ExtractIconW()` +
`Icon.FromHandle()`; 6.2.1 uses `Icon(icon_path)` directly when `icon=` is
given, which is both correct and safer.

### Real bug found and fixed independently of pywebview: `icon_app.ico`

While testing the packaged WinPython build, the native window crashed the
*entire process* (not a catchable Python exception - an unhandled .NET
exception on a background thread) on startup, intermittently. Root cause:
Pillow's default ICO writer PNG-compresses any frame requested at 256px,
and the legacy `System.Drawing.Icon` class .NET Framework hosts (which is
what pythonnet uses) **cannot decode PNG-compressed icon frames at all** -
confirmed directly with `System.Drawing.Icon('icon_app.ico', size, size)`
failing at every single size, not just 256.

Fix already applied and kept (this fix is unrelated to whether pywebview is
active, so it was left in place even after reverting the window itself):

```python
from PIL import Image
src = Image.open("icon_app.png").convert("RGBA")
src.save(
    "icon_app.ico",
    sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)],
    bitmap_format="bmp",  # <- forces classic DIB frames, no PNG compression
)
```

Whenever `icon_app.ico` is regenerated in the future (e.g. from a new master
image), it must be regenerated with `bitmap_format="bmp"` or this exact
crash comes back.

### The reverted `launcher/gui.py` mechanism (for reactivation)

The full diff was `git diff`'d out to a patch before reverting, but patches
in the local Claude scratchpad don't survive between sessions, so the
architecture is written out here instead:

- `_native_window_usable()`: gate function. Returns `False` (falls back to
  the current browser-tab behavior, unchanged) if `PYPOTTERY_NO_NATIVE_
  WINDOW` is set, if `import webview` fails, or - Windows only - if
  `webview.platforms.winforms.renderer == "mshtml"` (pywebview's WinForms
  host silently downgrades to the ancient IE/MSHTML engine when the
  WebView2 Runtime isn't installed, instead of raising; that engine can't
  render the launcher's modern JS/CSS).
- In `_run()`, when a native window is usable: `server.serve_forever()`
  moves to a daemon thread (pywebview's loop needs the main thread), then
  `webview.create_window(...)` + `webview.start(icon=...)` on the main
  thread, blocking until the window closes.
- **Closing behavior** (this is the part worth preserving carefully - it
  took real iteration to get right): pywebview re-fires the `closing` event
  for *every* close, including a programmatic `window.destroy()` call, not
  just a user click. The handler vetoes the close (`return False`) and
  clicks the page's own `#btn-quit` via `window.evaluate_js(...)` - routing
  the native "X" button through the exact same themed confirm modal ->
  `/api/shutdown` -> "Terminated" screen flow the in-page Quit button uses,
  instead of a second native confirmation dialog. A separate thread waits
  on `state.stop_event` (already set by every real shutdown path: Quit
  button, launcher self-update restart, and the existing no-tab
  auto-shutdown timer) and calls `window.destroy()` once it fires. The veto
  handler checks `state.stop_event.is_set()` first and lets the close
  through when it's already true - without that check, `window.destroy()`
  would re-trigger its own veto forever and the window would never actually
  close.
- Second-instance handoff (`_defer_to_existing_instance`) also opens a
  native window pointing at the already-running instance's port, with the
  same usability gate and browser-tab fallback, but without the closing
  veto (that instance doesn't own the server, so there's nothing for it to
  gracefully shut down).

### Build script

`build_release/build_windows_release.py`'s `create_winpython_package()`
had `"pywebview>=6.2.1"` added to the `packages` list installed into the
WinPython bundle. Reverted along with `gui.py` since shipping the
dependency with nothing using it is dead weight.

## What frameless + custom title bar will additionally need

Confirmed available in pywebview (checked against the installed 6.1/6.2.1
source, applies to all platforms it supports, not just Windows):

- `webview.create_window(..., frameless=True, easy_drag=False)` - removes
  the OS title bar. `easy_drag=False` is important: with it `True`, the
  *entire* window becomes a drag handle on mousedown, which would make
  every button in the header undraggable-but-also-unclickable in practice.
- `webview.settings['DRAG_REGION_SELECTOR']` defaults to
  `.pywebview-drag-region` - any element with that class becomes a drag
  handle instead. Put it on the `.app-header` container (or a slim strip
  within it), *not* on the buttons inside - the injected JS
  (`webview/js/customize.js`) walks up from the actual click target
  looking for an exact match against elements carrying that class, so a
  click that lands on a button never reaches the drag handler as long as
  the button itself doesn't carry the class.
- Window controls (minimize/maximize/restore/close) have to be exposed to
  JS explicitly - `Window.minimize()`, `.maximize()`, `.restore()`,
  `.destroy()` exist Python-side (confirmed via
  `[m for m in dir(webview.Window) if not m.startswith('_')]`) but aren't
  reachable from JS without `window.expose(...)` (or the `js_api=` param on
  `create_window`) wiring them to `window.pywebview.api.*`.
- The close button should reuse the exact same veto -> `#btn-quit` click ->
  `stop_event` watcher mechanism already built and described above, not a
  raw `destroy()` call - that's what makes the custom close button behave
  identically to the already-solved native "X" case.
- The custom title bar buttons must only render when actually inside
  pywebview, not in a plain browser tab (the fallback path, and until
  macOS/Linux get the same treatment, those platforms too) - detect via
  `window.pywebview` (pywebview injects this after a `pywebviewready` event
  fires; it's not present synchronously on page load).
- Needs verification once implemented: whether a frameless WinForms window
  keeps reliable edge-resize and Windows 11 snap-layout behavior, or
  whether that has to be hand-rolled too (this was not tested - the whole
  frameless path was never built, only researched).

## Explicitly out of scope / untouched by any of this

- **Sub-apps** (PyPottery Layout/Lens/Ink/Scan/Trace): launched via
  `app_manager.py`'s `webbrowser.open(f"http://localhost:{app.port}")`,
  completely separate code path from the main launcher window. Opening
  those in a native window too (instead of the system browser) is a
  distinct, not-yet-discussed feature.
- **macOS and Linux**: pywebview is not in `build_unix_release.py`'s
  dependency list at all yet. Linux in particular needs a real decision
  before adding it - GTK+WebKit2 (lighter, but depends on system libraries
  the AppImage format is meant to avoid bundling around) vs Qt+WebEngine
  (self-contained via pip wheels, but ~150-250MB heavier than the current
  AppImage). Not resolved.
- **The PyInstaller-built `PyPottery.exe`** (`--onedir`) package: never had
  pywebview added to it. Bundling pythonnet through PyInstaller's static
  analysis is a different risk profile (see that build script's own
  warnings about mismatched OpenSSL DLLs from a dirty build env) that
  wasn't evaluated.
