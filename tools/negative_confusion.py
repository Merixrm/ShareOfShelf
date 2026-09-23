"""Where do the negatives actually go?

`src/classifier.py` has long claimed that "three quarters of off-brand drinks are
still handed a specific Sunich SKU instead of landing in `unknown_beverage`, which
inflates Sunich share-of-shelf". That conclusion was drawn from a per-bucket recall
figure (unknown_beverage recall 25%), and per-bucket recall does not support it: a
crop that misses `unknown_beverage` may well have landed in `non_beverage`, which is
the OTHER not-a-product bucket and is equally harmless for share of shelf.

The distinction decides where effort should go. If off-brand crops really are being
named as Sunich SKUs, an out-of-distribution detector is urgent. If they are merely
being shuffled between the two buckets, the buckets are working and the confusion is
cosmetic.

This prints the out-of-fold destination of every crop whose true label is a negative,
split into the categories that actually differ in cost.

Usage:
    python tools/negative_confusion.py [--mode lda]
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate import is_unknown_label                          # noqa: E402
from src.classifier import (                                   # noqa: E402
    apply_gates, load_kb_embeddings, CONF_THRESH, DEFAULT_MODE, MATCH_MODES,
    default_threshold,
)
from src.img2vec_dino2 import Img2VecDino2                     # noqa: E402
from tools.gate_sweep import out_of_fold                       # noqa: E402

KB_PATH = "data/knowledge_base/crops/object"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb", default=KB_PATH)
    ap.add_argument("--mode", default=DEFAULT_MODE, choices=list(MATCH_MODES))
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    img2vec = Img2VecDino2()
    classes, embeddings = load_kb_embeddings(args.kb, img2vec)
    raw, y, _ = out_of_fold(args.kb, classes, embeddings, args.mode)

    thr   = default_threshold(args.mode)
    preds = [apply_gates(p, vc, s, CONF_THRESH, thr) for (p, vc, s, _m) in raw]

    print(f"\n── Negative destinations (mode={args.mode}, out-of-fold) ──")
    for bucket in sorted({t for t in y if is_unknown_label(t)}):
        idx  = [i for i, t in enumerate(y) if t == bucket]
        dest = Counter(preds[i] for i in idx)

        exact    = dest[bucket]
        other_b  = sum(n for lab, n in dest.items()
                       if is_unknown_label(lab) and lab != bucket)
        rejected = dest["low_confidence"]
        named    = len(idx) - exact - other_b - rejected

        print(f"\n  {bucket}  (n={len(idx)})")
        print(f"    -> same bucket        {exact:>4}  {exact/len(idx):>6.1%}")
        print(f"    -> the OTHER bucket   {other_b:>4}  {other_b/len(idx):>6.1%}"
              f"   (harmless for share of shelf)")
        print(f"    -> low_confidence     {rejected:>4}  {rejected/len(idx):>6.1%}"
              f"   (harmless)")
        print(f"    -> a specific SKU     {named:>4}  {named/len(idx):>6.1%}"
              f"   <<< the damaging error")
        if named:
            got = Counter(preds[i] for i in idx
                          if not is_unknown_label(preds[i])
                          and preds[i] != "low_confidence")
            for lab, n in got.most_common():
                print(f"         {n:>3}x  {lab}")

    neg = [i for i, t in enumerate(y) if is_unknown_label(t)]
    bad = sum(1 for i in neg
              if not is_unknown_label(preds[i]) and preds[i] != "low_confidence")
    print(f"\n  Overall: {bad}/{len(neg)} negatives ({bad/len(neg):.1%}) were given a "
          f"specific product name.")
    print("  Per-bucket recall counts a bucket-to-bucket swap as a miss; share of "
          "shelf does not.")


if __name__ == "__main__":
    main()
