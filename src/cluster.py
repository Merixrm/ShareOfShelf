"""
Unknown-beverage clustering.

Architecture
------------

The clustering pipeline is completely independent from main.py.

Source images:
    data/knowledge_base/crops/object/unknown_beverage/

Persistent embedding pool:
    data/clustering/unknown_beverage_pool/

Visual clustering results (OUTSIDE the knowledge base — see CLUSTER_RESULTS_DIR):
    data/clustering/results/
        run_YYYY-MM-DD_HH-MM-SS/
            cluster_0/
            cluster_1/
            ...
            noise/

Workflow
--------

unknown_beverage images
        |
        v
Check persistent embedding pool
        |
        +---- already embedded ----> reuse embedding
        |
        +---- new image -----------> DINOv2 -> save embedding
        |
        v
Persistent embedding pool
        |
        v
DBSCAN
        |
        v
Copy images into cluster folders

Original images are NEVER moved or deleted.
"""

"""
Usage:
python -m src.cluster
"""

from pathlib import Path
from datetime import datetime
import os
import pickle
import shutil

import numpy as np
from PIL import Image
from sklearn.cluster import DBSCAN

from src.img2vec_dino2 import Img2VecDino2


# =============================================================================
# Configuration
# =============================================================================

# -------------------------------------------------------------------------
# Source directory
# -------------------------------------------------------------------------
#
# This is the real unknown_beverage folder in the knowledge base.
#
UNKNOWN_BEVERAGE_DIR = (
    Path("data")
    / "knowledge_base"
    / "crops"
    / "object"
    / "unknown_beverage"
)


# -------------------------------------------------------------------------
# Persistent embedding pool
# -------------------------------------------------------------------------
#
# The pool stores:
#
#     image filename
#     embedding
#
# Embeddings are calculated only once for each image.
#
POOL_DIR = (
    Path("data")
    / "clustering"
    / "unknown_beverage_pool"
)

POOL_FILE = POOL_DIR / "embeddings.pkl"


# -------------------------------------------------------------------------
# Visual clustering results
# -------------------------------------------------------------------------
#
# Every execution gets its own timestamped directory.
#
# CRITICAL: this MUST stay outside data/knowledge_base/ and data/test_set/.
#
# It used to live at UNKNOWN_BEVERAGE_DIR / "clustering_results", i.e. INSIDE
# the knowledge base. `load_kb_embeddings` globs "{kb_path}/**/*.jpg"
# recursively and takes the class label from the parent folder name, so every
# run of this script silently added `cluster_0`, `cluster_1`, ... and `noise`
# to the knowledge base as if they were real product classes. Five runs left
# 255 phantom images in a 674-image KB — 38% of it — with `noise` the single
# largest class. `classify()` could return "noise" as a product and it reached
# share_of_shelf.csv as a beverage with a market share, LDA fitted six garbage
# classes that were duplicate splits of the real unknown_beverage pool
# (corrupting the shared pooled covariance and therefore every decision
# boundary), and individual crops appeared up to 6x, dominating kNN votes.
# Three more runs did the same to data/test_set/, which left 269 of 315 test
# crops byte-identical to KB images and made evaluate.py refuse to run.
#
# `_load_images` below is already deliberately non-recursive so clustering
# never re-reads its own output. That defended this script against itself but
# not the KB loader against this script — hence the hard separation here, plus
# the depth guard in src/classifier.py.
CLUSTER_RESULTS_DIR = (
    Path("data")
    / "clustering"
    / "results"
)


# -------------------------------------------------------------------------
# DBSCAN configuration
# -------------------------------------------------------------------------

# Minimum number of samples required before clustering starts.
MIN_SAMPLES_TO_CLUSTER = 40

# DBSCAN epsilon in cosine-distance space.
#
# cosine distance = 1 - cosine similarity
#
# eps=0.20 corresponds to cosine similarity >= 0.80.
# (The comment here used to claim 0.15 / 0.85 while the code said 0.20 — the
# two had drifted apart on the single most important hyperparameter in the file.)
#
# UNCALIBRATED — do not trust clusters produced at this value yet. src/classifier.py
# measured the 750ml prototypes sitting at mean cosine 0.909 from EACH OTHER, i.e.
# a cosine distance of 0.091 between DIFFERENT products. This eps is more than
# double that, so it cannot separate SKUs that plain cosine already collapses, and
# DBSCAN's density-chaining makes it worse: one visually intermediate crop welds
# two products into a single cluster. The last run put 100 of 255 crops in `noise`,
# which is the algorithm reporting that a single global density threshold does not
# fit data where a common SKU has 30 crops and a rare one has 3.
#
# Calibrate before relying on this: build a k-distance plot (sorted distance to the
# min_samples-th neighbour) and look for a knee, and score candidate values against
# a hand-labelled ground truth with ARI/purity. If there is no clean knee, the
# finding is that DBSCAN is the wrong tool here and the shortlist is HDBSCAN
# (variable density, no eps) or average-linkage agglomerative (resists chaining).
DBSCAN_EPS = 0.15

# Minimum number of samples required to form a dense region.
DBSCAN_MIN_SAMPLES = 2


# Supported image formats.
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


# =============================================================================
# Source image loading
# =============================================================================

def _load_images():
    """
    Load only image files directly inside UNKNOWN_BEVERAGE_DIR.

    IMPORTANT
    ---------
    This function does NOT recursively search directories.

    Therefore images inside:

        clustering_results/
        cluster_0/
        cluster_1/
        noise/

    are ignored.

    Returns:
        list[Path]
    """

    if not UNKNOWN_BEVERAGE_DIR.exists():
        return []

    images = sorted(
        path
        for path in UNKNOWN_BEVERAGE_DIR.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
        )
    )

    return images


# =============================================================================
# Persistent embedding pool
# =============================================================================

def _ensure_pool():
    """
    Create the persistent embedding pool directory if necessary.
    """

    POOL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# Bumped whenever the on-disk pool layout changes; an older pool is discarded
# rather than misread.
POOL_FORMAT = 2


def _model_key():
    """Identity of the embedder whose vectors the pool holds.

    Class name alone is NOT enough. `Img2VecDino2.EMBED_VERSION` went to 2 when
    preprocessing changed from resize+center-crop to letterboxing, which produces
    completely different vectors under the same class name. A pool keyed only on
    the filename would mix v1 and v2 vectors in one matrix, and DBSCAN would then
    "discover" that the dominant structure in the data is which version of the
    preprocessing code happened to run. Those clusters would look plausible and
    mean nothing. `src/classifier.py` already keys its KB cache this way.
    """
    return (Img2VecDino2.__name__,
            getattr(Img2VecDino2, "EMBED_VERSION", 1))


def _pool_key(image_path):
    """Pool key: path relative to the source dir, so it survives the tree moving."""
    return os.path.relpath(
        image_path,
        UNKNOWN_BEVERAGE_DIR,
    ).replace("\\", "/")


def _load_pool():
    """
    Load the persistent embedding pool, discarding it when it is stale.

    Pool format:

        {
            "format":  POOL_FORMAT,
            "model":   ("Img2VecDino2", EMBED_VERSION),
            "entries": {
                "<path relative to source dir>": {
                    "size":      int,          # bytes
                    "embedding": numpy_array
                }
            }
        }

    `size` mirrors `src/classifier.py:_cache_signature`, for the reason recorded
    there: a name-only key silently serves a stale embedding when an image is
    replaced in place. That is invisible on inspection — the file on disk looks
    right — and it quietly corrupts every cluster the image takes part in.

    Returns:
        dict of entries (empty when there is no usable pool)
    """

    if not POOL_FILE.exists():
        return {}

    with open(
        POOL_FILE,
        "rb",
    ) as f:
        pool = pickle.load(f)

    if not isinstance(pool, dict):
        raise ValueError(
            f"Invalid embedding pool format: {POOL_FILE}"
        )

    if pool.get("format") != POOL_FORMAT:
        print(
            "\n  Embedding pool uses an old layout — rebuilding it from scratch."
        )
        return {}

    if pool.get("model") != _model_key():
        print(
            f"\n  Embedding pool was built by {pool.get('model')}, "
            f"now running {_model_key()} — rebuilding it from scratch."
        )
        print(
            "  (Mixing embedding versions would cluster by preprocessing version.)"
        )
        return {}

    return pool.get("entries", {})


def _save_pool(entries):
    """
    Save the persistent embedding pool, stamped with the layout and embedder
    version so a later run can tell whether these vectors are still comparable.
    """

    _ensure_pool()

    pool = {
        "format":  POOL_FORMAT,
        "model":   _model_key(),
        "entries": entries,
    }

    with open(
        POOL_FILE,
        "wb",
    ) as f:
        pickle.dump(
            pool,
            f,
        )


# =============================================================================
# Embedding extraction
# =============================================================================

def _extract_new_embeddings(
    images,
    pool,
):
    """
    Extract DINOv2 embeddings only for images that are not already
    present in the persistent pool.

    Existing embeddings are reused.

    Returns:
        updated pool
    """

    # Re-embed when the key is absent OR the file changed size, so replacing an
    # image in place can no longer serve the previous image's vector forever.
    new_images = [
        image_path
        for image_path in images
        if pool.get(_pool_key(image_path), {}).get("size")
        != image_path.stat().st_size
    ]

    if not new_images:

        print(
            "\n  No new images found."
        )

        print(
            "  All embeddings already exist in the pool."
        )

        return pool

    print(
        f"\n  New images requiring embeddings: "
        f"{len(new_images)}"
    )

    # Load DINOv2 only when new images actually need embedding.
    img2vec = Img2VecDino2()

    for image_path in new_images:

        print(
            f"  Embedding: {image_path.name}"
        )

        try:

            with Image.open(
                image_path
            ) as img:

                img = img.convert(
                    "RGB"
                )

                embedding = img2vec.getVec(
                    img
                )

        except Exception as e:

            print(
                f"    ERROR embedding "
                f"{image_path.name}: "
                f"{type(e).__name__}: {e}"
            )

            continue

        embedding = np.asarray(
            embedding,
            dtype=np.float32,
        )

        if embedding.ndim != 1:

            raise ValueError(
                f"Expected a 1-D embedding for "
                f"{image_path.name}, "
                f"got shape {embedding.shape}"
            )

        pool[_pool_key(image_path)] = {
            "size":      image_path.stat().st_size,
            "embedding": embedding,
        }

    _save_pool(pool)

    return pool


# =============================================================================
# Build embedding matrix
# =============================================================================

def _build_embedding_matrix(
    images,
    pool,
):
    """
    Build an embedding matrix using the persistent pool.

    The order of rows is exactly the same as the order of `images`.

    Returns:
        numpy array with shape (N, D)
    """

    embeddings = []

    valid_images = []

    for image_path in images:

        sample = pool.get(
            _pool_key(image_path)
        )

        if sample is None:

            print(
                f"  WARNING: No embedding "
                f"found for {image_path.name}. "
                f"Skipping."
            )

            continue

        embedding = np.asarray(
            sample["embedding"],
            dtype=np.float32,
        )

        if embedding.ndim != 1:

            raise ValueError(
                f"Invalid embedding shape for "
                f"{image_path.name}: "
                f"{embedding.shape}"
            )

        embeddings.append(
            embedding
        )

        valid_images.append(
            image_path
        )

    if not embeddings:

        return (
            np.empty(
                (0, 0),
                dtype=np.float32,
            ),
            [],
        )

    return (
        np.asarray(
            embeddings,
            dtype=np.float32,
        ),
        valid_images,
    )


# =============================================================================
# L2 normalization
# =============================================================================

def _normalize_embeddings(
    embeddings,
):
    """
    L2-normalize embeddings.

    This makes the representation consistent with the cosine
    distance used by DBSCAN.
    """

    if embeddings.size == 0:
        return embeddings

    norms = np.linalg.norm(
        embeddings,
        axis=1,
        keepdims=True,
    )

    normalized = np.zeros_like(
        embeddings
    )

    nonzero = (
        norms[:, 0] > 0
    )

    normalized[nonzero] = (
        embeddings[nonzero]
        / norms[nonzero]
    )

    return normalized


# =============================================================================
# DBSCAN
# =============================================================================

def _run_dbscan(
    embeddings,
    eps=DBSCAN_EPS,
    min_samples=DBSCAN_MIN_SAMPLES,
):
    """
    Run DBSCAN using cosine distance.

    Returns:
        numpy array of cluster labels.
    """

    clustering = DBSCAN(
        eps=eps,
        min_samples=min_samples,
        metric="cosine",
        algorithm="brute",
    )

    labels = clustering.fit_predict(
        embeddings
    )

    return labels


# =============================================================================
# Save visual clustering results
# =============================================================================

def _create_run_directory():
    """
    Create a unique directory for the current clustering run.

    Example:

        clustering_results/
            run_2026-08-11_14-30-52/
    """

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    run_dir = (
        CLUSTER_RESULTS_DIR
        / f"run_{timestamp}"
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    return run_dir


def _save_visual_results(
    images,
    labels,
):
    """
    Copy images into cluster folders.

    Original images are NEVER moved.

    Example:

        clustering_results/
            run_2026-08-11_14-30-52/
                cluster_0/
                cluster_1/
                noise/
    """

    run_dir = _create_run_directory()

    for image_path, label in zip(
        images,
        labels,
    ):

        if label == -1:

            destination_dir = (
                run_dir
                / "noise"
            )

        else:

            destination_dir = (
                run_dir
                / f"cluster_{int(label)}"
            )

        destination_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = (
            destination_dir
            / image_path.name
        )

        # IMPORTANT:
        # COPY only.
        #
        # The original image inside
        # unknown_beverage remains untouched.
        shutil.copy2(
            image_path,
            destination,
        )

    return run_dir


# =============================================================================
# Save CSV
# =============================================================================

def _save_csv(
    run_dir,
    images,
    labels,
):
    """
    Save cluster assignments for the current run.
    """

    csv_file = (
        run_dir
        / "clusters.csv"
    )

    with open(
        csv_file,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "crop,cluster_id\n"
        )

        for image_path, label in zip(
            images,
            labels,
        ):

            f.write(
                f"{image_path.name},"
                f"{int(label)}\n"
            )

    return csv_file


# =============================================================================
# Reporting
# =============================================================================

def _print_result(
    images,
    labels,
    run_dir,
):
    """
    Print a compact clustering summary.
    """

    n_samples = len(
        images
    )

    unique_labels = set(
        labels
    )

    cluster_labels = sorted(
        label
        for label in unique_labels
        if label != -1
    )

    n_clusters = len(
        cluster_labels
    )

    n_noise = int(
        np.sum(
            labels == -1
        )
    )

    print(
        "\n" + "─" * 60
    )

    print(
        "UNKNOWN BEVERAGE CLUSTERING RESULT"
    )

    print(
        "─" * 60
    )

    print(
        f"  Samples:   {n_samples}"
    )

    print(
        f"  Clusters:  {n_clusters}"
    )

    print(
        f"  Noise:     {n_noise}"
    )

    if n_clusters > 0:

        print(
            "\n  Cluster sizes:"
        )

        for cluster_id in cluster_labels:

            size = int(
                np.sum(
                    labels
                    == cluster_id
                )
            )

            print(
                f"    cluster_{cluster_id}: "
                f"{size} crops"
            )

    if n_noise > 0:

        print(
            f"    noise: "
            f"{n_noise} crops"
        )

    print(
        "\n  Visual results:"
    )

    print(
        f"    {run_dir}"
    )

    print(
        "─" * 60
    )


# =============================================================================
# Main clustering pipeline
# =============================================================================

def cluster_unknown_beverages(
    eps=DBSCAN_EPS,
    min_samples=DBSCAN_MIN_SAMPLES,
):
    """
    Complete unknown-beverage clustering pipeline.

    Steps:

        1. Read unknown_beverage images.
        2. Check persistent embedding pool.
        3. Embed only new images.
        4. Build embedding matrix.
        5. L2-normalize embeddings.
        6. Run DBSCAN.
        7. Copy images into cluster folders.
        8. Save CSV.
    """

    print(
        "\n" + "─" * 60
    )

    print(
        "UNKNOWN BEVERAGE CLUSTERING"
    )

    print(
        "─" * 60
    )

    print(
        "  Source:"
    )

    print(
        f"    {UNKNOWN_BEVERAGE_DIR}"
    )

    # -------------------------------------------------------------------------
    # Load source images
    # -------------------------------------------------------------------------

    images = _load_images()

    n_samples = len(
        images
    )

    print(
        f"\n  Samples: {n_samples}"
    )

    if n_samples < MIN_SAMPLES_TO_CLUSTER:

        print(
            f"\n  Need at least "
            f"{MIN_SAMPLES_TO_CLUSTER} "
            f"images to start clustering."
        )

        print(
            "─" * 60
        )

        return None

    # -------------------------------------------------------------------------
    # Load persistent pool
    # -------------------------------------------------------------------------

    pool = _load_pool()

    print(
        f"  Pool entries before update: "
        f"{len(pool)}"
    )

    # -------------------------------------------------------------------------
    # Embed only new images
    # -------------------------------------------------------------------------

    pool = _extract_new_embeddings(
        images,
        pool,
    )

    print(
        f"  Pool entries after update: "
        f"{len(pool)}"
    )

    # -------------------------------------------------------------------------
    # Build embedding matrix
    # -------------------------------------------------------------------------

    embeddings, valid_images = (
        _build_embedding_matrix(
            images,
            pool,
        )
    )

    if len(valid_images) < MIN_SAMPLES_TO_CLUSTER:

        print(
            f"\n  Only "
            f"{len(valid_images)} "
            f"valid embeddings available."
        )

        print(
            "  Clustering not started."
        )

        print(
            "─" * 60
        )

        return None

    # -------------------------------------------------------------------------
    # Normalize
    # -------------------------------------------------------------------------

    normalized = (
        _normalize_embeddings(
            embeddings
        )
    )

    # -------------------------------------------------------------------------
    # DBSCAN
    # -------------------------------------------------------------------------

    print(
        "\n  Running DBSCAN..."
    )

    print(
        f"    eps:         {eps}"
    )

    print(
        f"    min_samples: {min_samples}"
    )

    labels = _run_dbscan(
        normalized,
        eps=eps,
        min_samples=min_samples,
    )

    # -------------------------------------------------------------------------
    # Save visual results
    # -------------------------------------------------------------------------

    run_dir = _save_visual_results(
        valid_images,
        labels,
    )

    # -------------------------------------------------------------------------
    # Save CSV
    # -------------------------------------------------------------------------

    csv_file = _save_csv(
        run_dir,
        valid_images,
        labels,
    )

    # -------------------------------------------------------------------------
    # Reporting
    # -------------------------------------------------------------------------

    _print_result(
        valid_images,
        labels,
        run_dir,
    )

    print(
        "\n  CSV:"
    )

    print(
        f"    {csv_file}"
    )

    return {
        "n_samples": len(valid_images),
        "n_clusters": len(
            set(labels)
            - {-1}
        ),
        "n_noise": int(
            np.sum(
                labels == -1
            )
        ),
        "labels": labels,
        "images": valid_images,
        "run_dir": run_dir,
        "csv_file": csv_file,
    }


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":

    cluster_unknown_beverages()