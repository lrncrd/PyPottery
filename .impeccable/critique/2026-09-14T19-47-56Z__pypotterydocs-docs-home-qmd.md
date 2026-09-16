---
target: docs_home.qmd (PyPotteryDocs suite homepage)
total_score: 26
max_score: 32
na_heuristics: 7,9
p0_count: 1
p1_count: 2
target_identity: "file:C:\\Users\\larth\\Documents\\PyPottery\\PyPotteryDocs\\docs_home.qmd"
target_fingerprint: "sha256:d84bfca94e3a3c9d97f2f98ea0b0d1ccfc23d76f2922b0bbb2a751a800039ceb"
target_path: "C:\\Users\\larth\\Documents\\PyPottery\\PyPotteryDocs\\docs_home.qmd"
timestamp: 2026-09-14T19-47-56Z
slug: pypotterydocs-docs-home-qmd
---
Method: dual-agent (A: ae8f8c986b1d6c0a5 · B: aeb12b22fcf7831af)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Hover/lift feedback consistent on cards/buttons; little else needed on a static page |
| 2 | Match System / Real World | 4 | Domain vocabulary (`schede di reperto`, rim/profile/section) and accurate tool→phase mapping |
| 3 | User Control and Freedom | 3 | Standard Quarto nav; no way to skip the long scroll to the actionable section |
| 4 | Consistency and Standards | 3 | Card system is coherent, but 6 divergent pill/badge species dilute the pattern (see P3) |
| 5 | Error Prevention | 3 | External links correctly use `rel=noopener`, `target=_blank`, directional icons |
| 6 | Recognition Rather Than Recall | 4 | Inter-phase connector pills restate the hand-off artifact, reducing recall burden |
| 7 | Flexibility and Efficiency | n/a | No power-user path expected on a linear first-visit overview page |
| 8 | Aesthetic and Minimalist Design | 2 | Same 5-tool/3-phase content restated three times back-to-back (see P0) |
| 9 | Error Recovery | n/a | Static page, no forms or destructive actions, no error states possible |
| 10 | Help and Documentation | 4 | The page *is* the docs hub; Getting Started links out correctly once reached |
| **Total** | | **26/32** | **Good (81%)** |

## Design Specificity Verdict

**Grounded in skin, generic in skeleton.** The copy, iconography, and connective tissue are genuinely archaeology-specific — `schede di reperto`, rim/profile/section terminology, the millimeter drafting-grid motif, terracotta/teal tokens, and especially the inter-phase connector pills that name the actual intermediate artifact ("Isolated Vessel Drawings," "Refined Vector Profiles") instead of a generic "Step 2." That device couldn't be lifted into another product unchanged. But the macro-structure — hero → feature/workflow diagram → capability table → values grid → citations-as-testimonials → CTA footer — is the standard SaaS landing template. The visual language is bespoke; the information architecture is boilerplate.

**Deterministic scan**: The CLI detector (`impeccable detect`) found no scannable patterns against the raw `.qmd` source (expected — it isn't HTML). Running it against the *live rendered page* (`http://localhost:4837/docs_home.html`, since the built `PyPotteryDocs/docs/docs_home.html` doesn't currently exist on disk — see note below) surfaced 53 findings desktop / 38 mobile across 12 rule types: `low-contrast` (17), `line-length` (19), `border-accent-on-rounded` (3), `all-caps-body` (3), `nested-cards` (3), `skipped-heading` (2), `cramped-padding` (1→3 at mobile), plus one-off `overused-font`, `cream-palette`, `layout-transition`, `dark-glow`, and an advisory `codex-grid-background`. At mobile width a new rule appeared: `body-text-viewport-edge` ×2 — body paragraphs sitting flush against the 16px viewport edge.

Cross-checking against `styles.css`, most of the `low-contrast` findings are **likely false positives**: the detector's own data shows medians of 6.2–8.5:1 (well above AA) alongside a reported single-sample "pixel contrast" of 1.1–1.2:1, tagged `on opacity stack` — consistent with sampling mid-fade during a CSS reveal transition rather than the settled state. `dark-glow` ("glow on dark page") directly contradicts the same run's own `cream-palette` finding (`rgb(253,251,247)`, a light page) and matches only a normal 10px elevation shadow (`--shadow-hover`) — a likely misclassification. `all-caps-body` most plausibly matches short badge/pill/label text (0.65–0.82rem, all 13 uppercase declarations in the stylesheet are on labels, not prose), not genuine body copy. `codex-grid-background` is advisory and correctly identifies the *intentional* drafting-grid brand motif — not a defect.

Where detector and design review **agree**: `nested-cards` (3) and `cramped-padding` on `.ecosystem-table-wrapper` corroborate Assessment A's cognitive-load finding that the page runs ~9 distinct nested component systems in one scroll. Where the **detector caught what the design review missed**: the 2 `skipped-heading` findings (a real heading-hierarchy gap, likely an h1→h3 jump inside one of the `{=html}` blocks) and the mobile-only `body-text-viewport-edge` bleed are genuine, source-independent defects neither reviewer would catch by reading markdown alone. Where the **design review caught what the detector missed**: the detector's blanket contrast alarm is mostly noise, but Assessment A independently flagged a specific, real contrast gap — `--text-muted` (#8c7562) used at 0.82–0.85rem body-size on `.pub-editorial-authors` and similar meta labels, which does compute under 4.5:1 against parchment/white.

**Visual overlays**: No browser-automation tool was available in this session, so no injected overlay exists in a `[Human]` tab — do not expect to see one. The detector's URL-scan mode did drive a real headless Chromium/Puppeteer instance against the live page (confirmed by its DOM/computed-style-specific findings), which is legitimate mechanical evidence, but it produced no screenshots and no console capture. Treat the finding list above as the full extent of the automated visual evidence for this run.

## Overall Impression

The page's voice is genuinely good — specific, lived-in, archaeologist-to-archaeologist — but it's buried under its own thoroughness. Five tools organized into three phases is told three separate times in three different formats (pipeline cards → prose recap → spec table) before the visitor ever reaches the one section that tells them what to actually click. The single biggest opportunity is subtraction, not addition: cut the redundant middle third and the page's real strengths — the empathetic hero, the trust-building "you stay in charge" framing, the concrete phase connectors — would read far stronger.

## What's Working

1. **The hero and "Made by archaeologists" copy are specific, not marketing fluff** — leading with lived pain ("retyping the notes off a stack of inventory cards") before any product claim is a genuine differentiator.
2. **The "will this replace my judgment?" anxiety is preempted before a visitor could even form it**, and reinforced (perhaps one time too many, see P3-adjacent note) across the page.
3. **The inter-phase connector pills** ("Isolated Vessel Drawings," "Refined Vector Profiles") turn a generic workflow diagram into something concretely archaeological — this is the single most product-specific design decision on the page.

## Priority Issues

**[P0] Triple redundancy of the same 5-tool/3-phase content**
*Why it matters*: The pipeline stage cards (with subtool subgrids), the "From the Old Workflow to the New One" prose section, and the 6-column ecosystem table all restate the identical tool→phase mapping back-to-back. This is the primary driver of the page's cognitive-load failures (fails "single focus," "one-thing-at-a-time," and "progressive disclosure" on the checklist) and is corroborated by the detector's `nested-cards` and `cramped-padding` findings on the same region.
*Fix*: Keep the pipeline cards as the canonical representation. Compress "From the Old Workflow" to a 2–3 sentence bridge (or cut it), and move the ecosystem table to a linked technical-reference page rather than inlining it here.
*Suggested command*: `/impeccable distill`

**[P1] Accessibility debt: unlabeled icons, skipped heading level, and undersized-text contrast**
*Why it matters*: The five tool-logo `<img>` tags in the ecosystem table (docs_home.qmd lines 503, 511, 519, 527, 535) have no `alt` attribute at all, unlike the properly labeled `.pipeline-tool-logo` images elsewhere — a screen reader gets filenames or nothing. The detector independently found 2 `skipped-heading` occurrences (a heading level jump), and Assessment A independently identified `--text-muted` (#8c7562) at 0.82–0.85rem on `.pub-editorial-authors` and similar meta labels computing under WCAG AA's 4.5:1 minimum for body-size text.
*Fix*: Add `alt=""` to the five ecosystem-table logos (decorative; the link text already names the tool). Audit the `{=html}` blocks for the heading jump and insert the missing level. Darken `--text-muted` for any body-size (not just caption-size) usage.
*Suggested command*: `/impeccable audit`

**[P1] Mobile: body text bleeds to the viewport edge and padding gets cramped**
*Why it matters*: At 390px width the detector found 2 `body-text-viewport-edge` findings — a 726-character and a 175-character paragraph both sitting flush against the right edge with no breathing room — plus `cramped-padding` rising from 1 finding (desktop) to 3 (mobile), including vertical padding under 4px for 12px+ text. A mobile reader on a real device will experience this as text touching the screen bezel.
*Fix*: Ensure body paragraphs inherit a consistent side gutter at narrow widths (check any `{=html}` block that sets its own inline padding, since these tend to escape the stylesheet's responsive rules) and bump cramped vertical padding to the ≥4px the detector flags as the floor for that text size.
*Suggested command*: `/impeccable adapt`

**[P2] Getting Started — the one clearly actionable section — is buried second-to-last**
*Why it matters*: It sits after the phase pipeline, the prose recap, the 6-column spec table, and the 4-card values grid. Assessment A's Jordan-persona walkthrough shows a first-time visitor plausibly disengaging from the redundant middle third before ever reaching it.
*Fix*: Move a condensed version (even just the 5-item numbered list, without re-explaining each tool) to directly follow the hero/trust section, and let the technical depth (spec table, values grid) live further down for visitors who scroll that far.
*Suggested command*: `/impeccable layout`

**[P3] Six divergent pill/badge species dilute a stable "what does this badge mean" pattern**
*Why it matters*: `pipeline-stage-pill`, `module-ver-badge`, `pipeline-saver-pill`, `pipeline-chip`, `hw-tag`, and `pub-journal-pill` are all visually distinct small rounded labels doing loosely related jobs (phase, version, time-saved, capability, hardware, journal) — consistent with the Consistency heuristic scoring a 3 instead of 4.
*Fix*: Consolidate to 2–3 archetypes (e.g., one "status/phase" pill style, one "metric/chip" style) reused with color/icon variation rather than structural variation.
*Suggested command*: `/impeccable typeset`

## Persona Red Flags

**Jordan (First-Timer)**: Hits three full retellings of the same 5-tool/3-phase content (pipeline cards → prose recap → spec table) before reaching Getting Started — the section that actually tells them what to click first. Likely to disengage mid-scroll.

**Sam (Accessibility-Dependent)**: The five unlabeled `<img>` tool-logo icons in the ecosystem table (docs_home.qmd L503–535) will announce as filenames or nothing to a screen reader. The 2 detector-confirmed skipped heading levels break linear heading-navigation for screen-reader users. `.pub-editorial-authors` and similar small meta labels fall under WCAG AA contrast.

**Casey (Mobile)**: At 390px, two body paragraphs sit flush against the viewport edge with no gutter (detector-confirmed), and the ecosystem table only gains `overflow-x: auto` inside a `@media (max-width: 768px)` block with no scroll affordance (no fade/shadow/"swipe" hint) — a visitor may not realize 4 of 6 columns are off-screen.

## Minor Observations

- `.pipeline-connector-line { background: dashed 1px var(--border-hover); }` (styles.css ~L1273) is invalid CSS shorthand — `background` doesn't accept a border-style keyword, so the intended dashed connector between phase cards likely isn't rendering as designed. Worth a quick visual check.
- The hero's pixelated vase icon has `alt=""` — defensible as decorative, but it's arguably the single most brand-distinctive visual asset on the page.
- The "~60x" / "~90%" efficiency claims recur in the hero, both phase "saver-pills," and phase leads — enough repetition to start reading as marketing despite the otherwise restrained, credible tone.
- One detector rule (`layout-transition`, "transition: width") couldn't be traced to `styles.css` at all — likely from a bundled Bootstrap/Quarto component rather than page-authored CSS; not confirmed as page-relevant.
- The detector's exit code returned 0 on both live-URL scans despite 52 and 37 warning-severity (non-advisory) findings, which contradicts its own documented "exit 2 = findings" contract — a tooling discrepancy worth flagging to whoever maintains the detector script, separate from this page's own issues.

## Questions to Consider

- If a visitor reads only the hero and Getting Started, does the page still succeed — and if so, what is the other two-thirds of the scroll actually for?
- Does the ecosystem table serve anyone who hasn't already absorbed the pipeline cards above it, or does it exist because "documentation sites have a specs table"?
- Would a skeptical archaeologist be more reassured by four spaced restatements of "you stay in charge," or by one concrete example of an actual correction workflow?
