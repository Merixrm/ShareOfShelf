"""Pick the rejection gates from an out-of-fold precision/recall trade-off.

Runs source-photo-grouped CV once, keeping the full (label, vote, score, margin) for
every crop, then sweeps the score and margin thresholds over those cached results.
Nothing is re-embedded per threshold, so the whole sweep costs one CV pass.

Why here and not in evaluate.py: the shipped test set is still leaky and has no
negatives left, so it cannot be used to choose a rejection threshold at all. The KB
does have negatives — 51 `unknown_beverage` and 58 `non_beverage` crops — and grouped
CV holds out whole source photos, so out-of-fold predictions on them are honest.

The two errors being traded:

    false accept — a crop that is NOT a known product gets a specific SKU name.
                   This inflates that brand's share of shelf. The expensive one.
    false reject — a crop that IS a known product gets rejected to low_confidence.
                   A lost facing: it drops out of the share denominator entirely.

Usage:
    python tools/gate_sweep.py                     # lda, sweep both gates
    python tools/gate_sweep.py --mode knn
"""

import argparse
import glob
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate import open_set_metrics                          # noqa: E402
from src.classifier import (                                   # noqa: E402
    KBIndex, classify_full, apply_gates, load_kb_embeddings,
    CONF_THRESH, DEFAULT_MODE, MATCH_MODES, default_threshold,
)
from src.img2vec_dino2 import Img2VecDino2                     # noqa: E402
from src.provenance import resolve_all                         # noqa: E402

KB_PATH = "data/knowledge_base/crops/object"


def out_of_fold(kb_path, classes, embeddings, mode, n_splits=5):
    """Full classify_full() output for every KB crop, from a model that never saw it."""
    from sklearn.model_selection import StratifiedGroupKFold

    files = sorted(glob.glob(f"{kb_path}/**/*.jpg", recursive=True))
    X = np.asarray(embeddings, dtype=np.float32)
    y = np.asarray(classes)
    groups, n_inferred = resolve_all(kb_path, files)

    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=0)
    raw = np.empty(len(X), dtype=object)
    for tr, te in splitter.split(X, y, np.asarray(groups)):
        idx = KBIndex(list(y[tr]), X[tr])
        raw[te] = [classify_full(v, idx, mode=mode) for v in X[te]]
    return list(raw), y, n_inferred


def sweep(raw, y, mode, score_thrs, margin_thrs):
    """Print SKU accuracy / false accepts for each (score, margin) pair."""
    print(f"  {'score':>6} {'margin':>7}   {'SKU acc':>8} {'f.rej':>6}   "
          f"{'neg ok':>7} {'f.acc':>6}   {'balanced':>8}")
    rows = []
    for s_thr in score_thrs:
        for m_thr in margin_thrs:
            preds = [
                apply_gates(p, vc, s, CONF_THRESH, s_thr,
                            margin=mg, margin_threshold=m_thr)
                for (p, vc, s, mg) in raw
            ]
            m = open_set_metrics(preds, y)
            rows.append((s_thr, m_thr, m))
            print(f"  {s_thr:>6.2f} {m_thr:>7.2f}   "
                  f"{m['sku_accuracy']:>8.1%} {m['false_rejects']:>6}   "
                  f"{m['neg_handled']:>7.1%} {m['false_accepts']:>6}   "
                  f"{m['balanced']:>8.1%}")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kb", default=KB_PATH)
    ap.add_argument("--mode", default=DEFAULT_MODE, choices=list(MATCH_MODES))
    ap.add_argument("--n-splits", type=int, default=5)
    ap.add_argument("--tta", action="store_true",
                    help="Sweep against TTA-embedded references. REQUIRED whenever "
                         "the embedding changes: TTA smooths every vector toward its "
                         "class mean, which shifts the whole margin distribution, so "
                         "a threshold swept on single-view vectors is no longer the "
                         "same operating point. Measured: at margin 0.05 the same "
                         "gate gave 1 false accept single-view and 4 under TTA.")
    ap.add_argument("--no-flip", action="store_true",
                    help="With --tta, drop the horizontal flip from the view set.")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    tta_flip = not args.no_flip
    img2vec = Img2VecDino2()
    classes, embeddings = load_kb_embeddings(args.kb, img2vec,
                                             tta=args.tta, tta_flip=tta_flip)
    raw, y, n_inferred = out_of_fold(args.kb, classes, embeddings,
                                     args.mode, args.n_splits)
    variant = ("single-view" if not args.tta
               else f"TTA {'5 views' if tta_flip else '4 views, no flip'}")
    print(f"\n── Gate sweep (mode={args.mode}, {variant}, {len(y)} crops, "
          f"{n_inferred} inferred groups) ──")

    margins = np.array([m for (_p, _v, _s, m) in raw])
    print(f"  margin distribution: min {margins.min():.3f}  "
          f"p25 {np.percentile(margins, 25):.3f}  median {np.median(margins):.3f}  "
          f"p75 {np.percentile(margins, 75):.3f}  max {margins.max():.3f}")

    cur = default_threshold(args.mode)
    print(f"\n  Current shipped gate: score>={cur:.2f}, margin off\n")

    score_thrs  = [0.0, cur, 0.50]
    margin_thrs = [0.0, 0.05, 0.10, 0.20, 0.30, 0.50]
    sweep(raw, y, args.mode, sorted(set(score_thrs)), margin_thrs)

    print("\n  margin 0.00 = gate disabled (current behaviour).")
    print("  Pick the row whose false-accept count you can live with. A false accept")
    print("  puts a competitor's bottle into YOUR share of shelf; a false reject only")
    print("  removes a facing from the denominator. They are not equally expensive,")
    print("  so do not just take the best 'balanced' number.")


if __name__ == "__main__":
    main()
