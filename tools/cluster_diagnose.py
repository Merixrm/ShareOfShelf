"""Can DBSCAN actually separate these products? Measure before changing the algorithm.

`src/cluster.py` groups unknown-beverage crops with DBSCAN at eps=0.20 in cosine
distance, chosen by hand and never scored. There are three specific reasons to doubt
it, and this tool tests all three rather than arguing about them:

  1. eps may be larger than the gap between DIFFERENT products. `src/classifier.py`
     measured the 750ml prototypes sitting at mean cosine 0.909 from each other —
     a cosine DISTANCE of 0.091, less than half the configured eps. If distinct SKUs
     are closer together than eps, no setting of min_samples can keep them apart.

  2. DBSCAN assumes ONE global density. These crops do not have one: a common SKU
     may appear 30 times and a rare one 3 times. A single (eps, min_samples) either
     loses the rare products to noise or merges the common ones. The last run put
     100 of 255 crops in `noise`, which is the algorithm saying exactly this.

  3. Density chaining. Density-reachability is transitive, so a single visually
     intermediate crop welds two products into one cluster. This is the failure mode
     DBSCAN is worst at and product embeddings are the worst input for.

What it reports
---------------
  * k-distance curve — the standard, principled way to choose eps: sort every point's
    distance to its min_samples-th nearest neighbour and look for a knee. NO CLEAN
    KNEE IS ITSELF THE RESULT. It means there is no density level that separates
    these clusters, and eps tuning cannot fix that.
  * ARI and purity against a hand-labelled ground truth, if one exists, for DBSCAN
    across a range of eps and for two alternatives — HDBSCAN (variable density, no
    eps) and average-linkage agglomerative (resists the chaining in 3).

Ground truth
------------
Without it none of the quality numbers can be computed, and eps tuning is guessing.
Generating the template takes seconds and filling it in takes about twenty minutes:

    python tools/cluster_diagnose.py --emit-template
    # edit data/clustering/ground_truth.csv, putting crops of the same product
    # under the same group name (any name; only the partition matters)
    python tools/cluster_diagnose.py

Usage:
    python tools/cluster_diagnose.py --emit-template
    python tools/cluster_diagnose.py
"""

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import cluster as C                                   # noqa: E402

GROUND_TRUTH = Path("data/clustering/ground_truth.csv")


def load_ground_truth(path=GROUND_TRUTH):
    """Return {crop filename: group label}, ignoring rows left blank."""
    if not Path(path).is_file():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["crop"]: r["group"].strip() for r in csv.DictReader(f)
                if r.get("crop") and r.get("group", "").strip()}


def emit_template(images, path=GROUND_TRUTH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    existing = load_ground_truth(path)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["crop", "group"])
        for p in images:
            w.writerow([p.name, existing.get(p.name, "")])
    return path


def k_distance(X, min_samples):
    """Sorted distance to the min_samples-th nearest neighbour, cosine metric."""
    from sklearn.neighbors import NearestNeighbors
    nn = NearestNeighbors(n_neighbors=min_samples, metric="cosine",
                          algorithm="brute").fit(X)
    d, _ = nn.kneighbors(X)
    return np.sort(d[:, -1])


def purity(labels_true, labels_pred):
    """Fraction of clustered points whose cluster's majority label is their own.

    Noise (-1) is excluded — a point DBSCAN declined to cluster is not a wrong
    assignment, it is an abstention, and scoring it as an error would flatter any
    setting that clusters aggressively.
    """
    mask = labels_pred != -1
    if not mask.any():
        return float("nan")
    total = 0
    for c in set(labels_pred[mask]):
        members = labels_true[(labels_pred == c)]
        vals, counts = np.unique(members, return_counts=True)
        total += counts.max()
    return total / mask.sum()


def score_run(name, labels, y_true):
    from sklearn.metrics import adjusted_rand_score
    n_clusters = len(set(labels) - {-1})
    n_noise    = int((labels == -1).sum())
    if y_true is None:
        print(f"  {name:<34} clusters={n_clusters:<3} noise={n_noise:<4}")
        return
    ari = adjusted_rand_score(y_true, labels)
    pur = purity(y_true, labels)
    print(f"  {name:<34} clusters={n_clusters:<3} noise={n_noise:<4} "
          f"ARI={ari:>6.3f}  purity={pur:>6.1%}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--emit-template", action="store_true")
    ap.add_argument("--min-samples", type=int, default=C.DBSCAN_MIN_SAMPLES)
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    images = C._load_images()
    if not images:
        raise SystemExit(f"No images under {C.UNKNOWN_BEVERAGE_DIR}")

    if args.emit_template:
        path = emit_template(images)
        print(f"Wrote {len(images)} rows to {path}")
        print("Fill the 'group' column: same product -> same group name.")
        print("Leave a row blank to exclude it. Then re-run without --emit-template.")
        return

    pool = C._load_pool()
    pool = C._extract_new_embeddings(images, pool)
    X, valid = C._build_embedding_matrix(images, pool)
    X = C._normalize_embeddings(X)
    print(f"\n── Clustering diagnosis: {len(valid)} crops ──")

    truth = load_ground_truth()
    y_true = None
    if truth:
        keep = [i for i, p in enumerate(valid) if p.name in truth]
        if len(keep) < len(valid):
            print(f"  ground truth covers {len(keep)}/{len(valid)} crops; "
                  f"scoring on those")
        X      = X[keep]
        valid  = [valid[i] for i in keep]
        y_true = np.array([truth[p.name] for p in valid])
        print(f"  ground truth: {len(set(y_true))} true product groups")
    else:
        print(f"  !! No ground truth at {GROUND_TRUTH} — ARI/purity cannot be")
        print("     computed, so eps cannot be validated. Run --emit-template.")

    # ── k-distance curve ────────────────────────────────────────────────────
    kd = k_distance(X, args.min_samples)
    print(f"\n  k-distance curve (k={args.min_samples}), cosine distance:")
    for q in (10, 25, 50, 75, 90, 95, 99):
        print(f"    p{q:<3} {np.percentile(kd, q):.3f}")
    # A knee shows up as a jump between consecutive sorted values.
    jumps = np.diff(kd)
    if len(jumps):
        i = int(np.argmax(jumps))
        print(f"    largest single jump: {kd[i]:.3f} -> {kd[i+1]:.3f} "
              f"(+{jumps[i]:.3f}) at point {i+1}/{len(kd)}")
        print("    A knee worth trusting is a jump that stands out from its "
              "neighbours;")
        print("    a curve that rises smoothly means no density level separates "
              "these clusters.")
    print("\n  For reference: DIFFERENT 750ml SKUs sit ~0.091 apart in this metric.")
    print(f"  Any eps above that cannot separate them. Current eps = {C.DBSCAN_EPS}.")

    # ── DBSCAN across eps, plus alternatives ────────────────────────────────
    print(f"\n  DBSCAN (min_samples={args.min_samples}):")
    for eps in (0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30):
        labels = C._run_dbscan(X, eps=eps, min_samples=args.min_samples)
        marker = "  <- current" if abs(eps - C.DBSCAN_EPS) < 1e-9 else ""
        score_run(f"eps={eps:.2f}{marker}", labels, y_true)

    print("\n  Alternatives:")
    try:
        from sklearn.cluster import HDBSCAN
        for mcs in (2, 3, 5):
            labels = HDBSCAN(min_cluster_size=mcs, metric="cosine").fit_predict(X)
            score_run(f"HDBSCAN min_cluster_size={mcs}", labels, y_true)
    except ImportError:
        print("    HDBSCAN unavailable (needs scikit-learn >= 1.3)")

    from sklearn.cluster import AgglomerativeClustering
    for thr in (0.05, 0.10, 0.15, 0.20):
        labels = AgglomerativeClustering(
            n_clusters=None, distance_threshold=thr,
            metric="cosine", linkage="average").fit_predict(X)
        score_run(f"agglomerative avg thr={thr:.2f}", labels, y_true)

    if y_true is None:
        print("\n  Without ground truth these rows show only SHAPE, not quality.")
        print("  A setting that produces a tidy number of clusters can still be")
        print("  splitting one product in two and merging two others.")


if __name__ == "__main__":
    main()
