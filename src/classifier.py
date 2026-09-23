"""Shared classification core.

Both the production pipeline (`main.py`) and the evaluation harness (`evaluate.py`)
import from here so they exercise the *exact same* KB-loading and matching logic —
no drift between what we measure and what we ship.

Three matching modes. The numbers below are 5-fold cross-validation grouped by
SOURCE PHOTO over the 419-crop knowledge base (`tools/baseline_cv.py`), with
provenance read from `data/knowledge_base/provenance.csv` — no filename guessing,
no crop scored against a twin from its own photograph:

  * "lda"       — 69.7%. Supervised head fitted on the KB embeddings. Cosine matching
                  weights all 768 dimensions equally, but most encode bottle shape and
                  shelf lighting, which every SKU of a brand shares; LDA learns the
                  small subspace where flavour actually lives. THE DEFAULT.
  * "knn"       — 59.7%. Weighted inverse-distance vote over the k nearest reference
                  crops (the original behaviour). Biased when a class is over-represented.
  * "prototype" — 53.7%. One L2-normalised centroid per class. Intended to fix KB
                  imbalance, but averaging washes out the fine detail that separates
                  look-alike SKUs: the 750ml prototypes sit at mean cosine 0.909 from
                  each other, so the family collapses. Kept for comparison.

An earlier version of this docstring reported 97.1% / 79.4% / 70.6% "on the 34-crop
test set". Do not resurrect those figures. They were wrong twice over:

  1. Selection. The match mode, the rejection thresholds, the letterbox
     preprocessing and TTA were each chosen by maximising accuracy on those same
     crops, so the number quoted afterwards was an estimate of how well the choices
     fit that set, not of how the pipeline generalises.
  2. Leakage. By the time it was last measured the test set had grown to 315 crops,
     269 of them BYTE-IDENTICAL to knowledge-base images (`test_set/unknown_beverage`
     and `test_set/non_beverage` were straight copies of the KB folders, plus 153
     clustering artifacts). A leaked crop retrieves itself at similarity 1.0 and is
     scored correct by construction. `evaluate.py:assert_no_leakage` refuses to run
     on it, so those figures could only have come from `--allow-leaked`.

The gap between 97.1% and 69.7% is the cost of measuring on data you tuned against
and partly trained on. Measure changes against the grouped-CV figure.

Two rejection gates (see `apply_gates`):
  * score gate — floor on the match score. NOTE the score is a cosine similarity in
                 knn/prototype but a posterior probability in lda, so the floor is
                 per-mode — use `default_threshold(mode)`, don't hardcode 0.60.
  * vote gate  — the original relative vote-share floor (kNN mode only).

Open-set behaviour does NOT come from the score gate. It comes from the KB's
`unknown_beverage` and `non_beverage*` buckets. Keep those buckets populated;
they are load-bearing, and the gate is not a substitute for them.

These buckets work far better than this docstring used to claim. Measured
out-of-fold under source-photo-grouped CV on the cleaned KB
(`tools/negative_confusion.py`, lda mode, margin gate off):

    non_beverage      n=58   -> same bucket 70.7%   other bucket 29.3%   a SKU 0.0%
    unknown_beverage  n=51   -> same bucket 84.3%   other bucket  5.9%   a SKU 9.8%

    Overall 5 of 109 negatives (4.6%) were given a specific product name.

The previous text here reported "unknown_beverage n=28 recall 25%" and concluded
"three quarters of off-brand drinks are still handed a specific Sunich SKU, which
inflates Sunich share-of-shelf". Both the number and the conclusion were wrong:

  * WRONG METRIC. Per-bucket recall counts an `unknown_beverage -> non_beverage`
    prediction as a miss. For share of shelf it is not a miss at all — both buckets
    mean "not a named product" and both are excluded from the count. Only the
    "-> a SKU" column is a real error, and it is 4.6%, not 75%.

  * CONTAMINATED MEASUREMENT. That 25% was measured while the KB contained six
    phantom classes (`noise`, `cluster_0`..`cluster_4`) written into it by
    `src/cluster.py` — 255 images, 38% of the KB, and every one of them a COPY of an
    `unknown_beverage` crop. Those copies competed for exactly the predictions
    `unknown_beverage` should have won, so the bucket's recall was being stolen by
    duplicates of itself. Removing them took recall 25% -> 84.3%.

The structural criticism still stands in principle — the bucket IS a grab-bag whose
within-class scatter inflates the single pooled covariance LDA shares across all
classes — but the evidence no longer supports treating a dedicated out-of-distribution
detector as urgent. The cheap mitigations (keep the buckets populated and varied, and
use the margin gate below) already take false accepts to zero on this data. Re-measure
before investing in an OOD model.

`unknown_beverage` was previously split into `unknown_bottle` (26 refs) and
`unknown_can` (2). The split bought nothing — container shape is not what the
bucket is for, and at 2 images `unknown_can` could not be fitted at all (0%
recall) while tripping the n_splits warning on every evaluation run. Merging
lifted overall grouped CV 71.8% -> 72.4% and bucket recall 23% -> 25%, both
marginal; the real reason to do it is that one bucket is the honest model of
"a drink we are choosing not to name". Note it cost `non_beverage` some recall
(71% -> 62%) — the buckets compete for the same ambiguous crops.
"""

import os
import glob
import pickle
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.neighbors import NearestNeighbors
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

# Reference class that is not a real product — the generic "unknown" bucket for a
# beverage we detect but deliberately do not name.
#
# Deliberately NOT called plain "unknown": `src/llm_fallback.py` uses that string
# as its "no match" sentinel and `report.py` skips it, so a KB class of that name
# would be silently dropped from share-of-shelf.
UNKNOWN_LABELS = {"unknown_beverage"}

# Distractor reference classes for things we DETECT but do NOT want to report:
# non-beverages (snacks, boxes, jars, cartons…). Any knowledge-base folder whose
# name starts with this prefix is treated as "skip" — a crop matched to it is
# excluded from predictions and the facings count, rather than being forced into
# `low_confidence` where it would be indistinguishable from a genuinely novel
# beverage. To use: add folders like `non_beverage_snack/`, `non_beverage_box/`
# under the KB with a handful of example crops each (the KB cache auto-refreshes).
NON_BEVERAGE_PREFIX = "non_beverage"


def is_non_beverage(label):
    """True if `label` is a non-beverage distractor class that should be skipped."""
    return label.startswith(NON_BEVERAGE_PREFIX)

# Defaults (tune with evaluate.py's threshold sweep).
MATCH_MODES   = ('lda', 'knn', 'prototype')
DEFAULT_MODE  = 'lda'
N_NEIGHBORS   = 5

# Softmax temperature for the kNN vote — see the note in `classify_full`. Smaller
# means the nearest neighbour dominates more; larger approaches an unweighted vote.
KNN_TEMPERATURE = 0.05
CONF_THRESH   = 0.40   # min vote-share to accept (knn mode)
SIM_THRESH    = 0.60   # min cosine similarity to accept (prototype/knn)

# The rejection floor is per-mode because the score it gates is a different
# quantity in each: a cosine similarity for prototype/knn, a posterior
# probability for lda. Reusing 0.60 across all three would silently apply a
# near-meaningless floor to lda.
#
# The lda floor is deliberately loose. Measured on the test set, anything above
# 0.30 only rejects predictions that were CORRECT (97.1% -> 94.1% at 0.50,
# 88.2% at 0.60), and it buys nothing in exchange: off-brand products are caught
# by the unknown_*/non_beverage buckets, which scored 14/14 at both 0.30 and
# 0.50. So the gate is a backstop against a genuinely uncertain crop, not the
# open-set mechanism — keep it low and keep those buckets populated instead.
SIM_THRESH_BY_MODE = {'prototype': 0.60, 'knn': 0.60, 'lda': 0.30}

# Margin floor (top-1 score minus runner-up) per mode. None = gate disabled.
#
# Measured out-of-fold with `tools/gate_sweep.py` over source-photo-grouped CV on the
# 419-crop KB, which contains 109 negatives (51 unknown_beverage + 58 non_beverage):
#
#   score  margin   SKU acc  false rejects   negatives handled   FALSE ACCEPTS
#    0.00   0.00     67.1%         0               95.4%               5
#    0.30   0.00     66.5%         5               95.4%               5   <- was shipped
#    0.30   0.05     65.2%        16               99.1%               1   <- now default
#    0.30   0.10     64.8%        23              100.0%               0
#
# The two errors are not equally expensive: a false reject drops one facing out of
# the share DENOMINATOR, while a false accept moves a competitor's bottle into YOUR
# numerator. So some asymmetry in favour of rejecting is right.
#
# 0.05 rather than 0.10 deliberately. 0.10 buys the last false accept for 7 more lost
# facings, and 0 vs 1 on n=109 negatives is well inside noise — paying a real,
# measurable cost for a difference that is not measurable is a bad trade. 0.05
# removes 4 of the 5 for 11 lost facings, which is the part of the curve where the
# gate is actually earning its keep.
#
# Worth knowing when you re-tune: most of what the margin gate rejects is ambiguity
# between two SUNICH FLAVOURS, not between Sunich and a competitor. If you report
# share at BRAND level those confusions cancel and the gate mostly costs you, so
# 0.00 becomes defensible. At SKU level they don't cancel and the gate helps.
#
# ANY CHANGE TO THE EMBEDDING INVALIDATES THIS TABLE. Re-run tools/gate_sweep.py.
# Demonstrated, not hypothetical: embedding the KB with TTA shifts every margin
# upward (median 0.922 -> 0.933, and the whole distribution with it), so the SAME
# 0.05 threshold gave 1 false accept on single-view references and 4 on TTA ones.
# A threshold is a property of the score distribution, not of the pipeline.
#
#   condition                      margin for ~1 f.acc   margin for 0 f.acc
#   single-view references         0.05 -> 65.2% SKU     0.10 -> 64.8%, 23 f.rej
#   TTA references (5 views)       unreachable           0.20 -> 64.2%, 44 f.rej
#
# TTA on the reference side raises closed-set naming (68.1% vs 66.5% with the gate
# off) but LOWERS open-set rejection at every margin below 0.20 — it smooths
# off-brand crops toward known class means too, making them look more like real
# products. At the operating point chosen here it does not pay, so references stay
# single-view. `load_kb_embeddings(tta=True)` keeps the capability for re-testing.
#
# Note what the same table says about the score floor: at margin 0.10 the rows for
# score 0.00 and 0.30 are IDENTICAL, and at margin 0.00 the 0.30 floor rejects 5
# crops that were all correct while catching no false accepts at all. It is inert.
# It is kept only as a cheap backstop for a genuinely degenerate embedding.
#
# knn and prototype are left disabled: they have not been swept, and shipping an
# unmeasured threshold is how the last set of magic numbers got here. Run
# `tools/gate_sweep.py --mode knn` before enabling one.
#
# HONEST CAVEAT: 0.10 was chosen by reading the table above, which was computed on
# the same KB it is now applied to. The predictions are out-of-fold, so this is far
# better than the previous practice of tuning on the test set — but the CHOICE still
# saw the numbers. Confirm it on the independent test set once that is rebuilt
# (tools/build_test_set.py), and treat 0 vs 1 false accept as noise on n=109.
MARGIN_THRESH_BY_MODE = {'lda': 0.05, 'knn': None, 'prototype': None}


def default_threshold(mode):
    """Rejection floor appropriate to `mode`."""
    return SIM_THRESH_BY_MODE.get(mode, SIM_THRESH)


def default_margin(mode):
    """Margin floor appropriate to `mode`; None when the gate is disabled."""
    return MARGIN_THRESH_BY_MODE.get(mode)


# Thin-class warnings are deduplicated per process. `evaluate.py` builds a fresh
# KBIndex for every CV fold and every mode, so an un-deduplicated warning prints
# nine times for one underlying problem and buries the accuracy figures it sits
# between.
_warned_thin = set()


# Softmax temperature for the LDA head.
#
# LDA's raw posteriors are unusable as a confidence signal: it whitens
# within-class scatter to unit variance in a 19-dimensional space, so
# between-class distances land in the tens, squaring them puts the gap between
# rank-1 and rank-2 at a median of ~58 LOG units, and softmax then reports
# 100% / 0% / 0% / 0% for every single crop. That is arithmetic, not certainty,
# and it makes the ranked candidate list (`top_matches`) useless — the whole point of
# that list is to show the runner-up when the top call is wrong.
#
# Dividing the discriminant scores by T before the softmax fixes the display.
# T=30 was fitted by minimising out-of-fold negative log-likelihood over 5-fold CV
# on the KB (NLL 9.43 at T=1, 0.574 at T=30); re-fit with proper calibration if the
# KB changes a lot.
#
# T IS NOT DECISION-NEUTRAL. This comment used to claim it was — "softmax is
# monotone, so the ranking and the argmax are bit-for-bit identical at any T" —
# which is true of the RANKING and false of the DECISION, because the score then
# goes to `apply_gates` and is compared against a floor. At T=1 the posteriors
# saturate to 1.0/0.0 and nothing is ever rejected; at T=30 they spread out and the
# floor starts to bite. So T and the rejection threshold are ONE COUPLED PAIR of
# hyperparameters, and they were fitted by two procedures that never saw each other
# (NLL minimisation for T, a test-set accuracy sweep for the floor).
#
# The danger was the comment more than the coupling: it told the next person T was a
# display knob, so retuning it for display would have silently moved the
# operating point with no visible symptom. If you change T, re-pick the gate.
#
# The margin gate below reduces but does NOT remove this coupling — a probability
# margin p1-p2 still depends on T. What it does fix is drift with class count.
LDA_TEMPERATURE = 30.0


def _lda_scores(index, vec):
    """Temperature-scaled LDA posteriors for one vector, as (labels, probs)."""
    d = np.atleast_2d(index.lda.decision_function([vec]))[0].astype(np.float64)
    z = d / LDA_TEMPERATURE
    z -= z.max()
    p = np.exp(z)
    return index.lda.classes_, p / p.sum()


# ── Knowledge-base embedding cache ──────────────────────────────────────────

def _cache_signature(kb_path, list_imgs):
    """Path-form-independent fingerprint of the KB contents.

    Keyed on paths RELATIVE to kb_path plus file size. Absolute paths would make
    the cache miss whenever the pipeline is invoked from a different working
    directory or with an absolute --kb path, silently re-embedding all 270 images
    (~4 minutes on CPU) on a KB that never changed. Size catches a file being
    replaced in place, which a name-only key would miss.
    """
    return [(os.path.relpath(p, kb_path).replace("\\", "/"), os.path.getsize(p))
            for p in list_imgs]


def assert_flat_class_tree(root, files, what="knowledge base"):
    """Fail loudly if any image sits deeper than `<root>/<class>/<file>.jpg`.

    The label comes from `Path(f).parent.name`, so ANY directory nested under a
    class folder silently becomes a new class. That is not hypothetical: for five
    runs `src/cluster.py` wrote its output to
    `<kb>/unknown_beverage/clustering_results/run_*/cluster_0/`, and this loader
    dutifully registered `cluster_0`…`cluster_4` and `noise` as products. 255 of
    674 KB images — 38% — were clustering artifacts, `noise` was the largest class
    in the knowledge base, and `classify()` could return it as a beverage that then
    appeared in share_of_shelf.csv with a market share. The same thing happened to
    `data/test_set/`, leaving 269 of 315 test crops byte-identical to KB images.

    A depth check rather than a folder allowlist on purpose: an allowlist needs
    editing every time a real SKU is added, so it rots and eventually gets removed.
    Depth needs no maintenance and cannot be defeated by accident — anything that
    writes a subdirectory into a class folder trips it on the very next run.
    """
    nested = [p for p in files
              if len(Path(os.path.relpath(p, root)).parts) != 2]
    if not nested:
        return

    bad_dirs = sorted({str(Path(os.path.relpath(p, root)).parent) for p in nested})
    listing  = "\n".join(f"    {d}" for d in bad_dirs[:10])
    more     = f"\n    … and {len(bad_dirs) - 10} more" if len(bad_dirs) > 10 else ""
    raise ValueError(
        f"Malformed {what} at {root}: {len(nested)} image(s) are nested deeper "
        f"than <class>/<image>.jpg.\n"
        f"  Offending directories:\n{listing}{more}\n\n"
        f"  The class label is the image's parent folder name, so each of these "
        f"would be registered as a product.\n"
        f"  Expected layout: {root}/<class_name>/<image>.jpg — exactly one level.\n"
        f"  If this is generated output (clustering runs, exports, backups), move "
        f"it outside {root} entirely; do not nest it under a class folder."
    )


def kb_variant(tta=False, tta_flip=True):
    """Name for a KB embedding variant; '' is the plain single-view default."""
    if not tta:
        return ""
    return "tta" if tta_flip else "tta_noflip"


def load_kb_embeddings(kb_path, img2vec, tta=False, tta_flip=True):
    """Return (classes, embeddings) from cache or recompute if KB changed.

    `tta` embeds each reference as the average of several augmented views, the same
    way `main.py` embeds query crops. Leaving it off makes queries and references
    live in different distributions and fits the LDA head on single-view vectors it
    will never see at inference — see `Img2VecDino2.getRobustVec`.

    Each variant gets its OWN cache file. Sharing one would make a TTA run and a
    plain run invalidate each other on every alternation, silently re-embedding all
    419 images (minutes on CPU) each time — and a cache key that merely *detected*
    the mismatch would still thrash. Separate files let both stay warm.
    """
    variant    = kb_variant(tta, tta_flip)
    cache_name = f".kb_cache{'_' + variant if variant else ''}.pkl"
    cache_file = Path(kb_path) / cache_name
    list_imgs  = sorted(glob.glob(f"{kb_path}/**/*.jpg", recursive=True))

    if not list_imgs:
        raise ValueError(
            f"Knowledge base is empty: no .jpg files found under {kb_path}\n"
            "Add labelled crop images first (see README Step 2)."
        )

    assert_flat_class_tree(kb_path, list_imgs, what="knowledge base")

    # Class name alone is NOT enough to identify the embedding: changing the
    # preprocessing inside an embedder produces different vectors under the same
    # class name, which would silently serve a stale cache. Embedders expose
    # EMBED_VERSION and bump it whenever their output changes.
    model_key = (img2vec.__class__.__name__, getattr(img2vec, "EMBED_VERSION", 1),
                 variant)
    signature = _cache_signature(kb_path, list_imgs)

    if cache_file.exists():
        with open(cache_file, 'rb') as f:
            cache = pickle.load(f)
        if cache.get('signature') == signature and cache.get('model') == model_key:
            print(f"  Loaded {len(list_imgs)} KB embeddings from cache.")
            return cache['classes'], cache['embeddings']

    use_tta = tta and hasattr(img2vec, "getRobustVec")
    print(f"  Computing embeddings for {len(list_imgs)} KB images (first run only)"
          f"{' with TTA — 5x slower' if use_tta else ''}…")
    classes, embeddings = [], []
    for i, filename in enumerate(list_imgs, 1):
        img = Image.open(filename)
        vec = (img2vec.getRobustVec(img, include_flip=tta_flip) if use_tta
               else img2vec.getVec(img))
        img.close()
        classes.append(Path(filename).parent.name)
        embeddings.append(vec)
        if i % 10 == 0 or i == len(list_imgs):
            print(f"    {i}/{len(list_imgs)}")

    with open(cache_file, 'wb') as f:
        pickle.dump({'signature': signature, 'classes': classes,
                     'embeddings': embeddings, 'model': model_key}, f)
    print("  Embeddings cached — next run will be instant.")
    return classes, embeddings


# ── Index ───────────────────────────────────────────────────────────────────

class KBIndex:
    """Holds the per-image kNN index, the per-class prototype index, and the LDA head."""

    def __init__(self, classes, embeddings, n_neighbors=N_NEIGHBORS):
        self.classes    = list(classes)
        self.embeddings = np.asarray(embeddings, dtype=np.float32)

        # Per-image kNN (original behaviour).
        self.k = min(n_neighbors, len(self.embeddings))
        self.knn = NearestNeighbors(metric='cosine', n_neighbors=self.k, algorithm='brute')
        self.knn.fit(self.embeddings)

        # Per-class prototypes: one L2-normalised centroid per label.
        self.proto_labels = sorted(set(self.classes))
        protos = []
        for lab in self.proto_labels:
            rows = [i for i, c in enumerate(self.classes) if c == lab]
            centroid = self.embeddings[rows].mean(axis=0)
            norm = np.linalg.norm(centroid)
            protos.append(centroid / norm if norm > 0 else centroid)
        self.proto_matrix = np.asarray(protos, dtype=np.float32)
        self.proto_knn = NearestNeighbors(metric='cosine', n_neighbors=1, algorithm='brute')
        self.proto_knn.fit(self.proto_matrix)

        # Supervised head. Cosine matching treats all 768 dimensions as equally
        # informative, but most of them encode bottle shape and shelf lighting —
        # shared by every Sunich SKU — while flavour lives in a small subspace.
        # LDA learns that subspace from the KB labels, which is why it separates
        # the 750ml family that raw cosine collapses. Ledoit-Wolf shrinkage keeps
        # it stable at 270 samples x 768 dims (far more features than samples).
        self.lda = self._fit_lda()

    def _fit_lda(self):
        """Fit the LDA head over every class that has enough references.

        Classes with a single reference image are EXCLUDED from the fit rather
        than disabling the head. The old behaviour returned None here, which
        silently downgraded the entire pipeline to kNN — 97.1% to 79.4% on the
        test set — because one folder somewhere had one image in it. That is a
        bad trade and an easy trap to fall into: adding a new competitor brand
        starts with exactly one crop of it, so the act of extending the knowledge
        base was what broke the classifier, and the only symptom was one printed
        line in the middle of a long startup log.

        The cost of excluding instead is local and loud: a thin class simply
        cannot be predicted in lda mode, so crops of that product fall to whatever
        the head does have — which for a competitor pack means a same-flavour
        class of the wrong brand. Hence the warning below says what to do about it
        rather than just reporting a number.
        """
        counts = {lab: self.classes.count(lab) for lab in self.proto_labels}
        thin   = sorted(lab for lab, n in counts.items() if n < 2)
        if thin and tuple(thin) not in _warned_thin:
            _warned_thin.add(tuple(thin))
            print(f"  ⚠ LDA cannot fit {len(thin)} class(es) with only 1 reference "
                  f"image: {', '.join(thin)}")
            print("    They will never be predicted in lda mode — crops of them "
                  "land on the nearest class that IS fitted. Add a 2nd reference "
                  "crop each (a different facing, ideally the other language face).")

        rows = [i for i, c in enumerate(self.classes) if counts[c] >= 2]
        fit_labels = sorted({self.classes[i] for i in rows})
        if len(fit_labels) < 2:
            print("  LDA head unavailable: fewer than 2 classes with ≥2 reference images.")
            return None

        embeddings = self.embeddings[rows]
        labels     = np.asarray([self.classes[i] for i in rows])
        try:
            # priors=uniform on purpose. sklearn's default estimates priors from
            # the TRAINING class frequencies — here that's how many reference
            # photos we happened to take of each SKU (4 to 44), not how often it
            # actually appears on a shelf. Left at the default, the posterior is
            # silently tilted toward whichever class we photographed the most,
            # which is backwards: KB size is a labelling artifact, not a signal
            # about the real world. Uniform priors let the discriminant score
            # alone decide, so photographing more angles of one SKU can no
            # longer out-vote a thinner class on a genuinely closer match.
            n_classes = len(fit_labels)
            return LinearDiscriminantAnalysis(
                solver='eigen', shrinkage='auto',
                priors=np.full(n_classes, 1.0 / n_classes),
            ).fit(embeddings, labels)
        except Exception as e:                       # singular covariance, etc.
            print(f"  LDA head unavailable ({type(e).__name__}: {e})")
            return None

    @property
    def products(self):
        return self.proto_labels


# ── Classification ───────────────────────────────────────────────────────────

def classify(vec, index, mode=DEFAULT_MODE):
    """Return (product, vote_confidence, score). See `classify_full` for the margin.

    The default used to be 'prototype' while DEFAULT_MODE was 'lda', so any caller
    that omitted `mode` silently got the WORST of the three modes (53.7% vs 69.7%
    grouped CV). Every current caller passes it explicitly, so this was dormant —
    but it is exactly the kind of trap that costs a day when someone adds a caller.
    """
    return classify_full(vec, index, mode=mode)[:3]


def classify_full(vec, index, mode=DEFAULT_MODE):
    """Return (product, vote_confidence, score, margin).

    vote_confidence — relative vote share (kNN); 1.0 in the other modes (not meaningful there).
    score           — the mode's native confidence, in [0, 1]. Cosine similarity to the
                      best match for prototype/knn; posterior probability for lda. The
                      scales are NOT comparable, which is why the rejection floor is
                      per-mode (see SIM_THRESH_BY_MODE).
    margin          — score of the best class minus the runner-up, on that same scale.
                      0.0 when there is only one class to choose from.

    Why the margin is worth carrying
    --------------------------------
    An absolute floor on `score` drifts as the knowledge base grows. With uniform
    priors over C classes, chance is 1/C, so typical top-1 posteriors shrink as
    classes are added and a fixed floor of 0.30 silently tightens every time a SKU is
    introduced — the gate gets stricter without anyone changing it. The class count
    went 20 -> 26 -> 20 during the clustering-contamination episode alone.

    A margin only involves the top two candidates, so adding a distant class barely
    moves it. It is also the quantity that matches the actual question: "is this
    crop clearly THIS product rather than the next best one?" A confident,
    well-separated match and a three-way tie can share the same top-1 score, and only
    the margin tells them apart.

    It does NOT make the gate independent of LDA_TEMPERATURE — a probability margin
    still depends on T. T and the margin threshold stay a coupled pair; see the note
    on LDA_TEMPERATURE above.
    """
    if mode == 'lda':
        if index.lda is None:                        # KB too thin — degrade, don't crash
            return classify_full(vec, index, mode='knn')
        labels, proba = _lda_scores(index, vec)
        order = np.argsort(proba)[::-1]
        i     = int(order[0])
        # Single fitted class => nothing to be confused with => maximum margin.
        margin = float(proba[i] - proba[order[1]]) if len(order) > 1 else 1.0
        # str() on purpose: lda.classes_ holds np.str_, which serialises oddly in
        # shelf_api.py's JSON payloads and compares surprisingly in places.
        return str(labels[i]), 1.0, float(proba[i]), margin

    if mode == 'prototype':
        k = min(2, len(index.proto_labels))
        dists, idx = index.proto_knn.kneighbors([vec], n_neighbors=k)
        product        = index.proto_labels[idx[0][0]]
        top_similarity = 1.0 - float(dists[0][0])
        if k > 1:
            margin = top_similarity - (1.0 - float(dists[0][1]))
        else:
            margin = 1.0            # only one prototype: nothing to confuse it with
        return product, 1.0, top_similarity, float(margin)

    # kNN vote, weighted by a softmax over similarity.
    #
    # This used to weight by 1/(dist + 1e-8). That is unbounded as distance goes to
    # zero: a reference crop at distance 0 — a duplicate, or a near-duplicate export
    # of the same photo — receives weight 1e8 and outvotes the other four neighbours
    # by eight orders of magnitude. The vote gate then passes it at
    # vote_confidence ~= 1.0, so a single accidental duplicate in the KB could
    # dictate the answer while *looking* maximally confident. The knowledge base had
    # exactly that problem: crops duplicated up to 6x by the clustering runs.
    #
    # exp(sim / T) is bounded, so the nearest neighbour leads the vote without being
    # able to annihilate it. T controls how sharply; at T -> 0 this becomes 1-NN, at
    # large T it becomes an unweighted vote among the k neighbours. 0.05 is a
    # starting value chosen against the observed spread of same-class cosine
    # similarity (0.81-0.92 within a domain) — tune it with tools/gate_sweep.py
    # rather than trusting it.
    dists, idx = index.knn.kneighbors([vec])
    sims = 1.0 - dists[0]
    z    = (sims - sims.max()) / KNN_TEMPERATURE
    w    = np.exp(z)
    weight_map = {}
    for weight, i in zip(w, idx[0]):
        label = index.classes[i]
        weight_map[label] = weight_map.get(label, 0.0) + float(weight)
    total          = sum(weight_map.values())
    product        = max(weight_map, key=lambda x: weight_map[x])
    vote_confidence = weight_map[product] / total
    top_similarity  = 1.0 - float(dists[0][0])
    # A UNANIMOUS vote has no runner-up, so the runner-up share is 0 and the margin
    # is 1.0 — maximum confidence. Treating the missing second element as "margin 0"
    # instead would invert the meaning and make a margin gate reject precisely the
    # crops all k neighbours agreed on.
    shares = sorted((w / total for w in weight_map.values()), reverse=True)
    margin = float(shares[0] - (shares[1] if len(shares) > 1 else 0.0))
    return product, vote_confidence, top_similarity, margin


def top_matches(vec, index, k=5, mode=DEFAULT_MODE):
    """Return the k best-matching classes as [(label, score)], best first.

    `classify` only reveals the winner, which is not enough for OCR re-ranking: when
    the top match is wrong the right answer is almost always second or third, so
    `main.py --ocr` and `evaluate.py --ocr` re-rank this list with label text.

    Ranked by LDA posterior when the head is available, otherwise by prototype
    cosine. Either way there is exactly one row per class, so the list can't be
    filled with five crops of the same over-represented product.
    """
    k = max(1, min(k, len(index.proto_labels)))

    if mode == 'lda' and index.lda is not None:
        labels, proba = _lda_scores(index, vec)
        order = np.argsort(proba)[::-1][:k]
        return [(str(labels[i]), float(proba[i])) for i in order]

    dists, idx = index.proto_knn.kneighbors([vec], n_neighbors=k)
    return [(index.proto_labels[i], 1.0 - float(d))
            for d, i in zip(dists[0], idx[0])]


def apply_gates(product, vote_confidence, score,
                conf_threshold=CONF_THRESH, sim_threshold=SIM_THRESH,
                margin=None, margin_threshold=None):
    """Reject to 'low_confidence' when the match is too weak.

    Three gates, any one of which rejects:

      score  — floor on the absolute match quality. `sim_threshold` must be on the
               same scale as the score `classify` returned for that mode; use
               `default_threshold(mode)`. Drifts as the class count changes (see
               `classify_full`), so keep it as a loose backstop rather than the
               primary mechanism.
      margin — floor on how far the best class beat the runner-up. Pass both
               `margin` and `margin_threshold` to enable it; omitting either leaves
               it off, so existing callers are unaffected. This is the gate that
               separates "clearly this product" from "a coin-flip between two
               look-alike flavours", which the score gate cannot see: a three-way
               tie and a decisive match can share the same top-1 score.
      vote   — the original relative vote-share floor. Only bites in kNN mode; the
               other modes pass vote_confidence=1.0.

    Reminder for whoever tunes these: none of them is the open-set mechanism. An
    off-brand product that happens to look like a Sunich SKU scores high AND wins by
    a wide margin, so no threshold here will catch it — that is what the
    `unknown_beverage` / `non_beverage` buckets are for, and what an explicit
    out-of-distribution score would do properly.
    """
    if score < sim_threshold:
        return "low_confidence"
    if margin is not None and margin_threshold is not None and margin < margin_threshold:
        return "low_confidence"
    if vote_confidence < conf_threshold:
        return "low_confidence"
    return product
