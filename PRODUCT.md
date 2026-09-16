# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Archaeologists, ceramic specialists (ceramicists/pottery analysts), archaeological illustrators, museum curators, and academic researchers who document, analyze, vectorize, and publish ceramic finds from archaeological excavations and museum collections.

## Product Purpose
PyPottery digitizes, standardizes, and automates the classical archaeological pottery documentation workflow. It bridges the gap between traditional manual pottery drawing (pencil tracings, ink profile drawings, rim diameter measurements, and publication plate layout assembly) and modern computational archaeology. Success means researchers can produce publication-grade, standardized, vector-accurate ceramic illustrations and catalogs in minutes rather than days of tedious manual inking.

## Positioning
Unlike general-purpose graphic design software (Photoshop, Illustrator, Inkscape) or generic AI image tools, PyPottery is purpose-built by archaeologists for archaeologists. It directly incorporates ceramic scientific conventions (rim orientation, profile sectioning, standardized inking styles, metric scale bars, and publication plate composition) into specialized, local AI and computer-vision pipelines without requiring third-party cloud services or data sharing.

## Operating Context
- **Environments**: Archaeological field excavation dig houses, museum research archives, university laboratories, and personal workstations.
- **Workflow**: Digitizing hand-drawn pottery cards and field sheets, extracting published drawings from excavation monographs and legacy PDFs, enhancing pencil sketches into clean digital inks, interactive SAM2 vector segmentation, and compiling publication-ready plates.
- **Hardware & Security**: Operates completely offline on local researcher hardware (Windows, macOS, Linux). Employs local PyTorch acceleration (NVIDIA CUDA or Apple Silicon MPS) with complete fallback support for standard CPU-only machines, guaranteeing data sovereignty for unpublished excavation finds.

## Capabilities and Constraints
- **PyPotteryScan**: AI-powered digitization of archaeological pottery cards with OCR text recognition.
- **PyPotteryLens**: Computer-vision extraction of ceramic figures and sherd drawings directly from published monograph PDFs.
- **PyPotteryInk**: AI-assisted digital inking of pencil drawings, yielding publication-quality line art.
- **PyPotteryTrace**: Interactive vectorization of ceramic drawings using SAM2 (Segment Anything Model 2) to produce clean SVG vectors.
- **PyPotteryLayout**: Automated generation of publication plates with metric scaling and export to PDF and SVG.
- **Launcher Hub**: Unified local server and process manager orchestrating isolated Python virtual environments, hardware detection, shared AI weight caches, and system diagnostics.

## Brand Commitments & Design System
- **Tone**: Scholarly, precise, and authentic, celebrating the craft of pottery documentation while welcoming users with beloved archaeological pop-culture touches (ASCII terminal banner, classic cinema quotes).
- **Design Metaphor**: Archaeological field desk meets precision drafting room—drawing paper, terracotta clay sherds, Mediterranean Aegean glazes, and dark terminal workstations.

### Color Palette Tokens
| Token / Role | Hex / Value | Usage & Context |
| :--- | :--- | :--- |
| **Terracotta Primary** | `#c2410c` | Primary CTA buttons, active states, key brand elements, focus rings |
| **Terracotta Dark** | `#9a3412` | Hover state for primary buttons, active pill backgrounds |
| **Terracotta Light / Accent** | `#ea580c` | Secondary terracotta accents, badge highlights |
| **Terracotta Soft / Glow** | `rgba(194, 65, 12, 0.08)` / `#fff7ed` | Subdued badge fills, active navigation highlights, glowing shadows (`rgba(194,65,12,0.15)`) |
| **Nero Caffè (Coffee Black)** | `#1c1917` (Stone 900) / `#1c1309` | Dark developer card (`.developer-box`), site navigation header (`#quarto-header`), terminal bars, and footer (`.site-footer`) |
| **Obsidian Dark Surface** | `#12100e` | Inner terminal code viewport (`.developer-terminal`), git clone console background |
| **Dark Console Border** | `#292524` / `#44403c` | Borders and dividers across dark developer boxes and terminal headers |
| **Dark Surface Foreground** | `#f5f5f4` / `#a8a29e` | Light stone text and subdued secondary labels inside dark containers |
| **Mediterranean Glaze Teal** | `#0d9488` / `#0f766e` | Secondary accents, successful offline badges, segmentation tags, interactive vector accents |
| **Teal Soft** | `rgba(13, 148, 136, 0.08)` / `#f0fdf4` | Soft pill backgrounds for "100% Offline" and verified indicators |
| **Parchment Ground (Page)** | `#fbf9f5` / `#fdfbf7` | Warm archaeological paper background for all landing and documentation pages |
| **Sand Ground (Subtle)** | `#f5efe6` / `#f6f3ed` | Secondary surface, sidebar backgrounds, alternating section fills |
| **Pure White Surface** | `#ffffff` | Elevated tool cards, download cards, modal windows |
| **Parchment Borders** | `#e8e3d8` / `rgba(194, 130, 80, 0.16)` | Card outlines, technical dividers, pill borders |
| **Text Main (Dark Earth)** | `#1c1917` / `#1c1309` | Main typography, high-contrast headings, and body reading text |
| **Text Dim (Terra d'Ombra)** | `#57534e` / `#5c4a35` | Subtitles, secondary descriptions, card text |
| **Text Muted** | `#78716c` / `#8c7562` | Meta tags, timestamps, captions, disabled states |
### Visual Motifs & Layout Conventions
- **Carta Millimetrata (Technical Drafting Grid)**: The foundational visual motif for all PyPottery suite applications. Evokes the tactile precision of an archaeological drafting table and millimetric tracing paper:
  - **Global Page Background (`body`)**: Applied to `body` across all apps over warm parchment (`#fbf9f5`) with a fixed dual-layer terracotta grid: minor `14px × 14px` grid at `rgba(194, 65, 12, 0.035)` and major `70px × 70px` grid at `rgba(194, 65, 12, 0.07)`, pinned with `background-attachment: fixed` so the drafting grid stays stable during scrolling.
  - **Canvas & Preview Workspaces**: Mirrored directly inside interactive vectorization canvases, sherd previews, and calibration viewports (`.annotation-canvas-container`, `.tabular-image`) to give ceramic profiles and drawings a physical drafting-sheet context.
  - **Surface Contrast Guarantee**: All functional data surfaces—data tables, forms, cards, and dark consoles—must maintain solid, opaque backgrounds (`#ffffff`, `#fbf9f5`, `#12100e`) to prevent grid moiré and preserve effortless reading comfort during prolonged scientific analysis.
- **Peeking Pixel Watermark**: Low-opacity archaeological vessel watermark (`icon_app.png`, 82% opacity, hover 100%) peeking from behind the main download card, strictly clipped with `clip-path: inset(0 0 22% 0)` to prevent any bottom bleed.
- **Section Transitions**: Clean gradient fading dividers (`<hr class="hero-pipeline-hr">`) fading out smoothly at left and right extremities.
- **Typography**: Dual-type system using `Plus Jakarta Sans` for clean, contemporary scholarly prose and `JetBrains Mono` / `Fira Code` for technical metrics, terminal commands, and coordinate data.
- **Rounded Rectangles**: All cards, panels, badges, buttons, and container elements must use subtly rounded corners (`border-radius: 8px` for cards and panels, `border-radius: 6px` for buttons and badges, `border-radius: 4px` for small inline chips). Sharp right-angle rectangles are forbidden in UI components; the soft radius reinforces the hand-crafted, parchment-grounded aesthetic.
- **Bootstrap Icons (No Emoji)**: All iconographic communication must use [Bootstrap Icons](https://icons.getbootstrap.com/) (`<i class="bi bi-*"></i>`) loaded via the official Bootstrap Icons CSS. Emoji characters are strictly prohibited in UI copy, labels, badges, buttons, and navigation elements. Choose semantically accurate Bootstrap Icon glyphs (e.g., `bi-archive` for archive/storage, `bi-cpu` for hardware, `bi-file-earmark-pdf` for PDF export) to maintain visual consistency and accessibility across platforms.
- **Splash Screen Progress Bar**: The initial environment loading progress track must have an outer vertical height of `22px` (`height: 22px; padding: 2.5px; border-radius: 9999px; background: #e8e3d8; box-shadow: inset 0 1px 3px rgba(28, 25, 23, 0.12);`), and its inner fill must use the Terracotta gradient (`linear-gradient(90deg, #c2410c, #ea580c)`) with centered white percentage typography (`font-size: 0.76rem; font-weight: 700; line-height: 1; letter-spacing: 0.03em;`). This ensures comfortable vertical breathing room across all PyPottery applications so the percentage label does not touch or overflow the pill boundary.
- **App Header Version Badge**: The version pill badge (`.version-badge`) beside the application title must be optically and vertically centered with the headline text (`display: inline-flex; align-items: center; justify-content: center; line-height: 1; font-family: var(--font-mono); font-size: 0.72rem; font-weight: 700; padding: 3px 8px; border-radius: var(--radius-full); transform: translateY(2px);`). The `translateY(2px)` offset optically balances the pill against the cap-height of the title, preventing the badge from floating too high above the visual baseline.

## Evidence on Hand
- Complete source implementations across five suite modules (`PyPotteryScan`, `PyPotteryLens`, `PyPotteryInk`, `PyPotteryTrace`, `PyPotteryLayout`).
- Scientific documentation and tutorials in `PyPotteryDocs/`.
- Suite configurations in `launcher/config/apps.json`.
- Official vector and brand assets in `PyPotteryDocs/imgs/`.

## Product Principles
1. **Respect Archaeological Drawing Conventions**: Outputs must faithfully respect classical ceramic publication standards (rim orientation, metric scale bars, profile section hatching).
2. **Local-First and Data Sovereign**: Archaeological discoveries often involve sensitive, unpublished contextual data; all processing remains strictly local with zero cloud telemetry.
3. **Ergonomic Scientific Craft**: Eliminates repetitive manual tracing and plate layout alignment, liberating researchers to focus on analysis and typo-chronological interpretation.
4. **Inclusive Hardware Resilience**: Ensures high-end AI capabilities degrade gracefully to run reliably on field laptops without requiring expensive GPUs.
