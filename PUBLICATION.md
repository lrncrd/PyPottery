# Publication roadmap

Compiled 2026-09-13 from a cross-repo audit (launcher hardening notes, native
window roadmap, macOS/Linux verification handoff, the PyPotteryScan design
critique, GLM-OCR status report, and a `graphify` knowledge graph built over
`launcher/` + `PyPotteryDocs/` + the 5 app repos). Grouped by how much they
block a "complete" multi-platform public release. **Updated 2026-09-19**
after the PyPotteryLayout 0.3.3 release and a re-audit of every item below
against the current state of each repo (not just re-reading old notes).

## Design principle: every app is standalone

Each sub-app must run on its own (`git clone` + `pip install -r requirements.txt`
+ `python app.py`), with or without the PyPottery Launcher. Consequence for
every item below: **no cross-repo imports or shared runtime packages.**
Common code (beacon/auto-shutdown, logging setup, release workflow, vendored
libs) is *copied* into each repo with the same interface, never imported from
a sibling repo or from `launcher/`. Env vars like `PORT`/`PYPOTTERY_PORT` are
optional overrides with an in-app default, never required.

## Resolved since 2026-09-13

- **PyPotteryInk version drift** (was P1). Root cause was systemic, not
  Ink-specific: every app keeps a `VERSION` file (bumped automatically by
  that app's release workflow) alongside a legacy `version.txt` the
  automation never touches, and the launcher's `AppManager._detect_version`
  (`launcher/app_manager.py`) checked `version.txt` first — so any app could
  silently drift the same way Ink did. Fixed properly instead of just
  re-syncing the two files: the launcher now reads `VERSION` only, and the
  vestigial `version.txt` has been removed from PyPotteryLayout, PyPotteryInk
  and PyPotteryLens (PyPotteryScan/PyPotteryTrace never had one). This class
  of bug can't recur.
- **PyPotteryLayout shipped v0.3.3** (2026-09-19, real GitHub release, not
  draft/prerelease — confirmed via the API). Bundled: auto-shutdown/beacon
  (see below), the About-modal redesign onto the shared suite pattern,
  independent top-spacing control and SVG margin-border export for
  grid/puzzle layouts, expanded table-numbering positions, Basic/Advanced
  settings tabs. Documented in
  `PyPotteryDocs/pypotterylayout/version_history.qmd`. A backup branch
  (`main-backup-2026-09-19`, pushed to origin) preserves the pre-release
  state of `main` (v0.3.2) if a rollback is ever needed.
- **Header/modal visual drift across the 5 apps** (part of the old P2
  "Aesthetic/structural drift" item). The About-modal backdrop blur/tint is
  now `rgba(28,25,23,0.45)` + `blur(8px)` on all 5 apps (Layout previously
  had none, Ink/Scan/Lens had mismatched opacity); PyPotteryScan's header
  markup uses a real `<header>` tag instead of a `<div>`; PyPotteryLens's
  modal was relocated out of `.header-content` for structural consistency.
  The deeper items in that old bullet (duplicated `release.yml`/`FUNDING.yml`,
  copy-pasted Pixel Assistant widget, per-app vendored Bootstrap, an isolated
  `PRODUCT.md` in PyPotteryScan only) are **still open** — see P2 below.
- **PyPotteryLayout README standardized** — new lean template (features,
  two-path Quick Start: PyPottery Suite Launcher for regular users vs.
  `pip install -r requirements.txt` for source installs, link to
  `version_history.html` instead of an inline changelog). Also found and
  fixed a duplicate, already-drifted copy of the README that lived at
  `PyPotteryDocs/pypotterylayout/README.md` — deleted, nothing referenced it.
  **Not yet done for Ink/Lens/Scan/Trace** — see P2.

- **PyPotteryScan refactor + offline assets** (2026-09-19, on `beta`, not
  released). The 4 Blueprints are now one (URL map verified identical, 33
  rules) and the ~6000 lines of inline JS live in `app/static/js/app.js`
  (byte-identical). The old P0 "CDN violation" turned out to be narrower than
  written: the launcher's `VendorAssetsManager` already downloads
  Bootstrap/icons/fonts once and syncs them into each app's (gitignored)
  `static/vendor` on every start; the only asset it missed was SheetJS
  (`xlsx`), so Scan's Excel export always hit the CDN. Added to the launcher
  (`d6dcf10`); verified Scan loads with zero errors and all vendor files 200
  with external network blocked. Useless `preconnect` hints to Google removed.
  **Known limit:** a standalone `git clone` of any app has no `vendor/` (it is
  gitignored, launcher-managed), so it falls back to the CDN - online works,
  offline standalone does not. Open decision if we want offline-standalone:
  track `vendor/` in each repo (~0.7 MB) or let each app self-download it.
- **Fonts/vendor loading uniformed across all 5 apps** (2026-09-19, on `beta`,
  not released). Only Plus Jakarta Sans 700/800 were bundled, but the styles
  use 400-800, and Ink/Trace/Layout pulled the rest (and JetBrains Mono) from
  Google Fonts while Scan/Lens had no mono font at all. The launcher's
  `VendorAssetsManager` now vendors Jakarta 400-800 + JetBrains Mono 400-700;
  every app links only the local `vendor/fonts/fonts.css`, with Google Fonts
  as an `onerror` fallback (so a standalone clone without `vendor/` still
  works online). Layout also switched Bootstrap/icons from CDN-only to
  vendor-first with CDN fallback. Verified all 5 apps offline in headless
  Chrome (fonts.css + woff2 served locally, no errors). Lens's own
  suite-style header/About-modal redesign (hardware chip, copy-citation) was
  committed on `beta` in the same pass.


## P0 - blocks a multi-platform release

- [ ] **macOS/Linux verification was never actually completed.**
  `MACOS_LINUX_VERIFICATION.md` is a checklist, not a report: macOS was
  tested exactly once, on Apple Silicon, on 2026-09-08. Linux has had **zero**
  native passes. Everything in that file - data directory migration, DMG
  Gatekeeper translocation, AppImage `python_runtime/` persistence, the
  desktop entry install script, second-instance handoff, full sub-app
  lifecycle - needs a real run on real hardware before claiming 3-platform
  support. Can't be done from this Windows machine; needs someone with
  access to a Mac and a Linux box (or CI runners) to work through the
  checklist.

## P1 - should fix before calling it done, each is small

- [ ] **Finish the auto-shutdown/beacon rollout on Ink, Scan, Trace.** The
  heartbeat + exit-confirmation + beacon mechanism (see
  `AUTO_SHUTDOWN_MODULES_GUIDE.md`) is **committed locally on `beta` (2026-09-19,
  together with each app's UI redesign) but not pushed and not merged to `main`.
  HTTP-level lifecycle test passed on all three (2026-09-19, standalone with `PORT`
  override: heartbeat 200, beacon 204, survives beacon+heartbeat within grace = F5,
  process exits ~5.3s after a lone beacon). The browser-side JS (`beforeunload`
  prompt, `sendBeacon` on `pagehide`) is still not browser-tested** for these three. Scan's `.gitignore` is already fixed
  (`/static/`). Remaining: manual QA, push `beta`, backup + merge to `main`.
  Original notes on the uncommitted state:
  - PyPotteryInk: `app.py` + `static/js/app.js`, sitting uncommitted in the
    working tree alongside unrelated pre-existing WIP (`ink.py`, CSS/templates).
  - PyPotteryScan: `app/routes.py` + `app/__init__.py` + a new
    `app/static/js/beacon.js`. **`beacon.js` currently falls under this
    repo's `.gitignore` rule `static/` (line 226, matches at any depth) and
    will not be picked up by a plain `git add` — chosen fix: anchor the
    `.gitignore` rule rather than `git add -f`, so future files don't hit it.** Also has unrelated
    uncommitted logo changes mixed into the working tree.
  - PyPotteryTrace: `app.py` + `interactive_app/main.py` +
    `interactive_app/static/js/app.js`, also uncommitted, also mixed with
    unrelated pre-existing WIP.
  - PyPotteryLens and PyPotteryLayout are done and released.
- [ ] **GitHub auto-release workflow produces useless release notes.** Every
  app's `release.yml` creates its GitHub Release with
  `generate_release_notes: true`, which - since these repos release via
  direct pushes to `main`, not merged PRs - produces nothing but
  `**Full Changelog**: <compare link>` (confirmed on the just-published
  PyPotteryLayout v0.3.3 via the API). The launcher's "Changelog & Release
  Notes" panel (`launcher/web_server.py:647`, reads `rel.body` straight from
  the GitHub Release) shows exactly that generic line to end users instead
  of anything readable - even though a proper, hand-written changelog entry
  exists in parallel on `PyPotteryDocs/<app>/version_history.qmd`, which the
  launcher never reads. Two separate things that need to become one: either
  make the release workflow pull its body from a changelog file committed
  alongside the code (e.g. a small `CHANGELOG.md` with an "Unreleased"
  section per app), or otherwise stop maintaining two disconnected changelog
  surfaces. Needs its own careful design pass, not a quick patch - it changes
  the release workflow for every future release for every app.
- [ ] **Confirm the GLM-OCR fixes actually hold.** `PyPotteryScan/GLM_OCR_STATUS.md`
  documents two real bugs already patched (`TokenizerBackend` missing class
  after the `transformers` upgrade to 5.17.0; empty-output bug from using
  `AutoTokenizer` instead of `AutoProcessor`) plus a `modelSelectionDefaulted`
  polling bug. Status doc says fixed but ends on "restart the server and
  retry" - no confirmation on record that the retry happened. Worth one
  clean end-to-end OCR run before release, not just re-reading the notes.
- [ ] **No sub-app has launcher-grade error logging.** Checked directly:

  | App | uses `logging` module | `print()` calls |
  |---|---|---|
  | PyPotteryInk | no | 243 |
  | PyPotteryLayout | no | 26 |
  | PyPotteryLens | no | 235 |
  | PyPotteryScan | only `logging.basicConfig(level=INFO)` to stdout | 202 |
  | PyPotteryTrace | no | 516 |

  None of the 5 apps have anything like `launcher/logging_setup.py`
  (rotating file handler, `sys.excepthook`, `threading.excepthook`,
  `faulthandler`). Partial mitigation: the launcher already redirects each
  sub-app's stdout/stderr to `logs/apps/<id>.log`
  (`app_manager.py`'s `_open_app_log`), so `print()` output isn't lost when
  launched normally. Real gap: an unhandled exception on a background
  thread (model downloads in Lens, OCR model loading in Scan, diffusion
  inference in Ink) dies silently with no trace - the exact failure mode
  the launcher itself hit and fixed with `guarded()`. The pattern already
  exists and works in `launcher/logging_setup.py`; per the standalone
  principle above, copy it as a `logging_setup.py` *inside each app repo*
  (same content, no import from `launcher/` or a sibling repo) - low effort
  for real reliability gain.

## P2 - polish, fine to ship without and follow up later

- [ ] **Standardized README rollout to Ink, Lens, Scan, Trace.** Only
  PyPotteryLayout has the new lean template (see "Resolved" above).
  Deliberately deferred - the other 4 have wildly different lengths (238 to
  615 lines) and depth (Lens/Trace carry detailed workflow/architecture
  content the lean template doesn't have room for); each one links to
  `version_history.html` instead of duplicating a changelog inline once
  this is done. Note: Lens is GPLv3, the other four are Apache 2.0 - keep as
  is, don't unify licenses.
- [ ] **Aesthetic/structural drift across the 5 sub-apps** (narrowed - the
  modal/header visual drift itself is fixed, see "Resolved" above). Still
  not standardized:
  - `release.yml` and `FUNDING.yml` duplicated near-identically across all 5
    repos (auto-versioning workflow, VERSION-file lockstep).
  - The "Pixel Assistant" help widget is copy-pasted into each app's
    `templates/index.html` rather than shared.
  - Each app vendors its own copy of Bootstrap (and PyPotteryScan also
    vendors SheetJS/xlsx) instead of a shared vendor directory.
  - `PyPottery Color Palette Design Tokens` is documented only in
    `PyPotteryScan/PRODUCT.md` (graph shows it as an isolated, degree-1
    node) - not referenced by the other 4 apps, so unclear whether it's
    actually followed anywhere else or just an intention written once.
  - Decide scope before touching this: aligning CSS/visual conventions is
    cheap; unifying code structure is constrained by the standalone
    principle - no shared `ProjectManager`/vendor package imported across
    repos. Alignment means keeping copies in sync (same interface, per-repo
    copy), not extracting a common dependency.
- [ ] **Native window with custom title bar.** Deliberately deferred by the
  project itself (`NATIVE_WINDOW_ROADMAP.md`) - a working `pywebview`
  implementation was built and reverted because the native OS title bar
  didn't match the app's dark header. Browser-tab UI works fine today; this
  is cosmetic, not a blocker. Plan is documented and ready to resume
  (frameless window + custom title bar, not a re-colored native one).
- [ ] **Cross-building macOS/Linux packages from a different host OS**
  (`_install_launcher_deps`'s `--platform` fallback) is implemented but has
  never been exercised for real. Low priority since native builds work on
  all three platforms already - only matters if a future CI setup wants one
  machine producing every package.
- [ ] **YouTube tutorials - sequencing, not a blocker.** Recommendation:
  ship the app + docs site first, record tutorials after the interface has
  settled from beta feedback rather than in the same push - a tutorial
  recorded against UI that changes in the following weeks ages fast. Fine to
  announce "tutorials coming" at launch without having them ready.

## Sources

- `KNOWN_ISSUES.md` - launcher hardening pass (fixed/deferred list)
- `NATIVE_WINDOW_ROADMAP.md` - native window decision and revert
- `MACOS_LINUX_VERIFICATION.md` - cross-platform verification checklist
- `AUTO_SHUTDOWN_MODULES_GUIDE.md` - auto-shutdown/beacon rollout spec and
  per-app checklist
- `PyPotteryScan/.impeccable/critique/2026-09-12T17-44-42Z__app-templates-index-html.md`
- `PyPotteryScan/GLM_OCR_STATUS.md`
- `PyPotteryDocs/pypotterylayout/version_history.qmd` - v0.3.3 changelog entry
- Memory `pypotteryscan-structure-refactor` - Blueprint/inline-JS cost estimate
- Memory `pypottery-suite-modal-beacon-version-2026-09` - what shipped
  2026-09-19 and what's still deferred
- `graphify-out/graph.json` / `GRAPH_REPORT.md` - cross-repo structural graph (see `graphify-out/SCOPE.md` for what it covers)
