---
target: PyPotteryLens/templates/index.html
total_score: 23
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 1
target_identity: "file:C:\\Users\\larth\\Documents\\PyPottery\\PyPotteryLens\\templates\\index.html"
target_fingerprint: "sha256:9887939dc5cda04490900b11bce2c0eca2eaa82bd9b85984d7f25f64c4ea2946"
target_path: "C:\\Users\\larth\\Documents\\PyPottery\\PyPotteryLens\\templates\\index.html"
timestamp: 2026-09-11T22-06-25Z
slug: pypotterylens-templates-index-html
---
# PyPotteryLens — Design Critique Report

Method: dual-agent (A: 9c157ca0-25a6-419b-b594-1bd35065c87e · B: e9f3f53d-6379-4348-b4c4-da8891f1e0fc)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|:-----:|-----------|
| 1 | Visibility of System Status | 3 | Full-screen inference overlays are good, but canvas auto-save (scheduleAutoSave 600ms) runs silently with no "Saved" indicator, inducing anxiety. |
| 2 | Match System / Real World | 3 | Ceramic drafting concepts (scale bars in cm, plate bisection, rim orientations) are authentic, but CV parameters (Kernel Size, Iterations) leak raw engineering terms. |
| 3 | User Control and Freedom | 1 | **Critical Flaw**: Annotation canvas completely lacks Undo/Redo (Ctrl+Z / Ctrl+Y). Errant brush strokes or clearing permanently overwrites hours of work in 600ms. |
| 4 | Consistency and Standards | 3 | Cohesive brand tokens and typography, but sidebar drawer toggle mechanics differ arbitrarily between Tab 3 (grid layout collapse) and Tab 4 (off-canvas overlay). |
| 5 | Error Prevention | 2 | Confirmations on major destructive acts, but zero guardrails against navigating tabs mid-polygon and no validation against duplicate sherd inventory codes. |
| 6 | Recognition Rather Than Recall | 3 | Scanned spread bisection popover is exemplary, but AI prompt customization requires memorizing bracket syntax (`[Scale]`, `[Class]`) without suggested field chips. |
| 7 | Flexibility and Efficiency | 2 | Total absence of keyboard shortcuts (B=Brush, E=Eraser, P=Polygon, S=Scale, Space+Drag=Pan, J/K plate navigation), causing severe click fatigue on large plate sets. |
| 8 | Aesthetic and Minimalist Design | 2 | Tab 4 (Tabular Workbench) suffers severe visual noise: 7-button command strip, plate canvas, zoom inspector, two collapsible dark console drawers, and an editable table. |
| 9 | Help Users Recognize, Diagnose, Recover | 2 | Toast notifications inform of errors, but AI extraction failures or OCR mismatches offer no actionable diagnosis, fallback paths, or field-level confidence flags. |
| 10 | Help and Documentation | 2 | Pixel Assistant links out to external documentation in a new tab (`target="_blank"`), severing context in offline dig houses. No inline empty-state onboarding. |
| **Total** | | **23/40** | **Acceptable** |

## Design Specificity Verdict

**LLM Assessment (Assessment A)**:
PyPotteryLens has exceptional domain grounding that is clearly authored for computational archaeology and ceramic documentation rather than being generic AI boilerplate. The visual identity faithfully anchors to the *Carta Millimetrata* drafting grid, archival parchment surfaces (`#fbf9f5`), terracotta brand accents (`#c2410c`), and archaeological affordances like scanned spread bisection down the book spine and metric scale calibration. However, localized regressions into generic AI habits compromise the experience: the "magic wand" AI prompt paradigm, the discordant 80s phosphor-green Pixel Assistant CRT monitor, and SaaS-style floating modals that break the archival dossier metaphor.

**Deterministic Scan (Assessment B)**:
The automated detector flagged 42 total findings (22 slop, 20 quality; 33 warnings, 9 advisories). 
- **Domain False Positives**: The detector flagged `cream-palette` (`#fbf9f5`), `codex-grid-background` (two-axis drafting grid), and `overused-font` (`Plus Jakarta Sans`). Cross-referencing with `PRODUCT.md` confirms these are intentional, core archaeological drafting room commitments (archival drawing paper, *Carta Millimetrata*, and unified suite typography), not generic AI slop.
- **Legitimate Deficiencies Caught**:
  - `skipped-heading`: Accessibility violation (WCAG 1.3.1) where `<h1>` jumps directly to `<h4>` in `#model-info-popup`.
  - `broken-image`: `<img>` tags without `src` or with empty `src=""` (`#postprocess-lightbox-img`, `#modal-image`).
  - `low-contrast`: Emerald green (`#10b981`, 2.5:1) and teal (`#0d9488`, 3.7:1) buttons failing WCAG AA 4.5:1 text contrast.
  - `gpt-thin-border-wide-shadow`: 8 instances pairing 1px borders with 36px–60px diffuse blur shadows.
  - `nested-cards`: 5 container nesting stacks in Tab 4 and modals adding unnecessary cognitive visual weight.
  - `icon-tile-stack`: 3 instances of 48x48 rounded squircle icon tiles stacked above modal headings.
  - `layout-transition`: 9 CSS transitions animating layout properties (`width`, `margin`, `padding`), degrading frame rates.

**Visual Overlays**:
Browser visualization and overlay injection were skipped because no interactive browser automation tool is exposed in the environment.

## Overall Impression
PyPotteryLens is a deeply authentic, specialized scientific drafting workstation with genuine archaeological craftsmanship. However, it currently operates with a dangerous lack of safety nets (missing Undo/Redo), high cognitive overload in its Tabular metadata workbench, and technical accessibility/contrast debt that makes it fragile for intensive field excavation usage.

## What's Working
1. **Scanned Spread Bisection Guide (`.spread-compare-popover`)**: The tactile illustration contrasting single pages against scissors-bisected monograph spreads translates complex CV pre-processing into an intuitive mental model.
2. **True-to-Scale Ceramic Post-Processing Grid**: Dynamically scaling ceramic cards to their calibrated `px_per_cm` metric ratio directly respects core archaeological publication conventions.
3. **Scholarly Materiality and Cohesive Tokens**: Archival parchment grounds, terracotta accents, and strict adherence to semantic Bootstrap Icons (no emojis) give the tool a dignified scholarly identity.

## Priority Issues

- **[P0] Absence of Undo/Redo in Annotation Masking Canvas (`annotation-tab.js`)**
  - *Why it matters*: Destroys researcher trust. A stray brush stroke, errant polygon click, or accidental "Clear Canvas" permanently destroys hours of ceramic tracing via an aggressive 600ms autosave.
  - *Fix*: Implement an in-memory canvas image-buffer history stack (20 steps), bind `Ctrl+Z` / `Ctrl+Y`, add Undo/Redo buttons to the retouch cluster, and show an explicit "Saved at HH:MM" badge.
  - *Suggested command*: `/impeccable harden`

- **[P1] Cognitive Overload and Visual Clutter in Tabular Workbench (Tab 4)**
  - *Why it matters*: Causes severe analysis paralysis. A 7-button command strip, 2 dark console drawers, an image inspector, and an editable table fight for primacy simultaneously.
  - *Fix*: Apply progressive disclosure: tuck AI tuning into a slide-over calibration sheet, separate plate inspection from data entry via master-detail view, and demote destructive "Clear Page Data" to an overflow menu.
  - *Suggested command*: `/impeccable distill`

- **[P2] Leaking Raw Computer Vision Engineering Parameters (Tab 2)**
  - *Why it matters*: Ceramicists and illustrators should not be forced to guess OpenCV morphological parameters like "Kernel Size: 2" and "Iterations: 10".
  - *Fix*: Collapse raw numerical controls into an "Advanced CV Parameters" disclosure; provide archaeological presets ("Delicate Pencil Shading", "Standard High-Contrast Ink", "Faint Lithograph").
  - *Suggested command*: `/impeccable clarify`

- **[P3] Lack of Drafting Keyboard Accelerators & Focus Rings**
  - *Why it matters*: Digitizing hundreds of monograph plates causes extreme repetitive strain when every tool switch requires a click. Suppressed focus outlines (`outline: none`) break keyboard accessibility.
  - *Fix*: Implement single-key drafting hotkeys (`B`=Brush, `E`=Eraser, `P`=Polygon, `S`=Scale, `Space+Drag`=Pan, `J`/`K`=Plates), add a hotkey modal (`?`), and style 2px terracotta `:focus-visible` rings.
  - *Suggested command*: `/impeccable polish`

## Persona Red Flags
- **Alex (Power User / Tech-Savvy Ceramic Specialist)**: Cannot calibrate a global scale ratio across uniformly scanned plates; cannot quickly navigate plates via `J`/`K` keys; lacks keyboard shortcuts (`B`, `E`, `P`); batch AI extraction runs without a progress breakdown table showing ambiguous OCR labels.
- **Jordan (First-Timer / Traditional Field Archaeologist)**: Intimidated by "Kernel Size" and "Iterations" in Tab 2; accidentally clears a mask in Tab 3 without an Undo option; clicks the Pixel Assistant for help and is disoriented when a new browser tab opens to GitHub Pages.
- **Sam (Accessibility-Dependent User / Screen Reader & Keyboard)**: Tab buttons lack WAI-ARIA `role="tablist"` and `aria-selected` semantics; buttons lack `:focus-visible` outlines; `<h1>` jumps to `<h4>` breaking document outline; emerald/teal buttons fail WCAG AA 4.5:1 contrast.

## Minor Observations
1. **Raw Unicode Text Character in Popover**: In `index.html` line 492, the spread axis uses raw `✂` instead of `<i class="bi bi-scissors"></i>`, violating `PRODUCT.md`.
2. **Pixel Assistant Aesthetic Mismatch**: The CRT monitor with green phosphor text (`#0f0`) introduces an alien 80s arcade feel that clashes with the Mediterranean terracotta palette.
3. **Broken Image Shells**: Empty `<img>` tags (`#postprocess-lightbox-img`, `#modal-image`) trigger unnecessary network errors prior to script hydration.
4. **Layout Thrashing Transitions**: 9 CSS transitions animate `width`, `margin-right`, and `padding` instead of GPU-accelerated `transform` and `opacity`.

## Questions to Consider
1. *Could the Tabular Workbench transition from a monolithic spreadsheet into a synchronized split-screen "Sherd Proofing Deck" pairing high-magnification drawing cutouts directly with bibliographic data?*
2. *Should the annotation canvas evolve from destructive raster mask painting to non-destructive vector paths and bezier curves with editable control points?*
3. *Could the Project Manager serve as an excavation monograph dashboard—displaying typology completion rates, scale calibration audits, and plate health at a glance?*
