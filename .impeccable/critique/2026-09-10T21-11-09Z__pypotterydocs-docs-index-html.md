---
target: PyPotteryDocs/docs/index.html
total_score: 14
max_score: 36
na_heuristics: 9
p0_count: 2
p1_count: 2
target_identity: "file:C:\\Users\\larth\\Documents\\PyPottery\\PyPotteryDocs\\docs\\index.html"
target_fingerprint: "sha256:b3b7b787846e27bb47c1dbd1a0e5935dd2a3c369b5a78f0baadf4126b868b80e"
target_path: "C:\\Users\\larth\\Documents\\PyPottery\\PyPotteryDocs\\docs\\index.html"
timestamp: 2026-09-10T21-11-09Z
slug: pypotterydocs-docs-index-html
---
Method: dual-agent (A: 1ee8067e-5692-40b5-85f4-aef1f585ad49 · B: 1aa11ab1-ec35-498d-8ce9-e7701fdba71a)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|:-----:|-----------|
| 1 | Visibility of System Status | 1/4 | Pipeline status unstated; steps 2 & 4 locked without dates; unpausable orbit animation |
| 2 | Match System / Real World | 2/4 | Real-world pipeline logic, but generic SaaS rocket emojis and planetary orbit replace archaeological visual language |
| 3 | User Control and Freedom | 1/4 | No top navbar, no search bar, no motion toggle, users trapped into linear scrolling |
| 4 | Consistency and Standards | 1/4 | Jarring UI/color disconnect with Quarto docs subpages; alternating left/right card alignment breaks reading flow |
| 5 | Error Prevention | 2/4 | Pixel assistant iframe is an inoperable prop; direct GitHub releases link without installers |
| 6 | Recognition Rather Than Recall | 2/4 | No visual previews of output plates/drawings; duplicate publication citations with identical titles |
| 7 | Flexibility and Efficiency | 1/4 | Zero installation accelerators (no `pip install`), no keyboard shortcuts, no search bar |
| 8 | Aesthetic and Minimalist Design | 2/4 | AI slop artifacts (gradient text, glows), dead bento grid CSS; hides actual pottery to show marketing fluff |
| 9 | Error Recovery | n/a | Static landing page with no forms or interactive input transactions |
| 10 | Help and Documentation | 2/4 | Links exist, but zero quickstarts, no hardware prerequisites (CUDA/MPS), fake assistant prop |
| **Total** | | **14/36** | **Needs Major Overhaul (Failing Grade: 38.8%)** |

---

## Design Specificity Verdict

### LLM Assessment (Design Director)
**Verdict: Category-Interchangeable AI SaaS Template ("The Ghost Pottery Problem")**
If one replaced "Pottery" with "Invoices", "Crypto", or "Legal Documents", the page would function without altering a single visual token, color value, or layout container.
- **Absence of Domain Artifacts**: Archaeological pottery documentation is an intensely tactile, precision-oriented field celebrated for stippling, profile cross-sections, rim diameter gauges, and Munsell charts. **There is not a single drawing, photo, or vector sherd anywhere on the landing page.**
- **Aesthetic Disharmony**: The neon indigo (`#4f46e5`) and hot pink (`#ec4899`) palette ignores archaeological materiality (terracotta, slip glaze, kiln black, archival India ink).
- **Template Residue**: The source contains abandoned CSS and JS remnants of an earlier Bento Grid layout (`.bento-grid`, `.card-large`, `.glass-overlay`), proving adaptation from an unrelated starter template.

### Deterministic Scan (Impeccable Detector)
The automated detector flagged **16 warnings** (0 errors):
- **11 Low-Contrast Violations (`low-contrast`)**:
  - Coming-soon step headers and descriptions fail WCAG AA (2.5:1 vs 4.5:1).
  - Publication card metadata (`.pub-meta`) has 2.5:1 contrast against `#ffffff`.
  - Preprint badges have 2.1:1 contrast against light backgrounds.
  - Footer copyright text (`#6b7280` on `#111827`) fails with 3.7:1 contrast.
- **5 Slop Anti-Patterns**:
  - `gradient-text`: Clipped text gradient in hero H1 (`#4f46e5` to `#ec4899`).
  - `ai-color-palette`: Default AI SaaS purple/violet/pink scheme.
  - `dark-glow`: Zero-offset indigo glowing halos on timeline progress and active dots (`box-shadow: 0 0 15px rgba(79, 70, 229, 0.5)`).
  - `side-tab`: Flagged on `.software-card::before` (determined to be a **false positive** on `index.html` as the class only exists in dead global CSS).

### Visual Overlays
Static HTML file analysis. No active development server or browser automation canvas detected. Static AST analysis provided 100% deterministic rule coverage.

---

## Overall Impression
PyPottery has world-class scientific backing (peer-reviewed papers in DAACH and JCH) wrapped in a generic 2023 AI SaaS wrapper that hides the pottery. The single biggest opportunity is transforming the hero from an abstract planetary orbit into a tactile, high-precision archaeological proof-of-work showcase.

---

## What's Working
1. **Legitimate Academic Rigor**: Real peer-reviewed journal articles with DOIs instantly elevate PyPottery above 99% of open-source AI projects.
2. **Clear Conceptual Pipeline**: Deconstructing post-excavation documentation into Extraction → Vectorization → Plate Assembly mirrors actual archaeological monograph production.
3. **Scroll-Driven Spine Architecture**: The central vertical progress timeline provides a solid narrative scaffolding for showcasing a multi-step suite.

---

## Priority Issues

### [P0] What: The "Ghost Pottery" Problem — Zero Archaeological Visuals
- **Why it matters**: Archaeologists and illustrators judge tools by vector accuracy, line weight preservation, and rim curvature fidelity. Without visual evidence, they will not risk field data.
- **Fix**: Replace the hero orbit with an interactive before-and-after loupe comparing an archival field sketch with the vectorized PyPottery plate.
- **Suggested command**: `/impeccable clarify`

### [P0] What: Broken Workflow Narrative via "Coming Soon" Padlocks
- **Why it matters**: Steps 2 and 4 display giant padlock emojis (`🔒`). It makes 40% of the advertised pipeline look like vaporware and creates the false impression that PyPottery is unusable today.
- **Fix**: Reorganize the pipeline around the **three shipping tools**: Lens (Extraction), Ink (Vectorization), and Layout (Assembly). Move unreleased modules to a discrete roadmap section.
- **Suggested command**: `/impeccable distill`

### [P1] What: Navigation Void & Documentation Disconnect
- **Why it matters**: `index.html` lacks a header navbar and search bar. Transitioning to Quarto docs (`intro.html`) causes a jarring visual shock with a completely different purple theme and layout.
- **Fix**: Add a unified persistent header across all pages with logo, search trigger (`Cmd+K`), navigation anchors, and harmonize CSS variables.
- **Suggested command**: `/impeccable layout`

### [P1] What: Reading Ergonomics & Low Contrast in Timeline Cards
- **Why it matters**: Left timeline cards enforce `text-align: right` on multi-line text, destroying reading speed. Text colors (`#9ca3af`) fail WCAG AA contrast.
- **Fix**: Left-align all card typography within a disciplined grid and elevate text colors to `#374151` / `#4b5563` ($\ge 4.5:1$).
- **Suggested command**: `/impeccable typeset`

### [P2] What: Self-Diluting Publication Grid & Fake "Pixel" Assistant
- **Why it matters**: Duplicating journal papers as preprints looks like citation padding. The non-interactive "Pixel" iframe acts as a deceptive, broken affordance.
- **Fix**: Consolidate into 2 authoritative journal cards with secondary preprint links. Replace Pixel with a copyable `pip install` terminal block.
- **Suggested command**: `/impeccable polish`

---

## Persona Red Flags

- **Dr. Elena (Field Archaeologist & Ceramic Specialist)**: Sees "PyTorch, YOLOv8, and SAM2" and fears engineering complexity; encounters padlocks on Steps 2 & 4 and assumes the software is broken; clicks "Download" and is dumped into raw GitHub wheel files.
- **Liam (Computational Archaeologist & Contributor)**: Finds no quick-start terminal command in hero; inspects code and finds dead Bento Grid CSS; finds no latency benchmarks.
- **Prof. Marcus (Archaeology Department Chair)**: Distrusts the neon pink SaaS aesthetic and rocket emojis for scholarly work; immediately flags duplicate preprints in the bibliography.

---

## Minor Observations
1. In hero, rotating `.orbit-system` causes the child center logo to tilt and flip upside down during spin.
2. CSS orbit rings are 300px/500px, but JS radius is 220px, causing icons to drift between tracks.
3. Unused CSS rules (`.bento-grid`, `.card-large`, `.glass-overlay`) clutter the stylesheet.
4. Iframe `pixel_assistant.html` lacks a `title` attribute (WCAG 4.1.2).
5. External publication links use `target="_blank"` without `rel="noopener noreferrer"`.

---

## Questions to Consider
1. What if the hero featured an interactive before/after split viewer comparing an excavation pencil sketch to an archival vector plate?
2. What if the color palette drew from terracotta, slip glaze, and archival drafting ink instead of generic SaaS neon indigo and pink?
3. What if the pipeline focused exclusively on the three shipping tools (Lens, Ink, Layout) rather than advertising unreleased features?
