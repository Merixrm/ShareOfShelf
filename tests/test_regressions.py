"""Regression tests for the failures that actually happened in this project.

Each test corresponds to a real bug that shipped, not a hypothetical one. They use
synthetic embeddings so the suite runs in seconds with no model download and no
knowledge base — the point is to protect the LOGIC, which is where every one of
these went wrong.

Run:
    python tests/test_regressions.py       # standalone, no pytest needed
    python -m pytest tests/                # if pytest is installed
"""

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classifier import (                                    # noqa: E402
    KBIndex, apply_gates, assert_flat_class_tree, classify, classify_full,
    default_margin, default_threshold, is_non_beverage,
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _unit(v):
    return v / np.linalg.norm(v)


def _toy_index(seed=0, per_class=5, dim=16):
    rng = np.random.default_rng(seed)
    centers = {c: _unit(rng.normal(size=dim)) for c in ("a", "b", "c")}
    classes, embs = [], []
    for lab, c in centers.items():
        for _ in range(per_class):
            classes.append(lab)
            embs.append(_unit(c + 0.05 * rng.normal(size=dim)))
    return KBIndex(classes, np.asarray(embs, dtype=np.float32)), centers


# ── the bugs ────────────────────────────────────────────────────────────────

def test_depth_guard_rejects_nested_output():
    """src/cluster.py wrote runs INTO the KB; the loader read them as classes.

    Five runs put 255 images under `unknown_beverage/clustering_results/run_*/`,
    which `load_kb_embeddings` registered as the classes `cluster_0`..`cluster_4`
    and `noise` — 38% of the KB, with `noise` the largest class in it.
    """
    root = "data/kb"
    good = [f"{root}/sunich_1L_apple/x.jpg", f"{root}/non_beverage/y.jpg"]
    assert_flat_class_tree(root, good, what="knowledge base")   # must not raise

    bad = good + [f"{root}/unknown_beverage/clustering_results/run_1/cluster_0/z.jpg"]
    try:
        assert_flat_class_tree(root, bad, what="knowledge base")
    except ValueError as e:
        assert "cluster_0" in str(e), "error must name the offending directory"
    else:
        raise AssertionError("depth guard did not fire on a nested output dir")


def test_classify_stays_a_three_tuple():
    """`classify` is the public 3-value API; `classify_full` adds the margin.

    If `classify` ever starts returning the 4-tuple, any caller that unpacks
    three values breaks at runtime, not at import.
    """
    index, centers = _toy_index()
    q = _unit(centers["a"] + 0.01).astype(np.float32)
    for mode in ("lda", "knn", "prototype"):
        three = classify(q, index, mode=mode)
        four  = classify_full(q, index, mode=mode)
        assert len(three) == 3, f"{mode}: classify must return 3 values"
        assert len(four) == 4, f"{mode}: classify_full must return 4 values"
        assert three == four[:3], f"{mode}: classify must be classify_full[:3]"


def test_unanimous_vote_is_not_scored_as_uncertain():
    """A margin bug I introduced: unanimous kNN vote produced margin 0.0.

    With only one label in the weight map there is no runner-up, and taking the
    missing second element as 0 margin INVERTS the meaning — a margin gate would
    then reject exactly the crops every neighbour agreed on.
    """
    index, centers = _toy_index()
    q = _unit(centers["a"] + 0.01).astype(np.float32)
    for mode in ("lda", "knn", "prototype"):
        _lab, _vc, _s, margin = classify_full(q, index, mode=mode)
        assert margin > 0.3, (
            f"{mode}: a confident, well-separated match must not look ambiguous "
            f"(margin={margin:.3f})"
        )


def test_margin_collapses_on_a_genuine_tie():
    """The margin has to actually detect ambiguity, not just be large always."""
    index, centers = _toy_index()
    tie = _unit(centers["a"] + centers["b"]).astype(np.float32)
    for mode in ("lda", "knn", "prototype"):
        _lab, _vc, _s, margin = classify_full(tie, index, mode=mode)
        assert margin < 0.35, (
            f"{mode}: a query midway between two classes must show a small margin "
            f"(margin={margin:.3f})"
        )


def test_duplicate_reference_cannot_dominate_knn_vote():
    """kNN weighted by 1/(dist+1e-8) gave a distance-0 neighbour weight 1e8.

    One duplicate then decided the answer while reporting vote_confidence ~= 1.0.
    The KB had crops duplicated up to 6x by the clustering runs, so this was live.
    """
    index, centers = _toy_index()
    q = _unit(centers["a"] + 0.01).astype(np.float32)

    # Same vector as the query, but labelled 'b'.
    classes = list(index.classes) + ["b"]
    embs    = list(index.embeddings) + [q]
    poisoned = KBIndex(classes, np.asarray(embs, dtype=np.float32))

    label, vote_conf, _s, _m = classify_full(q, poisoned, mode="knn")
    assert label == "a", (
        f"a single mislabelled duplicate hijacked the vote (got {label})"
    )
    assert vote_conf < 0.99, (
        f"vote_confidence {vote_conf:.3f} implies one neighbour swamped the rest"
    )


def test_margin_gate_wiring():
    """apply_gates must ignore the margin unless BOTH margin and threshold given."""
    assert apply_gates("a", 1.0, 0.9, 0.4, 0.3) == "a"
    assert apply_gates("a", 1.0, 0.9, 0.4, 0.3, margin=0.01) == "a"
    assert apply_gates("a", 1.0, 0.9, 0.4, 0.3, margin_threshold=0.2) == "a"
    assert apply_gates("a", 1.0, 0.9, 0.4, 0.3,
                       margin=0.01, margin_threshold=0.2) == "low_confidence"
    assert apply_gates("a", 1.0, 0.9, 0.4, 0.3,
                       margin=0.50, margin_threshold=0.2) == "a"


def test_score_gate_still_rejects():
    assert apply_gates("a", 1.0, 0.10, 0.4, 0.3) == "low_confidence"


def test_defaults_are_per_mode():
    """A single 0.60 floor across modes applies a near-meaningless gate to lda,
    whose score is a posterior rather than a cosine similarity."""
    assert default_threshold("lda") != default_threshold("prototype")
    assert default_margin("lda") is not None
    # Unswept modes must stay disabled rather than inherit an unmeasured number.
    assert default_margin("knn") is None
    assert default_margin("prototype") is None


def test_non_beverage_prefix():
    assert is_non_beverage("non_beverage")
    assert is_non_beverage("non_beverage_snack")
    assert not is_non_beverage("unknown_beverage")
    assert not is_non_beverage("sunich_1L_apple")


def test_provenance_roundtrip():
    """Recorded provenance must beat filename inference, and survive a reread."""
    from src.provenance import load_provenance, provenance_path, write_all

    with tempfile.TemporaryDirectory() as tmp:
        kb = Path(tmp) / "knowledge_base" / "crops" / "object"
        kb.mkdir(parents=True)
        mapping = {"sunich_1L_apple/2025-12.jpg": "2025",
                   "unknown_beverage/t3 (Edited).jpg": "t3"}
        write_all(str(kb), mapping)
        assert provenance_path(str(kb)).is_file()
        assert load_provenance(str(kb)) == mapping

        # write_all overwrites, so a hand-corrected group does not leave the
        # superseded row behind for load_provenance to pick between.
        write_all(str(kb), {"sunich_1L_apple/2025-12.jpg": "corrected"})
        assert load_provenance(str(kb)) == {"sunich_1L_apple/2025-12.jpg": "corrected"}


def test_inference_groups_a_photo_with_its_own_crop():
    """`t3.jpg` grouped as 't3' while its crop `t3 (Edited).jpg' grouped as
    't3 (Edited)', so a photo that HAD fed the KB looked held-out — which would
    have put it straight into a supposedly independent test set."""
    from src.provenance import infer_source_photo

    known = {"t3", "2025"}
    assert infer_source_photo("data/sample/t3.jpg", known_photos=known) == "t3"
    assert infer_source_photo("kb/unknown_beverage/t3 (Edited).jpg",
                              known_photos=known) == "t3"
    assert infer_source_photo("kb/unknown_beverage/t3 (Edited) (Edited 2).jpg",
                              known_photos=known) == "t3"


def test_inference_does_not_merge_distinct_products():
    """Stripping trailing digits collapsed `0x.jpg` and `0x244.jpg` into one group
    that spanned six different SKUs."""
    from src.provenance import infer_source_photo

    known = set()
    a = infer_source_photo("kb/sunich_1L_cherry/0x.jpg", known_photos=known)
    b = infer_source_photo("kb/sunich_750ml_mango/0x244.jpg", known_photos=known)
    assert a != b, "unrelated e-commerce files must not share a CV group"

    # And two flavours must not merge just because they share a view suffix.
    c = infer_source_photo("kb/sunich_1L_orange/orange_front.jpg", known_photos=known)
    d = infer_source_photo("kb/sunich_750ml_orange/orange_front.jpg", known_photos=known)
    assert c != d, "different SKUs must not share a CV group"


def test_open_set_metrics_do_not_punish_correct_rejection():
    """Plain accuracy scored a correctly-rejected unknown as an error, so the
    threshold sweep could only ever be maximised at 0."""
    from evaluate import open_set_metrics

    truths = ["sunich_1L_apple", "unknown_beverage", "non_beverage"]
    preds  = ["sunich_1L_apple", "low_confidence", "non_beverage"]
    m = open_set_metrics(preds, truths)
    assert m["sku_accuracy"] == 1.0
    assert m["neg_handled"] == 1.0, "rejecting an unknown is correct handling"
    assert m["false_accepts"] == 0

    # Naming a negative as a product IS the damaging error.
    m2 = open_set_metrics(["sunich_1L_apple", "sunich_1L_mango", "non_beverage"],
                          truths)
    assert m2["false_accepts"] == 1


# ── runner ──────────────────────────────────────────────────────────────────

def main():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:
            failed.append((name, e))
            print(f"  FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
