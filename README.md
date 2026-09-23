# ShareOfShelf

**Retail shelf analytics from a single photo.** ShareOfShelf finds every product on
a shelf photo, identifies the exact SKU (stock-keeping unit) of each facing, and
reports **share of shelf** by number of facings and by shelf space.

It is built for the Iranian beverage market. It ships with a labelled knowledge base
of **18 Sunich juice SKUs** (1 L and 750 ml, 9 flavours each), plus two special
buckets: `unknown_beverage` for off-brand drinks and `non_beverage` for everything
else on the shelf. Adding a new product needs no training run. You drop a few
reference photos into a folder.

```
shelf photo ─► YOLOv8 detect ─► merge split boxes ─► DINOv2 embed ─► LDA / kNN match ─► gates ─► share of shelf
                                                                          ▲
                                                        labelled knowledge base (reference crops)
```

The repository has two parts:

| Part | Folder | What it is |
| --- | --- | --- |
| Python pipeline | repository root | Detection, identification, evaluation and a small HTTP API |
| Web dashboard | [`web-base44/`](web-base44/) | Persian (RTL) React app on [Base44](https://base44.com). Its Shelf Analysis page calls the Python API |

---

## Contents

1. [Features](#features)
2. [How it works](#how-it-works)
3. [Installation](#installation)
4. [Run the pipeline on a shelf photo](#run-the-pipeline-on-a-shelf-photo)
5. [Command-line options](#command-line-options)
6. [Share-of-shelf report](#share-of-shelf-report)
7. [Detection API for the web app](#detection-api-for-the-web-app)
8. [Knowledge base](#knowledge-base)
9. [Evaluating accuracy](#evaluating-accuracy)
10. [Optional features](#optional-features): OCR, OpenAI fallback, unknown-beverage tools
11. [Configuration (environment variables)](#configuration-environment-variables)
12. [Project structure](#project-structure)
13. [Tests](#tests)
14. [Accuracy notes and known limitations](#accuracy-notes-and-known-limitations)
15. [Troubleshooting](#troubleshooting)
16. [Acknowledgements](#acknowledgements) and [License](#license)

---

## Features

- **Product detection.** A YOLOv8m model trained on SKU-110K finds every facing on
  the shelf. When YOLO splits one tall bottle into a top box and a bottom box, the
  two are merged back together.
- **SKU identification without training.** Each crop is embedded with
  [DINOv2](https://huggingface.co/facebook/dinov2-base) and matched against a folder
  of labelled reference crops. The default matching head is Linear Discriminant
  Analysis (LDA), fitted on the fly each run. It separates look-alike flavours much
  better than plain cosine similarity.
- **Open-set handling.** Crops that match nothing well enough become
  `low_confidence` and are left out of the share. Off-brand drinks go to
  `unknown_beverage`. Non-drinks (`non_beverage`) are skipped entirely.
- **Share of shelf** per SKU, by facings and by pixel area, as a console table and
  as CSV.
- **Detection API** (`shelf_api.py`). A small read-only HTTP API used by the web
  dashboard in [`web-base44/`](web-base44/).
- **Optional helpers:** OCR for bilingual Persian/English labels (`--ocr`), an
  OpenAI vision fallback for rejected crops (`--llm-fallback`), DBSCAN clustering of
  unknown crops, and a vision-LLM + web-search pipeline that suggests names for
  unknown products.
- **Honest evaluation.** Source-photo-grouped cross-validation and leakage checks,
  so reported accuracy is not inflated by near-duplicate crops.

## How it works

1. **Detect.** `models/best.pt` (YOLOv8m, trained on SKU-110K) predicts a box for
   every product with confidence ≥ 0.5. `src/detect.py` merges vertically adjacent
   boxes that belong to the same item, then saves a padded crop per box.
2. **Embed.** Each crop is letterboxed (padded to a square, not center-cropped,
   which would cut away most of a tall bottle) and embedded with DINOv2 into a
   768-dimensional vector. By default 5 augmented views of each crop are averaged
   (test-time augmentation, TTA).
3. **Match.** The vector is compared against every reference crop in
   `data/knowledge_base/crops/object/<class>/`. The folder name is the label. There
   are three matching heads:
   - `lda` (default): a supervised head fitted on the knowledge-base embeddings. It
     learns which embedding dimensions carry flavour rather than bottle shape.
   - `knn`: a weighted vote over the k nearest reference crops.
   - `prototype`: one mean vector per class. Kept for comparison; it confuses
     near-identical SKUs.
4. **Gate.** A prediction is accepted only if its score clears `--sim-threshold`
   and its lead over the runner-up clears `--margin-threshold`. Anything else
   becomes `low_confidence`.
5. **Aggregate.** Named beverages and `unknown_beverage` are counted as facings.
   Shares are computed over those facings only. `low_confidence` and
   `non_beverage` crops are in neither the numerator nor the denominator.

Knowledge-base embeddings are cached in
`data/knowledge_base/crops/object/.kb_cache.pkl`. The cache rebuilds itself
automatically when images are added or removed, or when you switch embedding
model.

## Installation

**Requirements**

- Python **3.11 or 3.12**.
- About 3 GB of disk for dependencies (much more with the CUDA build of torch).
- Internet on the first run only, to download DINOv2 from Hugging Face (~330 MB).
- A GPU is optional. Everything runs on CPU.

Everything else is in the repository: the YOLO weights (`models/best.pt`, ~52 MB),
the labelled knowledge base, sample shelf photos and the evaluation test set.

```bash
git clone <repo-url>
cd ShareOfShelf
```

### Option A: venv + pip (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1

# CPU-only machine? Install the small CPU build of torch first (optional).
# Without this, pip installs the default CUDA build, which is several GB.
pip install torch==2.13.0 torchvision==0.28.0 --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
```

### Option B: uv

`pyproject.toml` declares the same dependencies and routes torch to the CPU wheel
index:

```bash
uv sync                                   # core pipeline
uv sync --extra llm --extra ocr           # plus the optional features
```

Then prefix commands with `uv run`, for example `uv run python main.py --input ...`.

### Option C: conda

```bash
conda env create -f env.yaml
conda activate share-of-shelf
```

### Optional extras

The core install covers `main.py`, `evaluate.py`, `report.py`, `shelf_api.py`,
`tools/` and `src/cluster.py`. These features need extra packages (also listed at
the bottom of `requirements.txt`):

| Feature | Install |
| --- | --- |
| OCR (`--ocr`) | `pip install easyocr` |
| OpenAI fallback (`--llm-fallback`) | `pip install "openai>=1.0"` |
| Unknown-beverage naming pipeline | `pip install "openai>=1.0" ddgs` |
| Running the tests with pytest | `pip install pytest` (the tests also run without it) |

## Run the pipeline on a shelf photo

Run all commands from the repository root. Paths are relative to it.

```bash
python main.py --input data/sample/2025.jpg
```

**The first run is slow.** It downloads `facebook/dinov2-base` and embeds every
knowledge-base image, which takes a few minutes on CPU. After that the embeddings
are cached and later runs start almost instantly.

### Sample photos

| Image | Description |
| --- | --- |
| `data/sample/2025.jpg` | Sunich juice shelf |
| `data/sample/46.jpg` | One row of Sunich bottles, close up |
| `data/sample/t2.jpg` | Large multi-row shelf, mixed brands |
| `data/sample/PXL_20260807_132315005.MP.jpg` | Full-resolution 12 MP original (good for OCR) |
| `data/sample/*.jpg` | More raw shelf photos |
| `data/sample/shelf_sunich/`, `data/sample/sunich_shelf_2/` | More shelf photo sets |

### Output

For an input `.../<name>.jpg`, results are written to `data/<name>/` (for example
`data/sample/2025.jpg` → `data/2025/`). This folder is generated and gitignored.
`main.py` deletes the previous results in that folder before every run, so results
from two runs are never mixed.

```
data/<name>/
├── <name>_annotated.jpg          # the photo with detection boxes drawn on it
├── predictions.txt               # crop -> product (confidence) [source], human-readable
├── predictions.csv               # crop,product,confidence,source
├── share_of_shelf.csv            # product,facings,share_by_facings,share_by_space
├── crops.csv                     # crop -> source photo + box (provenance manifest)
└── crops/
    ├── <product_name>/           # crops confidently identified as this product
    ├── low_confidence/           # no match cleared the gates
    └── _skipped_non_beverage/    # matched the non_beverage class
```

A share-of-shelf table is also printed to the console. The input photo is never
modified.

## Command-line options

Full list: `python main.py --help`.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--input PATH` | required | Shelf photo to analyse |
| `--model {dino2,resnet18}` | `dino2` | Embedding model. ResNet18 is faster but clearly less accurate |
| `--match-mode {lda,knn,prototype}` | `lda` | Matching head (see [How it works](#how-it-works)) |
| `--sim-threshold X` | `0.30` for lda, `0.60` for knn/prototype | Minimum score to accept a match. For `lda` the score is a posterior probability; for `knn`/`prototype` it is cosine similarity |
| `--margin-threshold X` | `0.05` for lda, off otherwise | Minimum lead of the best class over the runner-up. Catches coin-flips between look-alike flavours. `0` disables it |
| `--conf-threshold X` | `0.4` | Minimum vote share, `knn` mode only |
| `--tta` / `--no-tta` | on | Test-time augmentation (5 views per crop). `--no-tta` is about 3.5× faster |
| `--no-merge` | off | Disable merging of split boxes (rarely needed) |
| `--ocr` | off | Use label text to re-rank close calls (see [OCR](#ocr---ocr)) |
| `--llm-fallback` | off | Send rejected crops to an OpenAI vision model (see [OpenAI fallback](#openai-vision-fallback---llm-fallback)) |

Examples:

```bash
python main.py --input data/sample/46.jpg --no-tta              # faster
python main.py --input data/sample/46.jpg --match-mode knn      # other matching head
python main.py --input data/sample/46.jpg --sim-threshold 0.20  # fewer rejections, more mistakes
python main.py --input data/sample/46.jpg --model resnet18      # faster, less accurate embedder
```

Why the `lda` threshold is loose: off-brand products are meant to be caught by the
`unknown_beverage` / `non_beverage` classes, not by the score gate. Raising it
mostly rejects correct predictions. The margin gate is what catches ambiguous
flavours. Both defaults were chosen with `tools/gate_sweep.py`; re-run it if you
change the embedding model or the knowledge base a lot.

## Share-of-shelf report

```bash
python report.py --input data/2025/predictions.csv
python report.py --input data/2025/predictions.csv --html
```

Breaks the predictions down by brand and by product (`brand_size_flavour`).
`--html` also writes a standalone `report.html` next to the CSV. Like `main.py`, the
report leaves `low_confidence` crops out of the totals.

## Detection API for the web app

```bash
python shelf_api.py                      # http://127.0.0.1:8001
```

`shelf_api.py` serves the pipeline over HTTP for one uploaded photo at a time. It
uses the same YOLO weights, box merging, matching head and gates as `main.py`,
returns per-crop results plus the share-of-shelf table, and **never writes to the
knowledge base**. The dashboard in `web-base44/` calls it from its Shelf Analysis
page.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/state` | `loading` / `ready` / `error`, plus the model and match mode |
| `POST` | `/api/upload?name=<file>` | Raw image bytes in the body. Saved to `data/_uploads/`. Returns `{"path": ...}` |
| `POST` | `/api/detect` | Body `{"image": "<path from upload>", "tta": true}`. Returns `{"session": "<id>"}` |
| `GET` | `/api/session/<id>` | Progress (`done` / `total`), then `crops[]`, `share_of_shelf[]`, `total_facings` |
| `GET` | `/api/crop/<id>/<crop>` | One crop image |

Example session:

```bash
curl -X POST --data-binary @data/sample/46.jpg "http://127.0.0.1:8001/api/upload?name=46.jpg"
# {"path": "data/_uploads/20260923-101500-000000-46.jpg"}
curl -X POST -d '{"image": "data/_uploads/20260923-101500-000000-46.jpg"}' http://127.0.0.1:8001/api/detect
# {"session": "b9aa5500"}
curl http://127.0.0.1:8001/api/session/b9aa5500
```

Notes:

- Models load in the background after start-up. Poll `/api/state` until it says
  `ready`.
- It accepts the same threshold flags as `main.py` (`--model`, `--match-mode`,
  `--sim-threshold`, `--margin-threshold`, `--conf-threshold`) plus `--host`,
  `--port` and `--verbose`.
- Uploads go to `data/_uploads/` and per-request crops to `data/_api_sessions/`.
  Both are gitignored and can be deleted at any time.
- CORS is open (`*`), and image paths outside `data/` are refused. The API has no
  authentication and is meant for local use. Do not expose it to the internet
  as-is.

To run the web app against it, see [`web-base44/READEME.md`](web-base44/READEME.md).

## Knowledge base

Predictions are limited to the classes in `data/knowledge_base/crops/object/`, and
accuracy depends mostly on how well those classes are covered.

```
data/knowledge_base/
├── crops/object/<class>/      # reference crops, one folder per class (folder name = label)
├── provenance.csv             # which shelf photo each reference crop came from
└── review_log.csv             # historical audit log of earlier labelling sessions
```

Current contents: 20 class folders (18 Sunich SKUs, `unknown_beverage`,
`non_beverage`) with 437 usable reference images.

### Rules

- **One folder per class**, named `<brand>_<size>_<flavour>`, for example
  `sunich_1L_apple`. Keep all three parts. OCR (`src/ocr.py:split_label`) and
  `report.py` parse them.
- **Only `.jpg` files are loaded.** The loader reads `**/*.jpg`. There are
  currently 29 `.webp` / `.jpeg` / `.png` / `.gif` files in the class folders that
  are ignored. Convert them to `.jpg` if you want them used.
- **At least 2 images per class.** A class with a single image is left out of the
  LDA fit and can never be predicted. `KBIndex` prints a warning when this happens.
- **No sub-folders inside a class folder.** The loader refuses to run if it finds
  one, because every nested folder would silently become a new class.
- **Crops from real shelf photos are worth far more than studio or e-commerce
  shots.** Adding about 180 studio images did not improve grouped-CV accuracy at
  all (see [Accuracy notes](#accuracy-notes-and-known-limitations)).

### Special classes

- `non_beverage`: distractors such as snacks and detergent. Crops that match it are
  skipped, not reported.
- `unknown_beverage`: a drink that is counted as a facing but deliberately not
  given a product name. Put an off-brand or unidentifiable bottle here rather than
  forcing it into a Sunich class.
- **A competitor you can name deserves its own class** (for example
  `sunstar_240ml_orange`). This works better than adding it to `unknown_beverage`
  and also reports the rival's share. When you add a competitor brand, also add its
  Persian and Latin spellings to `BRAND_TERMS` in `src/ocr.py`, so `--ocr` can
  recognise the brand text.

### Adding a product

1. Create `data/knowledge_base/crops/object/<brand>_<size>_<flavour>/`.
2. Copy in a few clean `.jpg` crops of that product. Good sources are the
   `crops/low_confidence/` and `crops/unknown_beverage/` folders from earlier
   `main.py` runs. For bilingual packs, include both the Persian and the English
   face: a shelf can show either.
3. Optional but recommended: record which shelf photo each new crop came from, so
   grouped cross-validation stays honest. Run
   `python tools/backfill_provenance.py` to see the inferred groups, then
   `--write` to save them (this rewrites `provenance.csv`, so re-apply any hand
   edits afterwards).
4. Re-run `main.py`. The embedding cache notices the change and rebuilds.
5. Measure before and after with `python tools/baseline_cv.py`.

Never take reference crops from `<name>_annotated.jpg`. Those crops contain the red
boxes and label text YOLO drew, and the knowledge base would learn to match on
them.

## Evaluating accuracy

### Grouped cross-validation (use this one)

```bash
python tools/baseline_cv.py                # all match modes
python tools/baseline_cv.py --modes lda
```

5-fold cross-validation over the knowledge base with **whole source photos held
out together**, using `provenance.csv` to know which photo each crop came from. It
needs no test set and is the honest generalisation estimate this project has.

### Test-set evaluation

```bash
python evaluate.py
python evaluate.py --match-mode knn
python evaluate.py --sim-threshold 0.55 --conf-threshold 0.40
python evaluate.py --no-sweep
```

Scores the classifier on the hand-labelled crops in `data/test_set/` (folder name =
ground-truth label) with the same matching code as production. It prints an
lda / knn / prototype comparison, a per-class precision/recall report, the top
misclassifications, a threshold sweep and the grouped-CV figure.

> **`evaluate.py` currently stops with a LEAKAGE error, and that is expected.**
> 116 of the 162 test crops are byte-identical to knowledge-base images, so they
> would retrieve themselves at similarity 1.0 and make every metric meaningless.
> The harness refuses to score that (`--allow-leaked` overrides it, for debugging
> only). Until the test set is rebuilt, use `tools/baseline_cv.py`.
>
> To rebuild it: `python tools/build_test_set.py --list` shows which shelf photos
> contributed nothing to the knowledge base, and `python tools/build_test_set.py`
> crops them into `data/test_set_staging/` for hand-labelling. Move the labelled
> crops into `data/test_set/<class>/` when done.

### Other evaluation tools

| Script | Purpose |
| --- | --- |
| `tools/baseline_cv.py` | Source-photo-grouped cross-validation on the knowledge base alone |
| `tools/gate_sweep.py` | Choose the score / margin thresholds from an out-of-fold precision-recall trade-off |
| `tools/negative_confusion.py` | Show where off-brand and non-beverage crops end up |
| `tools/build_test_set.py` | Cut crops from shelf photos that are not in the knowledge base, for a leak-free test set |
| `tools/backfill_provenance.py` | Rebuild `provenance.csv` for crops with no recorded source photo |
| `tools/cluster_diagnose.py` | Check whether DBSCAN can separate products before tuning it |

## Optional features

### OCR (`--ocr`)

```bash
pip install easyocr
python main.py --input data/sample/PXL_20260807_132315005.MP.jpg --ocr
```

`src/ocr.py` reads label text with EasyOCR (Persian + English) and turns it into
brand and flavour evidence that re-ranks the classifier's candidates. It is off by
default because it costs about 8 s per crop. EasyOCR downloads its models on first
use.

- By default OCR is consulted on crops where the top-2 gap is below `--ocr-margin`
  (0.35), **and** on every crop about to be named as a specific product
  (`--ocr-verify-brand`, on by default with `--ocr`). The second part catches a
  competitor pack with the same fruit picture, which the classifier can rate at 99%
  for a Sunich SKU. Use `--no-ocr-verify-brand` to only check close calls.
- A clear brand read acts as a **veto**: candidates of a different brand drop to the
  bottom, and if no knowledge-base class has that brand, the crop goes to
  `unknown_beverage`.
- **OCR needs resolution.** In measurements on knowledge-base crops, flavour text
  was read reliably only when the bottle was about **400 px wide or more**. Use
  original camera photos, not copies forwarded through a messaging app (which are
  heavily downscaled).
- On the 34-crop test set used at the time, OCR changed accuracy by +0.0% and never
  overturned a correct answer. So it is safe, and it fixes real errors on
  full-resolution photos. For example on `PXL_20260807_132315005.MP.jpg` it
  corrected a `sunich_1L_mix` to `sunich_1L_cherry` from the text `نکتا آلبالو`.

### OpenAI vision fallback (`--llm-fallback`)

```bash
pip install "openai>=1.0"
export OPENAI_API_KEY=sk-...            # Windows PowerShell: $env:OPENAI_API_KEY="sk-..."
python main.py --input data/sample/46.jpg --llm-fallback
```

The local matcher can only name products it has reference crops for. This fallback
gives crops it rejected (`low_confidence`) a second chance with an OpenAI vision
model. The model must pick from the same list of known products or answer
`unknown`, so it cannot invent a label.

- It is called **only** on `low_confidence` crops, so cost grows with the number of
  hard crops, not with shelf size.
- Rescued crops are marked `[llm]` in the console and `llm` in the `source` column of
  `predictions.csv`.
- Change the model with `--llm-model` or `$OPENAI_MODEL` (default `gpt-4.1`).
- Without the flag, or without a key, the pipeline behaves exactly as before.

### Unknown-beverage tools

Crops filed under `unknown_beverage` are drinks that were detected but not named.
Two tools help turn them into named classes. Neither writes to the knowledge base.
You review the suggestions and copy the crops into class folders yourself.

**Visual clustering (offline).** Groups similar unknown crops so you can label a
whole group at once. It copies images and never moves or deletes the originals.

```bash
python -m src.cluster                              # -> data/clustering/results/run_<timestamp>/
python tools/cluster_diagnose.py --emit-template   # writes data/clustering/ground_truth.csv
python tools/cluster_diagnose.py                   # scores DBSCAN vs. alternatives against it
```

**LLM identification (online, costs API calls).** A vision model reads each crop's
brand, flavour and size, re-checks each field separately, and verifies the brand
with a web search before it proposes a `brand_flavour_size` label.

```bash
pip install "openai>=1.0" ddgs
export GAPGPT_API_KEY=...
python -m src.unknown_beverage_pipeline --input data/knowledge_base/crops/object/unknown_beverage
```

Results go to `data/unknown_beverage_classification/run_<timestamp>/`
(`results.csv`, `results.json`, and copies sorted into `verified/`, `partial/` and
`unresolved_unknown/`). This folder is gitignored.

## Configuration (environment variables)

The core pipeline needs no configuration. Only the optional features do. Set the
values in your shell, or in a `.env` file that you load yourself (it is gitignored).
Never commit API keys.

| Variable | Used by | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | `main.py --llm-fallback` | OpenAI API key |
| `OPENAI_MODEL` | `main.py --llm-fallback` | Model override (default `gpt-4.1`) |
| `GAPGPT_API_KEY` | `src/unknown_beverage_pipeline.py` | Key for the OpenAI-compatible GapGPT endpoint |
| `GAPGPT_BASE_URL`, `GAPGPT_MODEL` | same | Endpoint and default model overrides |
| `GAPGPT_BRAND_MODEL`, `GAPGPT_FLAVOR_MODEL`, `GAPGPT_SIZE_MODEL`, `GAPGPT_VERIFY_MODEL` | same | Per-stage model overrides |
| `UB_SEARCH_BACKEND`, `UB_SEARCH_REGION` | same | Web-search backend and region for `ddgs` |
| `VITE_SHELF_API_URL` | `web-base44` | URL of `shelf_api.py` (default `http://127.0.0.1:8001`) |

## Project structure

```
ShareOfShelf/
├── main.py                  # CLI pipeline: photo -> predictions + share of shelf
├── shelf_api.py             # read-only HTTP detection API used by web-base44
├── evaluate.py              # accuracy harness (test set + grouped cross-validation)
├── report.py                # brand / product breakdown of a predictions.csv (+ optional HTML)
├── src/
│   ├── detect.py            # YOLO wrapper, box merging, crop saving, crop manifest
│   ├── img2vec_dino2.py     # DINOv2 embeddings (letterbox preprocessing, TTA)
│   ├── img2vec_resnet18.py  # ResNet18 embeddings (faster, less accurate)
│   ├── classifier.py        # KB loading + cache, LDA / kNN / prototype heads, gates
│   ├── provenance.py        # which shelf photo each KB crop came from
│   ├── ocr.py               # optional EasyOCR brand / flavour evidence
│   ├── llm_fallback.py      # optional OpenAI vision fallback
│   ├── cluster.py           # DBSCAN clustering of unknown_beverage crops
│   ├── unknown_beverage_classifier.py   # vision-LLM + web-search product naming
│   └── unknown_beverage_pipeline.py     # CLI for the above
├── tools/                   # evaluation and maintenance scripts (see "Other evaluation tools")
├── tests/test_regressions.py
├── models/best.pt           # trained YOLOv8m detector (~52 MB)
├── data/
│   ├── knowledge_base/      # labelled reference crops + provenance.csv
│   ├── test_set/            # labelled evaluation crops (folder = label)
│   ├── sample/              # raw shelf photos to try the pipeline on
│   └── clustering/ground_truth.csv   # hand labels for tools/cluster_diagnose.py
├── web-base44/              # React dashboard (Base44), see its READEME.md
├── requirements.txt         # pip dependencies
├── pyproject.toml           # same dependencies for uv
├── env.yaml                 # conda environment
└── LICENSE
```

Only the folders listed under `data/` above are committed. Everything else that
appears under `data/` (run outputs, API uploads and sessions, clustering results,
LLM runs, test-set staging) is generated and gitignored.

## Tests

```bash
python tests/test_regressions.py         # standalone, no pytest needed
python -m pytest tests/                  # if pytest is installed
```

Each test covers a bug that actually happened in this project. They use synthetic
embeddings, so they need no model download and no knowledge base, and finish in
seconds.

## Accuracy notes and known limitations

### Measured accuracy

Grouped cross-validation, measured on the 450-image knowledge base without TTA:

| Match mode | Grouped CV (whole source photos held out) |
| --- | --- |
| `lda` (default) | **72.4%** |
| `knn` | 54.4% |
| `prototype` | 53.1% |

An earlier 34-crop test set scored `lda` at 97.1%. That number is far too
optimistic: those test crops came from the same two shelf photos as many
knowledge-base crops (same shelf, same lighting, often the neighbouring facing of
the same product), so it measured memorisation rather than recognition. Only
trust the grouped-CV column.

### What improved accuracy

1. **Letterbox preprocessing.** The stock DINOv2 processor center-crops, which cut
   away about 70% of every bottle. Letterboxing was worth roughly +15 points.
2. **The LDA head.** Cosine matching weights all 768 dimensions equally, but most of
   them encode bottle shape and lighting, which are the same for every Sunich SKU.
   LDA learns the flavour-specific directions from the labels.
3. **Test-time augmentation.** +2.2 points when it was measured (6 crops fixed, 0
   broken). It costs about 3.5× runtime. This was measured on an older knowledge
   base and is worth re-checking on a rebuilt test set.
4. **Uniform LDA class priors.** Priors are not estimated from how many reference
   photos each class happens to have, which would tilt every prediction toward the
   most-photographed SKU.

### What did not help

- **Other classifier heads.** Logistic regression, linear SVM, nearest centroid,
  kNN and an LDA + kNN ensemble were all tried. None beat LDA.
- **Augmenting the reference crops.** +0.4 points, which is noise. Augmenting the
  query crop (TTA) is what helps.
- **Studio / e-commerce reference photos.** The knowledge base grew from 270 to 450
  images, mostly studio shots, and grouped CV stayed flat (70.4% → 72.4%). Studio
  shots are a different visual domain from shelf crops, and equalising their
  resolution did not close the gap. Crops from real shelf photos are what move the
  number.

### Known limitations

- **The shipped test set overlaps the knowledge base**, so `evaluate.py` stops with
  a leakage error. See [Evaluating accuracy](#evaluating-accuracy).
- **Off-brand drinks are the weakest point.** In the last measurement,
  `unknown_beverage` had about 25% recall and `non_beverage` about 62%, so many
  competitor products get a Sunich label. That makes Sunich's share of shelf look
  higher than it is. Naming competitors as their own classes is the most effective
  fix: in one test, two Sun Star packs labelled `sunich_1L_orange` (99%) and
  `sunich_1L_peach` were both identified correctly once `sunstar_240ml_*` classes
  existed.
- **Thin classes.** These have the fewest usable reference images and should get
  more crops from different real shelf photos first:
  `sunich_750ml_pineapple` (2), `sunich_750ml_pinacolada` (4),
  `sunich_750ml_pomegranate` (10), `sunich_750ml_apple` (12).
- **Confidence values are not calibrated probabilities.** In `lda` mode the reported
  confidence is a softmax over LDA scores at temperature 30 (`LDA_TEMPERATURE` in
  `src/classifier.py`), fitted by cross-validation. Without it, every crop would read
  100%. The temperature and the thresholds are tuned together: if you change one,
  re-run `tools/gate_sweep.py`.
- **Detection runs at confidence 0.5**, so very low-resolution or non-shelf images
  may produce no crops.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `ModuleNotFoundError: transformers` (or `torch`) | Dependencies are not installed in the active environment. Activate it and run `pip install -r requirements.txt`. |
| First run seems to hang | It is downloading `facebook/dinov2-base` (~330 MB) and embedding the knowledge base. This happens once. |
| `Knowledge base is empty` | You are running from the wrong directory. Run everything from the repository root. |
| `No crops found — check YOLO detection output` | YOLO found nothing above confidence 0.5. Usually a non-shelf image or a very low-resolution photo. |
| Everything lands in `low_confidence` | The products are not in the knowledge base. Add reference crops, or lower `--sim-threshold`. |
| A new class is never predicted | It has fewer than 2 `.jpg` images, or its images are not `.jpg`. |
| `UnicodeEncodeError` on Windows | The console is not UTF-8. Run `chcp 65001` first. |
| `LEAKAGE: ... test crops are byte-identical` from `evaluate.py` | Expected with the current test set. Use `tools/baseline_cv.py`. |
| Web app's Shelf Analysis page shows an error | `shelf_api.py` is not running, or is still loading. Check `http://127.0.0.1:8001/api/state`. |

## Acknowledgements

This project started as a fork of Albert Ferré's
[facings identifier](https://www.kaggle.com/code/albertferre/sku-facings-detector),
which combined YOLOv8 with ResNet18 image embeddings. The detector weights
(`models/best.pt`) come from that work: YOLOv8m trained on the
[SKU-110K](https://www.kaggle.com/datasets/thedatasith/sku110k-annotations) dataset.

- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics)
- [DINOv2](https://github.com/facebookresearch/dinov2) (`facebook/dinov2-base` via
  Hugging Face Transformers)
- [EasyOCR](https://github.com/JaidedAI/EasyOCR)

## License

Released under the [MIT License](LICENSE). The license file keeps the original
copyright notice of the upstream project, as the MIT License requires.
