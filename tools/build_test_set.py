"""Cut crops from KB-free shelf photos, ready to be hand-labelled into a test set.

Why the test set has to be rebuilt
----------------------------------
The shipped one cannot measure generalisation:

  * 116 of its 162 crops are byte-identical to knowledge-base images, so
    `assert_no_leakage` aborts. A leaked crop retrieves itself at cosine similarity
    1.0 and is scored correct by construction.
  * Of the 46 that are clean, every one is a Sunich SKU. There is not a single
    negative left, and a test set with no negatives cannot be used to choose a
    rejection threshold at all — every rejection scores as an error, so the sweep is
    maximised at a threshold of zero no matter what the model does.
  * 310 of the original 315 came from shelf photos that also fed the KB. Those are
    the same bottles under the same lighting at the same instant, which measures
    memorisation rather than recognition.

This tool detects and crops the shelf photos that contributed NOTHING to the KB —
determined from `data/knowledge_base/provenance.csv`, not from filename guessing —
and stages the crops for labelling. It uses the same `detect_products` / `save_crops`
path as the pipeline, so a crop labelled here is the exact pixels production
classifies, and it writes a provenance manifest alongside.

It deliberately does NOT write into `data/test_set/` or touch the existing one:
staging first means you never have a half-labelled test set that `evaluate.py`
would happily score.

Usage:
    python tools/build_test_set.py --list              # which photos are KB-free
    python tools/build_test_set.py                     # crop them all to staging
    python tools/build_test_set.py --photos t2 803     # just these
"""

import argparse
import glob
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detect import (                                        # noqa: E402
    detect_products, save_crops, write_crop_manifest, MANIFEST_NAME,
)
from src.provenance import (                                    # noqa: E402
    resolve_all,
)

KB_PATH     = "data/knowledge_base/crops/object"
PHOTO_DIR   = "data/sample"
STAGING_DIR = "data/test_set_staging"
MODEL_PATH  = "models/best.pt"
_SUFFIXES   = {".jpg", ".jpeg", ".png"}


def kb_free_photos(kb_path=KB_PATH, photo_dir=PHOTO_DIR):
    """Shelf photos on disk that contributed no crop to the knowledge base.

    Uses recorded provenance, so this is a fact rather than an inference. Under the
    old filename rule `t3.jpg` looked KB-free while its crop `t3 (Edited).jpg` was
    sitting in `unknown_beverage/` — building a "held-out" test set from that photo
    would have re-created the leakage this rebuild exists to remove.
    """
    kb_files = sorted(glob.glob(f"{kb_path}/**/*.jpg", recursive=True))
    kb_groups, _ = resolve_all(kb_path, kb_files)
    used = set(kb_groups)

    photos = sorted(p for p in glob.glob(f"{photo_dir}/*")
                    if Path(p).suffix.lower() in _SUFFIXES)
    free = [p for p in photos if Path(p).stem not in used]
    return free, [p for p in photos if Path(p).stem in used]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb", default=KB_PATH)
    ap.add_argument("--photo-dir", default=PHOTO_DIR)
    ap.add_argument("--staging", default=STAGING_DIR)
    ap.add_argument("--model", default=MODEL_PATH)
    ap.add_argument("--photos", nargs="+", default=None,
                    help="Only these photo stems (default: every KB-free photo)")
    ap.add_argument("--list", action="store_true",
                    help="Report which photos are KB-free and exit")
    ap.add_argument("--clean", action="store_true",
                    help="Empty the staging directory first")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    free, used = kb_free_photos(args.kb, args.photo_dir)
    print(f"{len(free) + len(used)} shelf photos in {args.photo_dir}")
    print(f"  {len(used)} already fed the knowledge base — NOT usable for testing")
    print(f"  {len(free)} KB-free:")
    for p in free:
        print(f"      {Path(p).stem}")
    if args.list:
        return
    if not free:
        raise SystemExit("\nNo KB-free photos — cannot build an independent test set.")

    if args.photos:
        wanted = set(args.photos)
        chosen = [p for p in free if Path(p).stem in wanted]
        missing = wanted - {Path(p).stem for p in chosen}
        if missing:
            raise SystemExit(f"Not KB-free (or not found): {', '.join(sorted(missing))}")
    else:
        chosen = free

    staging = Path(args.staging)
    if args.clean and staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    from ultralytics import YOLO
    yolo = YOLO(args.model)

    total = 0
    for photo in chosen:
        stem = Path(photo).stem
        out  = staging / stem
        boxes, _confs = detect_products(yolo, photo)
        crops = save_crops(photo, boxes, out / "crops", stem)
        write_crop_manifest(out / MANIFEST_NAME, crops)
        total += len(crops)
        print(f"  {stem:<40} {len(crops):>3} crops -> {out}/crops")

    print(f"\nStaged {total} crops from {len(chosen)} photos in {staging}/")
    print("\nNext, by hand:")
    print("  1. Sort each crop into data/test_set/<true_label>/ .")
    print("     Use the SAME label names as the KB class folders, and file off-brand")
    print("     drinks under unknown_beverage and snacks/boxes under non_beverage —")
    print("     without those negatives the rejection threshold cannot be chosen.")
    print("  2. Delete the old leaked folders once you have replacements:")
    print("       data/test_set/unknown_beverage/   (51 crops, copies of the KB)")
    print("       data/test_set/non_beverage/       (58 crops, copies of the KB)")
    print("  3. Re-run:  python evaluate.py")
    print("     It must print 'Leakage check: OK' and 'Source-photo check: OK'.")


if __name__ == "__main__":
    main()
