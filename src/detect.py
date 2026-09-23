"""YOLO detection helpers shared by `main.py`, `shelf_api.py` and `tools/`.

Box merging and crop saving live here, not in `main.py`, so every entry point
detects and crops *exactly* the same pixels — if they drifted, the web app and
the test-set builder would be working on crops the pipeline never produces.
"""

import csv
from pathlib import Path

from PIL import Image


# ── Box merging ─────────────────────────────────────────────────────────────

def merge_adjacent_boxes(boxes, confs,
                         x_overlap_thresh=0.80, width_ratio_thresh=0.75,
                         y_gap_thresh=0.05, max_merged_aspect=6.0):
    """
    Re-join a SINGLE tall object that YOLO split into a top and bottom box.

    This is deliberately conservative so it never glues together different
    products stacked across shelf rows (a bottle over the carton below it, etc.).
    Two boxes merge only when ALL of these hold — i.e. they really look like two
    halves of one item, not two neighbours in a column:

      - Same column      : horizontal overlap >= x_overlap_thresh of the narrower box
      - Same width        : narrower/wider width >= width_ratio_thresh
                            (a split shares one width; stacked products often differ)
      - Actually touching : vertical gap <= y_gap_thresh of the shorter box's height
                            (a shelf gap between two products is larger than this)
      - Plausible result  : merged height/width <= max_merged_aspect
                            (blocks tall multi-shelf towers from forming)

    Trade-off: if a genuine split is missed, the item is simply cropped as two
    pieces that both classify the same — far less harmful than merging two
    different products into one crop. Runs iteratively until nothing more merges.
    """
    if len(boxes) == 0:
        return boxes, confs

    boxes = [list(b) for b in boxes]
    confs = list(confs)

    changed = True
    while changed:
        changed = False
        n = len(boxes)
        used = [False] * n
        new_boxes, new_confs = [], []

        for i in range(n):
            if used[i]:
                continue
            bi = boxes[i]

            for j in range(i + 1, n):
                if used[j]:
                    continue
                bj = boxes[j]

                wi, wj = bi[2] - bi[0], bj[2] - bj[0]
                min_w  = min(wi, wj)
                if min_w <= 0:
                    continue

                # Same column: strong horizontal overlap relative to narrower box
                x_inter = max(0.0, min(bi[2], bj[2]) - max(bi[0], bj[0]))
                if x_inter / min_w < x_overlap_thresh:
                    continue

                # Same object: the two boxes must be about the same width
                if min_w / max(wi, wj) < width_ratio_thresh:
                    continue

                # Touching, not merely near: gap must be tiny (or overlapping)
                # positive = gap between boxes, negative = they already overlap
                y_gap = max(bi[1], bj[1]) - min(bi[3], bj[3])
                min_h = min(bi[3] - bi[1], bj[3] - bj[1])
                if min_h <= 0 or y_gap / min_h > y_gap_thresh:
                    continue

                # Sanity: the merged box must still look like one product,
                # not a tall tower spanning multiple shelves
                m_w = max(bi[2], bj[2]) - min(bi[0], bj[0])
                m_h = max(bi[3], bj[3]) - min(bi[1], bj[1])
                if m_w <= 0 or m_h / m_w > max_merged_aspect:
                    continue

                # Merge into bounding union
                new_boxes.append([min(bi[0], bj[0]), min(bi[1], bj[1]),
                                   max(bi[2], bj[2]), max(bi[3], bj[3])])
                new_confs.append(max(confs[i], confs[j]))
                used[i] = used[j] = True
                changed = True
                break

            if not used[i]:
                new_boxes.append(bi)
                new_confs.append(confs[i])
                used[i] = True

        boxes, confs = new_boxes, new_confs

    return boxes, confs


# ── Detection + cropping ────────────────────────────────────────────────────

def detect_products(yolo, image_path, conf=0.5, iou=0.5, merge=True):
    """Run YOLO on one shelf image and return (boxes, confs) after merging.

    Unlike `main.py`'s call this never passes save=True: ultralytics writes its
    annotated image to <project>/<name>.jpg, which for `data/2025/2025.jpg`
    overwrites the input photo. The UI draws boxes in the browser instead, so the
    source image stays pristine.
    """
    result = yolo.predict(
        source=str(image_path), save=False, save_crop=False,
        conf=conf, iou=iou, verbose=False,
    )[0]
    boxes = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()

    if not merge:
        return [list(b) for b in boxes], list(confs)
    return merge_adjacent_boxes(boxes, confs)


def save_crops(image_path, boxes, out_dir, prefix, pad=2):
    """Write one jpg per box under `out_dir`.

    Returns [{'name', 'path', 'box', 'area', 'source_photo'}] in detection order.
    The 2px pad and clamping match `main.py` so every caller gets the same
    pixels the pipeline would have classified.

    `source_photo` is the stem of the shelf photo this crop was cut from. It is
    RECORDED here, at the only moment it is known for certain, rather than
    recovered later from the filename — see `write_crop_manifest`.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(image_path).convert("RGB")
    iw, ih = img.size
    photo = Path(image_path).stem

    crops = []
    for idx, box in enumerate(boxes):
        x1 = max(0,  int(box[0]) - pad)
        y1 = max(0,  int(box[1]) - pad)
        x2 = min(iw, int(box[2]) + pad)
        y2 = min(ih, int(box[3]) + pad)
        name = f"{prefix}-{idx}"
        dest = out_dir / f"{name}.jpg"
        img.crop((x1, y1, x2, y2)).save(dest)
        crops.append({
            "name": name,
            "path": str(dest),
            "box":  [x1, y1, x2, y2],
            "area": max(0, x2 - x1) * max(0, y2 - y1),
            "source_photo": photo,
        })
    img.close()
    return crops


# ── Provenance ──────────────────────────────────────────────────────────────

MANIFEST_NAME = "crops.csv"


def write_crop_manifest(dest_csv, crops):
    """Record which shelf photo each crop came from.

    Provenance drives source-photo-grouped cross-validation, which is the only
    honest generalisation estimate this project has: holding out a crop while a
    near-twin from the same photo stays in the training half measures memorisation,
    not recognition.

    It used to be *recovered* from the filename by regex (`evaluate.py:source_photo`),
    which fails in both directions on real data. Too coarse: the e-commerce names
    `0x.jpg` / `0x244.jpg` collapse to one group `'0x'` spanning six different SKUs,
    and stripping the `_front`/`_back` view suffix merges `sunich_1L_orange` with
    `sunich_750ml_orange`. Too fine: `data/sample/t3.jpg` yields group `t3` while its
    own crop `t3 (Edited).jpg` yields `t3 (Edited)`, so a photo that DID feed the
    knowledge base looks held-out. 21 of the KB's inferred groups spanned more than
    one class label.

    Writing it down at crop time removes the guessing. The regex stays only as a
    fallback for crops that predate this manifest.
    """
    dest_csv = Path(dest_csv)
    dest_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["crop", "source_photo", "x1", "y1", "x2", "y2", "area"])
        for c in crops:
            w.writerow([c["name"], c["source_photo"], *c["box"], c["area"]])
    return dest_csv


def read_crop_manifest(manifest_csv):
    """Return {crop_name: source_photo} from a manifest, or {} if absent."""
    manifest_csv = Path(manifest_csv)
    if not manifest_csv.is_file():
        return {}
    with open(manifest_csv, newline="", encoding="utf-8") as f:
        return {row["crop"]: row["source_photo"] for row in csv.DictReader(f)
                if row.get("crop")}
