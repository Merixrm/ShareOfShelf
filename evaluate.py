"""Scored evaluation harness for the shelf-product classifier.

Measures accuracy against a hand-labelled test set so improvements are provable
instead of eyeballed. Uses the SAME matching code as production (`src/classifier.py`).

Test set layout (folder name = ground-truth label, disjoint from the KB images):
    data/test_set/<true_label>/*.jpg

The disjointness above is ENFORCED, not assumed — see `assert_no_leakage`. A test
crop that is byte-identical to a KB crop is its own nearest neighbour at cosine
similarity 1.0, so every metric derived from it is meaningless. This harness once
reported 100% kNN accuracy on a test set that was 34/34 copies of KB images; the
guard exists so that can never pass silently again.

Usage:
    python evaluate.py                          # prototype mode, default thresholds + sweep
    python evaluate.py --match-mode knn
    python evaluate.py --sim-threshold 0.55 --conf-threshold 0.40
    python evaluate.py --model resnet18
    python evaluate.py --allow-leaked           # report leakage but run anyway (debugging only)
"""

import glob
import sys
import hashlib
import argparse
from collections import Counter
from pathlib import Path

from PIL import Image
from sklearn.metrics import classification_report, accuracy_score

from src.classifier import (
    load_kb_embeddings, KBIndex, classify_full, apply_gates, top_matches,
    assert_flat_class_tree, is_non_beverage,
    CONF_THRESH, MATCH_MODES, DEFAULT_MODE, default_threshold, default_margin,
    UNKNOWN_LABELS,
)
from src.img2vec_dino2 import Img2VecDino2
from src.img2vec_resnet18 import Img2VecResnet18
from src.provenance import infer_source_photo, known_shelf_photos, resolve_all

KB_PATH       = 'data/knowledge_base/crops/object'
TEST_SET_PATH = 'data/test_set'


def load_test_crops(test_path):
    """Return list of (image_path, true_label) from data/test_set/<label>/*.jpg.

    Guarded by the same depth check as the KB loader, and for the same reason: the
    ground-truth label is the parent folder name, so a nested directory becomes a
    fake test class. `src/cluster.py` once wrote three runs into
    `data/test_set/unknown_beverage/clustering_results/`, which handed this harness
    `noise` (62 crops), `cluster_0` (34) and `cluster_1..4` as ground truth.
    """
    imgs = sorted(glob.glob(f"{test_path}/**/*.jpg", recursive=True))
    if imgs:
        assert_flat_class_tree(test_path, imgs, what="test set")
    return [(p, Path(p).parent.name) for p in imgs]


def _md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def source_photo(path):
    """Source-photo id for a crop — RECORDED where possible, inferred otherwise.

    Provenance now comes from `data/knowledge_base/provenance.csv`, written at crop
    time by `src/detect.py:write_crop_manifest` (or seeded by
    `tools/backfill_provenance.py`). `src/provenance.py:infer_source_photo` is the
    fallback for crops with no recorded entry.

    The rule this replaced stripped any trailing digits, which merged the unrelated
    e-commerce files `0x.jpg` and `0x244.jpg` into one group spanning six SKUs, and
    stripped `_front`/`_back` view suffixes without qualifying by class, merging
    `sunich_1L_orange` with `sunich_750ml_orange`. It also failed the other way:
    `t3.jpg` and its own crop `t3 (Edited).jpg` landed in different groups, so a
    photo that HAD fed the KB looked held-out. Over this KB the replacement takes
    multi-class groups from 21 down to 6, and those 6 are genuine shelf photos that
    really do contain several products.

    This wrapper keeps the single-argument signature for callers that only have a
    path; `grouped_cv` uses `resolve_all` directly so it can report how many crops
    it had to guess for.
    """
    return infer_source_photo(path)


def warn_shared_source_photos(samples, kb_path):
    """Warn when test crops come from shelf photos that also fed the KB.

    This is the failure mode `assert_no_leakage` explicitly does NOT catch: the
    files differ byte-for-byte, so the md5 check passes, but two crops from the
    same photo are the same bottle under the same lighting at the same instant —
    often literally adjacent facings of one product. A test set built that way
    measures "recognise a bottle whose neighbours you memorised", not "recognise
    this product on a future visit", and it reads far higher than reality.
    Measured here: 97.1% on such a test set versus 70.4% under source-photo-grouped
    cross-validation.

    A warning rather than an abort: the entire supplied test set overlaps, so
    failing would leave no way to run at all. The honest number is printed
    alongside instead (see `grouped_cv`).
    """
    kb_files = sorted(glob.glob(f"{kb_path}/**/*.jpg", recursive=True))
    kb_groups, _ = resolve_all(kb_path, kb_files)
    kb_photos = set(kb_groups)

    # Test crops have no manifest of their own yet, so their side is inferred. The
    # inference is now consistent with the KB side — under the old rule `t3.jpg` and
    # `t3 (Edited).jpg` produced different ids, which made an overlapping photo look
    # clean and would have let a "held-out" test set be built from a photo the KB
    # had already seen.
    known  = known_shelf_photos()
    shared = [p for p, _lbl in samples
              if infer_source_photo(p, known_photos=known) in kb_photos]
    if not shared:
        print("  Source-photo check: OK — test crops come from photos the KB never saw.")
        return
    photos = sorted({source_photo(p) for p in shared})
    print(f"\n  !! WEAK TEST SET: {len(shared)}/{len(samples)} test crops come from "
          f"shelf photo(s) that also contributed KB reference crops:")
    print(f"       {', '.join(photos)}")
    print("     These are different crops of the same shelf under the same lighting,")
    print("     so the accuracy below is optimistic. Treat the grouped-CV figure as")
    print("     the generalisation estimate, and build the test set from photos that")
    print("     contributed no KB images at all.")


def assert_no_leakage(samples, kb_path, allow=False):
    """Fail if any test crop is byte-identical to a knowledge-base crop.

    A leaked crop retrieves itself at similarity 1.0, so it is scored correct by
    construction and drags the threshold sweep toward a floor that only looks safe
    because nothing can fall below it. Cheap to check, catastrophic to miss —
    so this runs on every evaluation and raises by default.

    Note this catches exact copies only. Two *different* photos of the same
    physical bottle are also not independent samples; that needs a perceptual
    check and human judgement when the test set is assembled.
    """
    kb_hashes = {}
    for p in glob.glob(f"{kb_path}/**/*.jpg", recursive=True):
        kb_hashes.setdefault(_md5(p), p)

    leaked = [(p, kb_hashes[h]) for p, _lbl in samples
              if (h := _md5(p)) in kb_hashes]
    if not leaked:
        print(f"  Leakage check: OK — 0/{len(samples)} test crops appear in the KB.")
        return

    print(f"\n  !! LEAKAGE: {len(leaked)}/{len(samples)} test crops are byte-identical "
          f"to a knowledge-base image.")
    for test_p, kb_p in leaked[:10]:
        print(f"       {test_p}\n         == {kb_p}")
    if len(leaked) > 10:
        print(f"       … and {len(leaked) - 10} more")

    if allow:
        print("  --allow-leaked set: continuing, but every metric below is INVALID.\n")
        return
    raise SystemExit(
        "\nAborting: these results would be meaningless.\n"
        "Either remove the leaked crops from the test set, or re-run with "
        "--allow-leaked if you are deliberately inspecting the leaked behaviour."
    )


def embed_test_set(samples, img2vec, tta=False):
    """Embed every test crop once; reused across the threshold sweep.

    `tta` averages 5 augmented views per crop, matching main.py's default. The KB
    side stays un-augmented — the measured win comes from stabilising the QUERY,
    and leaving the KB alone keeps its embedding cache valid.
    """
    use_tta = tta and hasattr(img2vec, "getRobustVec")
    vecs = []
    for i, (path, _label) in enumerate(samples, 1):
        img = Image.open(path)
        vecs.append(img2vec.getRobustVec(img) if use_tta else img2vec.getVec(img))
        img.close()
        if i % 10 == 0 or i == len(samples):
            print(f"    embedded {i}/{len(samples)}")
    return vecs


def raw_predictions(vecs, index, mode):
    """classify_full() each vec once → (product, vote_conf, top_sim, margin).

    The margin is carried so the gate sweep can vary it without re-classifying.
    """
    return [classify_full(v, index, mode=mode) for v in vecs]


def score(raw, truths, conf_threshold, sim_threshold, margin_threshold=None):
    """Apply gates and return (predictions, accuracy, n_rejected).

    NOTE `accuracy` here is plain label agreement, which treats every rejection as
    an error — see `open_set_metrics` for the numbers that should drive threshold
    choice.
    """
    preds = [apply_gates(p, vc, ts, conf_threshold, sim_threshold,
                         margin=mg, margin_threshold=margin_threshold)
             for (p, vc, ts, mg) in raw]
    acc = accuracy_score(truths, preds)
    n_rejected = sum(1 for p in preds if p == "low_confidence")
    return preds, acc, n_rejected


def is_unknown_label(label):
    """True for the buckets that mean 'not a named product': unknown / non-beverage."""
    return label in UNKNOWN_LABELS or is_non_beverage(label)


def open_set_metrics(preds, truths):
    """Score naming and rejection SEPARATELY, because they are different jobs.

    Why plain accuracy cannot be used to pick a threshold
    -----------------------------------------------------
    A rejection threshold trades false accepts against false rejects. Scored with
    `accuracy_score`, a crop whose ground truth is `unknown_beverage` counts as WRONG
    the moment the gate rejects it — even though rejecting it is precisely the
    behaviour the gate exists to produce. Every rejection is therefore a pure loss,
    the sweep can only ever be maximised by a threshold of zero, and that is exactly
    what was observed and then written into `src/classifier.py:98-100` as "anything
    above 0.30 only rejects predictions that were CORRECT". That was an artifact of
    the objective, not a fact about the model.

    The two jobs, scored apart:

      sku_accuracy   — of the crops that ARE a known product, how many were named
                       correctly. Rejecting one is a false reject: a lost facing.
      neg_handled    — of the crops that are NOT a known product, how many were
                       either rejected or routed to an unknown/non-beverage bucket.
      false_accepts  — the complement: an off-brand or non-beverage crop confidently
                       given a specific SKU name. This is the damaging error for this
                       product, because it inflates that brand's share of shelf, and
                       it is invisible to per-crop accuracy on a test set of only
                       known products.

    `balanced` is their unweighted mean, offered as a single sortable number. It is a
    starting point, not a business objective — if a missed facing costs less than a
    competitor's bottle counted as ours, weight `neg_handled` higher and re-pick.
    """
    known = [(p, t) for p, t in zip(preds, truths) if not is_unknown_label(t)]
    neg   = [(p, t) for p, t in zip(preds, truths) if is_unknown_label(t)]

    sku_hit    = sum(1 for p, t in known if p == t)
    sku_reject = sum(1 for p, _ in known if p == "low_confidence")
    neg_ok     = sum(1 for p, _ in neg
                     if p == "low_confidence" or is_unknown_label(p))

    return {
        "n_known":       len(known),
        "n_neg":         len(neg),
        "sku_accuracy":  sku_hit / len(known) if known else float("nan"),
        "false_rejects": sku_reject,
        "neg_handled":   neg_ok / len(neg) if neg else float("nan"),
        "false_accepts": len(neg) - neg_ok,
        "balanced": (
            ((sku_hit / len(known)) + (neg_ok / len(neg))) / 2
            if known and neg else float("nan")
        ),
    }


def top_confusions(truths, preds, n=10):
    """Most common (true → predicted) mistakes, excluding correct calls."""
    mistakes = Counter((t, p) for t, p in zip(truths, preds) if t != p)
    return mistakes.most_common(n)


def grouped_cv(kb_path, classes, embeddings, modes=MATCH_MODES, n_splits=5):
    """Cross-validate on the KB, holding out whole source photos at a time.

    This is the generalisation estimate. Plain k-fold over KB crops reads ~17
    points higher because 270 crops come from only ~106 photos, so a held-out crop
    usually has a near-twin from the same photo still in the training half —
    exactly the flaw that makes the shipped test set optimistic. Grouping by
    source photo removes it.

    Note it is also somewhat pessimistic: each fold trains on 80% of an already
    thin KB, and classes with 4 reference images suffer most. The truth is
    between this and the test-set number, nearer this one.
    """
    import numpy as np
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.metrics import accuracy_score
    from src.classifier import KBIndex

    files = sorted(glob.glob(f"{kb_path}/**/*.jpg", recursive=True))
    X = np.asarray(embeddings, dtype=np.float32)
    y = np.asarray(classes)
    # Recorded provenance first, filename inference only for crops that predate the
    # manifest. `n_inferred` is printed rather than hidden: a run that had to guess
    # most of its groups has a correspondingly weaker claim to being leak-free.
    group_list, n_inferred = resolve_all(kb_path, files)
    groups = np.array(group_list)

    n_photos = len(set(groups))
    print(f"\n── Generalisation: {n_splits}-fold CV grouped by source photo ──")
    print(f"  {len(X)} KB crops from {n_photos} distinct photos "
          f"(whole photos held out together)")
    if n_inferred:
        print(f"  provenance: {len(files) - n_inferred} recorded, "
              f"{n_inferred} inferred from filenames"
              + ("  ← run tools/backfill_provenance.py --write"
                 if n_inferred == len(files) else ""))
    else:
        print(f"  provenance: all {len(files)} recorded (no filename guessing)")
    # Queries here ARE knowledge-base crops, so whatever embedding the KB used is
    # used on both sides. That makes this a measurement of a SYMMETRIC pipeline, and
    # it means grouped CV cannot measure the shipped asymmetry (TTA queries against
    # single-view references) at all — there is no separate query set to augment.
    # Measured symmetric comparison: single-view 69.7% argmax, TTA 70.9%, but TTA's
    # open-set rejection is worse at every margin below 0.20 (see
    # MARGIN_THRESH_BY_MODE). Use the independent test set to judge the asymmetry.
    print("  (symmetric: queries and references share this embedding)")

    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=0)
    folds = list(splitter.split(X, y, groups))

    print(f"\n  {'mode':<10} {'argmax':>7}   {'SKU acc':>8} {'f.rej':>6}   "
          f"{'neg ok':>7} {'f.acc':>6}")
    results = {}
    for mode in modes:
        # Keep the full (label, vote_conf, score) so the rejection gate can be
        # scored out-of-fold too. Argmax accuracy alone says nothing about whether
        # an off-brand crop gets handed a specific SKU name, which is the error that
        # actually distorts share of shelf.
        raw = np.empty(len(X), dtype=object)
        for tr, te in folds:
            idx = KBIndex(list(y[tr]), X[tr])
            raw[te] = [classify_full(v, idx, mode=mode) for v in X[te]]

        argmax = [r[0] for r in raw]
        thr    = default_threshold(mode)
        mthr   = default_margin(mode)
        gated  = [apply_gates(p, vc, s, CONF_THRESH, thr,
                              margin=mg, margin_threshold=mthr)
                  for (p, vc, s, mg) in raw]
        m      = open_set_metrics(gated, y)

        print(f"  {mode:<10} {accuracy_score(y, argmax):>7.1%}   "
              f"{m['sku_accuracy']:>8.1%} {m['false_rejects']:>6}   "
              f"{m['neg_handled']:>7.1%} {m['false_accepts']:>6}")
        results[mode] = {"argmax": accuracy_score(y, argmax), **m}

    print("\n  argmax  = nearest class ignoring the gate (comparable to older runs)")
    print("  SKU acc = of crops that ARE a known product, named correctly")
    print("  f.acc   = off-brand/non-beverage crops given a specific SKU name —")
    print("            the error that inflates a brand's share of shelf")
    return results


def evaluate_ocr(samples, vecs, truths, index, args):
    """A/B the OCR-assisted variant against the embedding-only baseline.

    OCR is run ONCE per crop and the signals are reused across every fusion
    setting — EasyOCR dominates the runtime, so re-reading per configuration
    would make the sweep unusable.
    """
    import time
    from src.ocr import OcrReader, fuse, should_consult

    print("\n── OCR-assisted variant ────────────────────────────────────────")
    try:
        reader = OcrReader()
    except Exception as e:
        print(f"  OCR unavailable ({type(e).__name__}: {e}) — skipping.")
        return

    t0 = time.time()
    signals, all_cands = [], []
    for i, ((path, _lbl), vec) in enumerate(zip(samples, vecs), 1):
        all_cands.append(top_matches(vec, index, k=len(index.products),
                                     mode=args.match_mode))
        signals.append(reader.read(path))
        if i % 10 == 0 or i == len(samples):
            print(f"    ocr {i}/{len(samples)}")
    dt = time.time() - t0
    print(f"  OCR: {dt:.0f}s total, {dt/max(1,len(samples)):.1f}s/crop")

    n_text   = sum(1 for s in signals if s)
    # Count a brand as READ only under the same gate `fuse` applies — score AND
    # margin over the runner-up brand. Reporting bare best_brand() here overstated
    # the yield, since a garbled token scores ~0.6 against every brand at once.
    n_brand  = sum(1 for s in signals
                   if s.brand_ranked()[1] >= 0.60
                   and s.brand_ranked()[1] - s.brand_ranked()[2] >= 0.15)
    n_flav   = sum(1 for s in signals if s.best_flavour()[1] >= 0.60)
    n_flav_ok = sum(1 for s, t in zip(signals, truths)
                    if s.best_flavour()[1] >= 0.60 and s.best_flavour()[0] in t)
    print(f"  Yield: text on {n_text}/{len(samples)} crops, "
          f"brand recognised on {n_brand}, flavour word on {n_flav} "
          f"({n_flav_ok} of those agree with ground truth)")

    base_acc = accuracy_score(truths, [c[0][0] for c in all_cands])
    print(f"\n  {'verify':>7} {'margin':>7} {'alpha':>6}  {'consulted':>10}  "
          f"{'accuracy':>9}  vs baseline")
    print(f"  {'—':>7} {'—':>7} {'—':>6}  {'0':>10}  {base_acc:>8.1%}   (embedding only)")
    # verify_brand=True is main.py's shipped default, so it has to be one of the
    # rows here — otherwise this harness measures a configuration nobody runs.
    for verify in (False, True):
        for margin in (0.35, 1.01):
            for alpha in (args.ocr_alpha, 3.0):
                preds, n_used = [], 0
                for cands, sig in zip(all_cands, signals):
                    if should_consult(cands, margin, verify_brand=verify):
                        n_used += 1
                        cands = fuse(cands, sig, alpha=alpha)
                    preds.append(cands[0][0])
                acc = accuracy_score(truths, preds)
                delta = acc - base_acc
                sign = "+" if delta >= 0 else ""
                print(f"  {str(verify):>7} {margin:>7.2f} {alpha:>6.1f}  {n_used:>10}  "
                      f"{acc:>8.1%}   {sign}{delta:.1%}")


def main():
    ap = argparse.ArgumentParser(description='Evaluate the shelf-product classifier')
    ap.add_argument('--model',          default='dino2', choices=['dino2', 'resnet18'])
    ap.add_argument('--match-mode',     default=DEFAULT_MODE, choices=list(MATCH_MODES))
    ap.add_argument('--conf-threshold', type=float, default=CONF_THRESH)
    # Default resolved per-mode after parsing: the score being gated is a cosine
    # similarity for prototype/knn but a posterior probability for lda.
    ap.add_argument('--sim-threshold',  type=float, default=None)
    ap.add_argument('--test-path',      default=TEST_SET_PATH)
    ap.add_argument('--tta',            action=argparse.BooleanOptionalAction, default=True,
                    help='Test-time augmentation on the query crops, matching main.py. '
                         'ON by default (+2.2 points grouped CV, McNemar p=0.031).')
    ap.add_argument('--no-sweep',       action='store_true', help='Skip the threshold sweep')
    ap.add_argument('--no-cv',          action='store_true',
                    help='Skip the source-photo-grouped cross-validation. That figure is '
                         'the honest generalisation estimate — the test-set accuracy above '
                         'it is optimistic whenever the two share source photos.')
    ap.add_argument('--allow-leaked',   action='store_true',
                    help='Run even if test crops are copies of KB crops. Debugging only — '
                         'the resulting metrics are invalid.')
    ap.add_argument('--ocr',            action='store_true',
                    help='Also score the OCR-assisted variant, so the contribution of '
                         'label text is measured rather than assumed. Slow (EasyOCR runs '
                         'once per test crop) but the signals are reused across settings.')
    ap.add_argument('--ocr-margin',     type=float, default=0.35,
                    help='Consult OCR only when top1-top2 probability gap is below this '
                         '(default: 0.35). 1.0 = always consult.')
    ap.add_argument('--ocr-alpha',      type=float, default=1.5,
                    help='Strength of the OCR bonus in fusion (default: 1.5)')
    args = ap.parse_args()
    if args.sim_threshold is None:
        args.sim_threshold = default_threshold(args.match_mode)

    # The box-drawing characters below are undefined in cp1252, which is the default
    # console encoding on Windows — without this the harness dies on its first header.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    samples = load_test_crops(args.test_path)
    if not samples:
        print(f"No test crops found under {args.test_path}/<label>/*.jpg")
        print("Create a small labelled test set first (folder name = product label).")
        raise SystemExit(1)
    truths = [lbl for _p, lbl in samples]
    print(f"Test set: {len(samples)} crops across {len(set(truths))} labels")
    assert_no_leakage(samples, KB_PATH, allow=args.allow_leaked)
    warn_shared_source_photos(samples, KB_PATH)

    print(f"\nLoading {args.model} + knowledge base…")
    img2vec = Img2VecDino2() if args.model == "dino2" else Img2VecResnet18()
    classes, embeddings = load_kb_embeddings(KB_PATH, img2vec)
    index = KBIndex(classes, embeddings)
    print(f"  KB: {len(index.products)} products, {len(embeddings)} reference images")

    print(f"\nEmbedding test crops… (TTA {'on' if args.tta else 'off'})")
    vecs = embed_test_set(samples, img2vec, tta=args.tta)
    raw  = raw_predictions(vecs, index, args.match_mode)

    # ── Headline: both modes at default thresholds, for a quick comparison ──
    print("\n── Mode comparison (each at its own default threshold) ──────────")
    for mode in MATCH_MODES:
        r = raw_predictions(vecs, index, mode)
        # Each mode is gated on its own scale — comparing lda posteriors against a
        # cosine floor of 0.60 would reject good predictions and understate it.
        thr = default_threshold(mode)
        _, acc, n_rej = score(r, truths, args.conf_threshold, thr)
        star = " ←" if mode == args.match_mode else ""
        print(f"  {mode:<10} accuracy={acc:.1%}  rejected={n_rej}/{len(samples)}"
              f"  (thr={thr:.2f}){star}")

    # ── Detailed report for the selected mode ──
    preds, acc, n_rej = score(raw, truths, args.conf_threshold, args.sim_threshold)
    print(f"\n── Report: mode={args.match_mode}  sim≥{args.sim_threshold}  "
          f"vote≥{args.conf_threshold} ──")
    print(f"  Accuracy: {acc:.1%}   Rejected (low_confidence): {n_rej}/{len(samples)}")

    m = open_set_metrics(preds, truths)
    print("\n  Open-set breakdown (naming and rejection scored separately):")
    print(f"    known products   n={m['n_known']:<4} named correctly {m['sku_accuracy']:.1%}"
          f"   false rejects {m['false_rejects']}")
    print(f"    not-a-product    n={m['n_neg']:<4} handled correctly {m['neg_handled']:.1%}"
          f"   FALSE ACCEPTS {m['false_accepts']}")
    print("    A false accept is an off-brand or non-beverage crop given a specific")
    print("    SKU name — it inflates that brand's share of shelf and is invisible to")
    print("    the plain accuracy figure above.")

    print("\n  Per-class precision / recall:")
    print(classification_report(truths, preds, zero_division=0))

    confusions = top_confusions(truths, preds)
    if confusions:
        print("  Top misclassifications (true → predicted):")
        for (t, p), c in confusions:
            print(f"    {c:>3}×  {t}  →  {p}")

    # ── Generalisation estimate (independent of the supplied test set) ──────
    if not args.no_cv:
        grouped_cv(KB_PATH, classes, embeddings)

    # ── OCR-assisted variant ────────────────────────────────────────────────
    if args.ocr:
        evaluate_ocr(samples, vecs, truths, index, args)

    # ── Threshold sweep: show the accept/reject trade-off, not one number ──
    if not args.no_sweep:
        print(f"\n── Score-threshold sweep (mode={args.match_mode}) ──")
        m0 = open_set_metrics(preds, truths)
        if not m0["n_neg"]:
            print("  !! The test set contains no negatives (no unknown_beverage or")
            print("     non_beverage crops), so a rejection threshold CANNOT be chosen")
            print("     from it: every rejection scores as an error and the sweep is")
            print("     maximised at 0.00 by construction. Add off-brand and")
            print("     non-beverage crops before reading anything into the column below.")

        print(f"  {'thr':>5}  {'SKU acc':>8} {'f.rej':>6}   "
              f"{'neg ok':>7} {'f.acc':>6}   {'balanced':>8}")
        best = (-1.0, None)
        thr = 0.0
        while thr <= 0.90 + 1e-9:
            sp, _, _ = score(raw, truths, args.conf_threshold, thr)
            m = open_set_metrics(sp, truths)
            better = m["balanced"] == m["balanced"] and m["balanced"] > best[0]
            print(f"  {thr:>5.2f}  {m['sku_accuracy']:>8.1%} {m['false_rejects']:>6}   "
                  f"{m['neg_handled']:>7.1%} {m['false_accepts']:>6}   "
                  f"{m['balanced']:>8.1%}{'  *' if better else ''}")
            if better:
                best = (m["balanced"], thr)
            thr += 0.05

        if best[1] is not None:
            print(f"\n  Best balanced: threshold={best[1]:.2f} → {best[0]:.1%}")
            print("  Read the whole column, not just the star: 'balanced' weights a lost")
            print("  facing and a competitor counted as ours equally, which is unlikely to")
            print("  match the business. Pick the row whose false-accept count you can live")
            print(f"  with, then set it with --sim-threshold (current: {args.sim_threshold:.2f}).")


if __name__ == "__main__":
    main()
