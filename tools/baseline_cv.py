"""Source-photo-grouped cross-validation on the knowledge base alone.

Runs the same `grouped_cv` the evaluation harness runs, but without needing a test
set. That matters right now for two reasons:

  * The shipped test set is still 116/162 byte-identical to KB crops, so
    `evaluate.py` correctly refuses to run until it is rebuilt.
  * Grouped CV never touched the test set anyway — it holds out whole source photos
    from the KB — so it is available immediately and is the honest generalisation
    estimate to measure every later change against.

Usage:
    python tools/baseline_cv.py
    python tools/baseline_cv.py --modes lda           # single mode, faster
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate import grouped_cv                       # noqa: E402
from src.classifier import load_kb_embeddings, MATCH_MODES   # noqa: E402
from src.img2vec_dino2 import Img2VecDino2            # noqa: E402

KB_PATH = "data/knowledge_base/crops/object"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb", default=KB_PATH)
    ap.add_argument("--modes", nargs="+", default=list(MATCH_MODES),
                    choices=list(MATCH_MODES))
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--tta", action="store_true",
                    help="Embed KB references with test-time augmentation too, so "
                         "references and queries live in the same distribution and "
                         "the LDA head is fitted on the vectors it will actually see. "
                         "5x slower on the first run; cached separately afterwards.")
    ap.add_argument("--no-flip", action="store_true",
                    help="With --tta, drop the horizontal flip from the view set. "
                         "The flip is the one view that suppresses chiral features — "
                         "i.e. brand text — so it is worth ablating on its own.")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    tta_flip = not args.no_flip
    label = ("single-view (no TTA)" if not args.tta
             else f"TTA {'5 views' if tta_flip else '4 views, no flip'}")
    print(f"Knowledge base: {args.kb}")
    print(f"  reference embeddings: {label}")
    img2vec = Img2VecDino2()
    classes, embeddings = load_kb_embeddings(args.kb, img2vec,
                                             tta=args.tta, tta_flip=tta_flip)
    print(f"  {len(embeddings)} crops across {len(set(classes))} classes")

    grouped_cv(args.kb, classes, embeddings,
               modes=tuple(args.modes), n_splits=args.n_splits)


if __name__ == "__main__":
    main()
