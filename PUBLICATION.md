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
- **Release-notes disconnect fixed at the launcher** (2026-09-19, on `beta`).
  The launcher's changelog panel now shows the hand-written entry from
  `PyPotteryDocs/<app>/version_history.qmd` (fetched from GitHub raw, cached
  2h, plain-text conversion) when its `### Version X.Y.Z` heading matches the
  release tag, and falls back to the GitHub release body otherwise
  (`launcher/update_checker.py`). No workflow changes in the 5 repos. **Needs
  the docs pushed to `main` to go live**, and Scan/Trace `version_history.qmd`
  need a `### Version X.Y.Z` heading under `## Latest Release` before they
  benefit (Trace's page is still "under construction").
- **Crash diagnostics in all 5 apps** (2026-09-19, on `beta`). The old P1
  "no launcher-grade logging" item overstated the gap: the launcher already
  captures each sub-app's stdout/stderr, including unhandled tracebacks from
  threads, in `logs/apps/<id>.log`. The real hole was native crashes
  (torch/OpenCV segfaults) and context-free tracebacks, now covered by an
  identical ~30-line block at the top of each `app.py` (`faulthandler` +
  timestamped/thread-named excepthooks). Deliberately not a shared module or
  a copy of `launcher/logging_setup.py` (standalone principle, and not needed).
- **Standardized README rolled out to Ink, Lens, Scan, Trace** (2026-09-19,
  on `beta`). Content that was only in the old READMEs was moved to the docs
  instead of dropped: Lens workflow details/troubleshooting/platform notes/
  0.3.0 changelog, Scan straighten tool + shortcuts, a new Trace "Technical
  Reference" page. Ink keeps its AI-disclosure/citation block. Trace's stale
  technical claims (routes, port, parameters) were dropped rather than moved.
- **Docs site rebuilt** (2026-09-19, root `beta`): Layout 0.3.3 notes, the
  new pages above, and previously-missing rendered images. Root cause of the
  missing files: the root `.gitignore` had unanchored `PyPotteryTrace/` etc.,
  which (case-insensitive on Windows) also hid new files under
  `PyPotteryDocs/pypotterytrace/` and `docs/pypotterytrace/`; anchored to
  `/PyPotteryTrace/`. Same class of bug as Scan's `static/` rule.
- **Minor uniformity**: `FUNDING.yml` added to Scan/Trace (`release.yml` was
  already byte-identical in all 5). `PRODUCT.md` in Scan is gitignored, so it
  was never a real drift.

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

- [ ] **Ship everything that is sitting on `beta`.** All 5 app repos and the
  root launcher repo have committed, tested-at-HTTP-level work on `beta`, none
  of it pushed and none merged to `main` (a push to `main` auto-releases):
  Ink/Scan/Trace (redesign + beacon + crash diagnostics + fonts + README),
  Lens (redesign + fonts + crash diagnostics + README), Layout (fonts + crash
  diagnostics on top of the released 0.3.3), Scan (single Blueprint + external
  JS). Per app: back up `main` as a branch (as done for Layout:
  `main-backup-2026-09-19`), merge `beta`, push, confirm the release. Do one
  app at a time. Beacon: the HTTP lifecycle passed on Ink/Trace/Scan
  (standalone, `PORT` override, F5 tolerance, exit ~5.3s after a lone beacon);
  the browser-side JS (`beforeunload` prompt, `sendBeacon` on `pagehide`) is
  still not browser-tested. Also push the root `beta` (launcher + docs) and
  re-check the docs site after merge.
- [ ] **Confirm the GLM-OCR fixes actually hold.** `PyPotteryScan/GLM_OCR_STATUS.md`
  documents two real bugs already patched (`TokenizerBackend` missing class
  after the `transformers` upgrade to 5.17.0; empty-output bug from using
  `AutoTokenizer` instead of `AutoProcessor`) plus a `modelSelectionDefaulted`
  polling bug. Status doc says fixed but ends on "restart the server and
  retry" - no confirmation on record that the retry happened. Worth one
  clean end-to-end OCR run before release, not just re-reading the notes.

## P2 - polish, fine to ship without and follow up later

- [ ] **Docs restructure: Getting Started + Usage + Version History per app.**
  Pilot done on PyPotteryLens (2026-09-19, on `beta`): `index.qmd` is now
  "Getting Started" (intro + install + first launch + troubleshooting, with a
  Quarto alias so the old `installation.html` redirects), `installation.qmd`
  removed, `usage.qmd` rewritten against the real UI as one linear guide.
  Storyboards for the animations live as `<!-- ANIMATION ... -->` comments in
  `pypotterylens/usage.qmd` (the 6 existing mock-ups still show the v0.2.1
  UI: 1 keep+retouch, 2 retouch, 3 redo; ~6 new ones proposed). Next: same
  schema for Scan, Ink, Trace, Layout, then build the animations once the UIs
  settle. Note: Lens docs now cite the local AI model as "Gemma 4 E2B (~10 GB)".
- [ ] **Residual drift across the 5 sub-apps** (mostly resolved - see
  "Resolved"). Left: the "Pixel Assistant" widget is a per-app copy (correct
  under the standalone principle, just keep the copies in sync), and Bootstrap
  is vendored per app by the launcher's shared `vendor/` sync. Nothing here
  needs a shared package.
- [ ] **Offline-standalone decision.** `vendor/` is gitignored and launcher-managed,
  so a plain `git clone` of one app falls back to CDNs (online works, offline
  does not). Options: track `vendor/` (~0.7 MB + 0.9 MB xlsx) in each repo, or
  let each app download it on first start. Your call.
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
