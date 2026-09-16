# Publication roadmap

Compiled 2026-09-13 from a cross-repo audit (launcher hardening notes, native
window roadmap, macOS/Linux verification handoff, the PyPotteryScan design
critique, GLM-OCR status report, and a `graphify` knowledge graph built over
`launcher/` + `PyPotteryDocs/` + the 5 app repos). Grouped by how much they
block a "complete" multi-platform public release.

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
- [ ] **PyPotteryScan violates its own local-first principle.**
  The Impeccable design critique
  (`PyPotteryScan/.impeccable/critique/2026-09-12T17-44-42Z__app-templates-index-html.md`)
  flagged a P0: `app/templates/index.html` depends on external CDNs, which
  breaks the offline/local-first architecture `PRODUCT.md` advertises as a
  suite-wide principle. A local-vendor-with-CDN-fallback pattern already
  exists elsewhere in the same file per the graph extraction - worth
  checking whether it's just inconsistently applied rather than absent.

## P1 - should fix before calling it done, each is small

- [ ] **PyPotteryInk version drift.** `PyPotteryInk/version.txt` says
  `2.1.0`; `PyPotteryInk/docs/version_history.html` documents nothing past
  `v1.0.0` (Sept 2025). Either the VERSION file was bumped without a
  changelog entry, or something is stale. Looks careless to a new user
  comparing the two.
- [ ] **Confirm the GLM-OCR fixes actually hold.** `PyPotteryScan/GLM_OCR_STATUS.md`
  documents two real bugs already patched (`TokenizerBackend` missing class
  after the `transformers` upgrade to 5.17.0; empty-output bug from using
  `AutoTokenizer` instead of `AutoProcessor`) plus a `modelSelectionDefaulted`
  polling bug. Status doc says fixed - worth one clean end-to-end OCR run to
  confirm before release, not just re-reading the notes.
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
  the launcher itself hit and fixed with `guarded()`. Since the pattern
  already exists and works in `launcher/logging_setup.py`, extracting it
  into a shared module the 5 apps import is low effort for real reliability
  gain.

## P2 - polish, fine to ship without and follow up later

- [ ] **Aesthetic/structural drift across the 5 sub-apps.** Not standardized:
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
  - Decide scope before touching this: folder/code-structure unification
    (extract shared `ProjectManager`, release workflow, vendor libs into a
    common package) is a different size of effort than just aligning
    CSS/visual conventions.
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

## Sources

- `KNOWN_ISSUES.md` - launcher hardening pass (fixed/deferred list)
- `NATIVE_WINDOW_ROADMAP.md` - native window decision and revert
- `MACOS_LINUX_VERIFICATION.md` - cross-platform verification checklist
- `PyPotteryScan/.impeccable/critique/2026-09-12T17-44-42Z__app-templates-index-html.md`
- `PyPotteryScan/GLM_OCR_STATUS.md`
- `PyPotteryDocs/pypotteryink/version_history.qmd` vs `PyPotteryInk/version.txt`
- `graphify-out/graph.json` / `GRAPH_REPORT.md` - cross-repo structural graph (see `graphify-out/SCOPE.md` for what it covers)
