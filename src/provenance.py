"""Which shelf photo did each knowledge-base crop come from?

Why this exists
---------------

Source-photo-grouped cross-validation is the only honest generalisation estimate
this project has. Two crops cut from the same photograph are the same bottle under
the same lighting at the same instant — often literally adjacent facings of one
product. Holding out one while its twin stays in the training half measures
memorisation, not recognition, which is why the shipped test set read 97.1% while
grouped CV read ~72%.

That grouping is only as good as the crop -> photo mapping behind it. Until now the
mapping was *recovered* from the filename by regex (`evaluate.py:source_photo`), and
on real data it failed in both directions:

  Too coarse — e-commerce filenames `0x.jpg` and `0x244.jpg` both reduce to the group
  `'0x'`, which spanned SIX different SKUs; stripping the `_front`/`_back` view suffix
  merged `sunich_1L_orange` with `sunich_750ml_orange`. 21 inferred groups spanned more
  than one class label.

  Too fine — `data/sample/t3.jpg` reduces to `t3`, but the crop cut from it,
  `t3 (Edited).jpg`, reduces to `t3 (Edited)`. A photo that DID feed the knowledge base
  therefore looked held-out, and would have been used to build a "clean" test set.

The fix is to stop inferring. `src/detect.py:save_crops` knows the source photo at the
moment it cuts a crop, and `write_crop_manifest` writes it down (`crops.csv` next to
every run's output). The knowledge base keeps that record in `provenance.csv`, so
`evaluate.py` can look provenance up instead of guessing it.

The regex remains as a fallback for crops with no recorded provenance; see
`tools/backfill_provenance.py` for seeding those.

Format (`data/knowledge_base/provenance.csv`):

    kb_file,source_photo,recorded_at
    sunich_1L_apple/2025-12.jpg,2025,2026-08-16T11:04:07

`kb_file` is relative to the KB root so the file survives the tree being moved or
checked out elsewhere.
"""

import csv
import glob
import re
from datetime import datetime
from pathlib import Path

PROVENANCE_NAME = "provenance.csv"

# Where the original shelf photographs live. Used only to confirm an inferred photo
# id really is a photo, never to enumerate crops.
SHELF_PHOTO_DIR = "data/sample"
_PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png"}


# ── Fallback inference (for crops that predate the manifest) ────────────────

# Photo editors append " (Edited)" / " (Edited 3)", sometimes more than once. These
# are the SAME photograph and must land in the same group. The old rule kept them,
# so `data/sample/t3.jpg` grouped as `t3` while its own crop `t3 (Edited).jpg`
# grouped as `t3 (Edited)` — a photo that fed the KB looked held-out.
_EDITED_SUFFIX = re.compile(r"\s*\(Edited(?:\s+\d+)?\)", re.IGNORECASE)

# Our own crop naming from `save_crops`: "<photo>-<idx>".
_CROP_INDEX = re.compile(r"^(.*?)-(\d+)$")

# Studio multi-angle shots: `apple_front`, `apple_frontleft`, `pomegranate_backup`.
# One physical carton photographed repeatedly in a single session.
_VIEW_SUFFIX = re.compile(r"^(.*)_(?:front|back)[a-z0-9]*$", re.IGNORECASE)


def known_shelf_photos(photo_dir=SHELF_PHOTO_DIR):
    """Stems of the original shelf photographs, used to confirm an inferred id."""
    return {Path(p).stem for p in glob.glob(f"{photo_dir}/*")
            if Path(p).suffix.lower() in _PHOTO_SUFFIXES}


def infer_source_photo(path, class_label=None, known_photos=None):
    """Best-effort group id for a crop with no recorded provenance.

    A deliberate replacement for the old `evaluate.py:source_photo`, which stripped
    any trailing digits and so collapsed the e-commerce filenames `0x.jpg` and
    `0x244.jpg` into one group `'0x'` spanning six different SKUs, while its
    view-suffix rule merged `sunich_1L_orange` with `sunich_750ml_orange`. Both
    errors under-report accuracy's optimism by hiding real leakage inside groups
    that look independent.

    The rule here, in order:

      1. Strip "(Edited N)" — same photograph, different export.
      2. If the result is a known shelf photo, that is the group.
      3. If it looks like `<photo>-<idx>` (our own crop naming), group by `<photo>`.
      4. If it looks like `<product>_<view>` (studio multi-angle), group by product
         AND class — one carton photographed from many angles, but never merging two
         different SKUs that happen to share a flavour word.
      5. Otherwise treat the file as its own independent source, qualified by class.

    Rule 5 is the important conservative default: a lone e-commerce download really
    is an independent sample, and guessing otherwise silently discards data. Groups
    that span several classes are EXPECTED under rules 2-3 — a shelf photo contains
    many products, and holding all of them out together is exactly the point.
    """
    if known_photos is None:
        known_photos = known_shelf_photos()
    cls  = class_label if class_label is not None else Path(path).parent.name
    stem = _EDITED_SUFFIX.sub("", Path(path).stem).strip()

    if stem in known_photos:
        return stem

    m = _CROP_INDEX.match(stem)
    if m:
        return m.group(1)

    m = _VIEW_SUFFIX.match(stem)
    if m:
        return f"{cls}::{m.group(1)}"

    return f"{cls}::{stem}"


def resolve_all(kb_path, files, recorded=None, known_photos=None):
    """Group id for every file in `files`, preferring the manifest over inference.

    Returns (groups, n_inferred) where `groups` is a list aligned with `files`.
    `n_inferred` is how many had to be guessed — report it, because a run with many
    guesses has a correspondingly less trustworthy generalisation estimate.
    """
    recorded = load_provenance(kb_path) if recorded is None else recorded
    if known_photos is None:
        known_photos = known_shelf_photos()
    root = Path(kb_path).resolve()

    groups, n_inferred = [], 0
    for f in files:
        rel = Path(f).resolve().relative_to(root).as_posix()
        if rel in recorded:
            groups.append(recorded[rel])
        else:
            n_inferred += 1
            groups.append(infer_source_photo(f, known_photos=known_photos))
    return groups, n_inferred


# ── Recorded provenance ─────────────────────────────────────────────────────

def provenance_path(kb_path):
    """Location of the provenance file for a KB rooted at `kb_path`.

    Sits at the knowledge-base root (`data/knowledge_base/`) rather than inside the
    crop tree, where a stray .csv would be a class folder's neighbour.
    """
    return Path(kb_path).parent.parent / PROVENANCE_NAME



def load_provenance(kb_path):
    """Return {kb_relative_path: source_photo}. Empty dict when no file exists."""
    path = provenance_path(kb_path)
    if not path.is_file():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["kb_file"]: row["source_photo"] for row in csv.DictReader(f)
                if row.get("kb_file") and row.get("source_photo")}



def write_all(kb_path, mapping):
    """Rewrite the provenance file from `{kb_relative_path: source_photo}`.

    Used by the backfill tool. Overwrites rather than appends, so re-running the
    backfill after correcting a group does not leave the superseded row behind for
    `load_provenance` to pick at random.
    """
    path = provenance_path(kb_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kb_file", "source_photo", "recorded_at"])
        for rel in sorted(mapping):
            w.writerow([rel, mapping[rel], stamp])
    return path
