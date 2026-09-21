# Licenses and third-party notices

This is a good-faith engineering review of the licenses involved in PyPottery, not legal advice. It was checked against the `requirements.txt` files of the suite and of each app, the code that imports the libraries, and the model pages on Hugging Face (2026-09-21).

## Summary

- **The suite launcher, Ink, Layout, Scan and Trace are Apache-2.0.** Every dependency they use is permissive (MIT / BSD / Apache-2.0 / PSF), or weak copyleft used as an unmodified library (LGPL-3.0, MPL-2.0). No conflict with Apache-2.0.
- **PyPotteryLens is GPL-3.0, and depends on two AGPL-3.0 libraries** (`ultralytics`, `PyMuPDF`). This is the only real licensing tension in the suite (see below). It does not affect the other apps, because the launcher starts every app as a separate process and only talks to it over HTTP (mere aggregation, no linking).
- **The public pages (README, docs site, citation metadata) call PyPottery "open source" without naming a license.** The license of each repository is the one in its own `LICENSE` file, listed in the table below; keep those files in place, since both Apache-2.0 and GPL-3.0 require the license text to travel with the code.
- **One model has non-open terms:** `stabilityai/sd-turbo` (used by Ink) is under the Stability AI Community License.

## PyPottery components

| Component | License | Notes |
|---|---|---|
| Launcher / suite (this repo) | Apache-2.0 | `LICENSE.txt` |
| PyPotteryInk | Apache-2.0 | Derived from `img2img-turbo` (MIT); its notice must be kept |
| PyPotteryLayout | Apache-2.0 | |
| PyPotteryScan | Apache-2.0 | |
| PyPotteryTrace | Apache-2.0 | |
| **PyPotteryLens** | **GPL-3.0** | Imports `ultralytics` and `fitz` (PyMuPDF), both AGPL-3.0 |

## The Lens question

`PyPotteryLens/utils.py` does `import fitz` and `from ultralytics import YOLO`. Both libraries are AGPL-3.0 (or commercial, sold separately by their vendors).

- GPL-3.0 and AGPL-3.0 can be combined (GPL-3.0 section 13, AGPL-3.0 section 13). So Lens under GPL-3.0 is **not an outright violation**, but the combined work must also honour the AGPL network clause: whoever lets other people use Lens over a network (a hosted service, for example) has to offer them the corresponding source. Used locally, as the suite intends, this has no practical effect.
- The trained YOLO weights that Lens downloads (`lrncrd/PyPotteryLens`, `BasicModelv8_v01.pt`) come out of the Ultralytics training pipeline. Ultralytics treats such weights as AGPL-3.0 material unless an enterprise license is held.
- Apache-2.0 code can be included in a GPL-3.0/AGPL-3.0 project, never the other way around. Lens therefore cannot be relicensed to Apache-2.0 while it keeps these two dependencies.
- The Windows/macOS packages ship the launcher, the Python runtime and Flask-level libraries only. Heavy libraries (torch, ultralytics, PyMuPDF...) are installed on the user's machine at first run and are not redistributed in the release archives. Lens is downloaded as its own repository.

**Recommendations** (none applied automatically):

1. Keep Lens's own `LICENSE` file (GPL-3.0) in its repository and never ship it as if it were covered by the suite's `LICENSE.txt`. Public pages may say "open source", but must not state that the whole suite is under one license.
2. Either relicense Lens to **AGPL-3.0** so its license matches what it really depends on, or replace `ultralytics`/`PyMuPDF` (for PDF rendering: `pypdfium2` is Apache-2.0/BSD; for detection: an Apache/MIT detector such as RT-DETR / DETR implementations in `transformers`, retraining the weights).
3. State the AGPL status of the YOLO weights next to the download in Lens.

## Dependencies by app

Only libraries whose license is not plain MIT / BSD / Apache-2.0 / PSF are called out; everything else in the `requirements.txt` files is permissive.

| Library | Used by | License | Impact |
|---|---|---|---|
| `ultralytics` | Lens | **AGPL-3.0** (or commercial) | see above |
| `PyMuPDF` | Lens | **AGPL-3.0** (or commercial) | see above |
| `CairoSVG` | Trace | LGPL-3.0 | Fine: unmodified, installed as a normal package the user can replace |
| `tqdm`, `certifi` | several | MPL-2.0 (tqdm: MPL-2.0 AND MIT) | Fine: file-level copyleft, unmodified |
| `torch`, `torchvision` | Ink, Lens, Scan, Trace | BSD-3-Clause | The CUDA wheels pull NVIDIA runtime libraries under NVIDIA's own EULA; they are downloaded by the user's machine, not redistributed by PyPottery |
| `transformers`, `diffusers`, `peft`, `accelerate`, `timm`, `sam2`, `openai`, `huggingface_hub`, `compressed-tensors`, `rectpack` | various | Apache-2.0 | none |
| `bitsandbytes`, `flask-cors`, `openpyxl`, `svgwrite`, `rdp`, `GPUtil`, `pydantic`, `PyYAML` | various | MIT | none |
| `numpy`, `scipy`, `pandas`, `scikit-image`, `Flask`, `Werkzeug`, `Jinja2`, `psutil`, `reportlab`, `matplotlib`, `seaborn`, `Pillow`, `opencv-python` | various | BSD / PSF / HPND / MIT / Apache-2.0 | none |

## Models downloaded at run time

| Model | Used by | License | Notes |
|---|---|---|---|
| SAM 2 checkpoints (Meta) | Trace | Apache-2.0 | |
| `Qwen/Qwen3.5-2B` | Scan | Apache-2.0 | |
| `zai-org/GLM-OCR` | Scan | MIT | Its layout stage (PP-DocLayoutV3) is Apache-2.0 |
| `google/gemma-4-E2B-it` | Lens | Apache-2.0 | |
| `stabilityai/sd-turbo` | Ink | **Stability AI Community License** | Free for personal/research use and for commercial use below US$1M annual revenue (registration with Stability AI required for commercial use); above that a paid license is needed. Users of Ink inherit this; worth a line in Ink's README |
| PyPotteryInk weights (`lrncrd/PyPotteryInk`) | Ink | own | Fine-tuned from sd-turbo, so subject to its terms too. Publish an explicit license on the model card |
| PyPotteryLens weights (`lrncrd/PyPotteryLens`) | Lens | own / AGPL-3.0 (Ultralytics) | see above |

## Assets bundled with the launcher

| Asset | License | Attribution |
|---|---|---|
| Bootstrap 5.3.3 | MIT | header kept in the minified file |
| Bootstrap Icons 1.11.3 | MIT | header kept in the CSS |
| SheetJS (`xlsx.full.min.js`) | Apache-2.0 | header kept in the file |
| Plus Jakarta Sans, JetBrains Mono (woff2) | SIL Open Font License 1.1 | The OFL asks that the copyright notice and license text travel with redistributed font files: **not yet included**, add them next to `launcher/static/vendor/fonts/` |
| Python runtime (Windows package, WinPython) | PSF / MIT | keep `python/LICENSE.txt` in the package (it is) |

## Open items

- [ ] Decide Lens: relicense to AGPL-3.0, or replace ultralytics / PyMuPDF.
- [ ] Add a licensing note to Ink about sd-turbo (Stability AI Community License) and put an explicit license on the Hugging Face model cards.
- [ ] Ship the OFL text for the two fonts.
- [ ] Re-run this review when `requirements.txt` changes materially.
