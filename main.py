import glob
import shutil
import argparse
from collections import Counter, defaultdict
from pathlib import Path
from PIL import Image
from ultralytics import YOLO

from src.img2vec_dino2 import Img2VecDino2
from src.img2vec_resnet18 import Img2VecResnet18
from src.detect import (
    merge_adjacent_boxes, save_crops, write_crop_manifest, MANIFEST_NAME,
)
from src.classifier import (
    load_kb_embeddings, KBIndex, classify_full, apply_gates, is_non_beverage,
    top_matches,
    CONF_THRESH, MATCH_MODES, DEFAULT_MODE, default_threshold, default_margin,
    UNKNOWN_LABELS,
)


MODEL_PATH  = 'models/best.pt'
DATA_PATH   = 'data'
KB_PATH     = 'data/knowledge_base/crops/object'


# Box merging and crop saving live in src/detect.py so shelf_api.py and
# tools/build_test_set.py detect and crop exactly what this pipeline does.


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Shelf product identifier')
    parser.add_argument('--input',          required=True,
                        help='Path to shelf image')
    parser.add_argument('--model',          default='dino2',
                        choices=['dino2', 'resnet18'],
                        help='Embedding model (default: dino2)')
    parser.add_argument('--match-mode',     default=DEFAULT_MODE,
                        choices=list(MATCH_MODES),
                        help='lda = supervised head over the KB embeddings, separates '
                             'look-alike flavours (default); knn = weighted vote over the '
                             'k nearest reference crops; prototype = one centroid per class '
                             '(collapses near-identical SKUs — kept for comparison)')
    parser.add_argument('--conf-threshold', type=float, default=CONF_THRESH,
                        help=f'Min vote-share to accept, knn mode only (default: {CONF_THRESH})')
    parser.add_argument('--margin-threshold', type=float, default=None,
                        help='Min gap between the best class and the runner-up. This is '
                             'the gate that catches a coin-flip between two look-alike '
                             'flavours, which the score gate cannot see — a three-way tie '
                             'and a decisive match can share the same top-1 score. '
                             'Measured out-of-fold on the KB: 0.05 (the default) takes '
                             'false accepts from 5 to 1 and 0.10 takes them to 0, at 11 '
                             'and 18 lost facings respectively. A false accept is an '
                             'off-brand crop given a specific SKU name, which inflates '
                             'that brand\'s share of shelf. Use 0 to disable.')
    parser.add_argument('--sim-threshold',  type=float, default=None,
                        help='Min score to accept. Scale depends on --match-mode: cosine '
                             'similarity for prototype/knn, posterior probability for lda. '
                             f'Defaults per mode: {default_threshold("prototype"):.2f} / '
                             f'{default_threshold("knn"):.2f} / {default_threshold("lda"):.2f}')
    parser.add_argument('--tta',            action=argparse.BooleanOptionalAction, default=True,
                        help='Test-time augmentation: embed 5 augmented views per query '
                             'crop and average. Costs 5x the embedding time per crop. '
                             'NOTE this makes queries asymmetric with the knowledge base, '
                             'which is embedded single-view — an asymmetry that grouped CV '
                             'structurally CANNOT measure, because there the query and the '
                             'reference are the same crops. The old "+2.2 points under '
                             'source-photo-grouped CV" claim here was not measurable by '
                             'that path (it had no TTA at all) and came from the test set, '
                             'which was 269/315 leaked. Re-validate on the rebuilt test '
                             'set before trusting the default either way.')
    parser.add_argument('--no-merge',       action='store_true',
                        help='Disable box merging entirely (merging is now conservative and '
                             'safe on multi-row shelves, so this is rarely needed)')
    parser.add_argument('--ocr',            action='store_true',
                        help='Read label text with OCR and use it to break ties between '
                             'look-alike flavours. Only consulted on crops the embedding '
                             'head is undecided about, because it costs seconds per crop. '
                             'NOTE: needs a high-resolution crop to work — see README.md for '
                             'the measured width threshold before relying on this.')
    parser.add_argument('--ocr-margin',     type=float, default=0.35,
                        help='Consult OCR when the top-2 probability gap is below this '
                             '(default: 0.35). Use 1.0 to consult on every crop.')
    parser.add_argument('--ocr-verify-brand', action=argparse.BooleanOptionalAction,
                        default=True,
                        help='With --ocr, also read every crop the head is about to name '
                             'as a specific product, not just the close calls. Catches the '
                             'competitor-pack error the margin gate cannot see: a rival '
                             'carton with the same fruit graphic scores 99%% on a Sunich '
                             'SKU, nowhere near the margin. Costs ~8s per named crop; use '
                             '--no-ocr-verify-brand for the old margin-only behaviour.')
    parser.add_argument('--ocr-alpha',      type=float, default=1.5,
                        help='Strength of the OCR bonus during fusion (default: 1.5)')
    parser.add_argument('--llm-fallback',   action='store_true',
                        help='Send crops the local matcher rejects (low_confidence) to an '
                             'OpenAI vision model as a second chance. Needs OPENAI_API_KEY. '
                             'Optional — without it the pipeline is unchanged.')
    parser.add_argument('--llm-model',      default=None,
                        help='OpenAI model for --llm-fallback (default: $OPENAI_MODEL or gpt-4.1)')
    args = parser.parse_args()
    if args.sim_threshold is None:
        args.sim_threshold = default_threshold(args.match_mode)
    if args.margin_threshold is None:
        args.margin_threshold = default_margin(args.match_mode)
    elif args.margin_threshold <= 0:
        args.margin_threshold = None          # explicit opt-out

    PATH    = Path(args.input).stem
    out_dir = Path(DATA_PATH) / PATH

    # ── Clear stale outputs so re-runs start clean ──
    # The WHOLE crops/ tree goes, not just crops/object. Each run files crop N
    # into crops/<whatever it predicted this time>/, so clearing only the
    # staging dir left every previous run's verdict on disk beside the new one:
    # data/2025 accumulated 39 crop names sitting in two folders at once, some
    # under classes this MVP no longer has (2025-11.jpg was filed as both
    # icymonkey_300ml_watermelon and sunich_1L_peach). That is actively
    # dangerous, because README "Extending the knowledge base" tells you to grow the knowledge base
    # from crops/low_confidence/ — so a crop that a later run classified
    # correctly still sits in low_confidence, and labelling from a stale folder
    # feeds a wrong reference image straight into the KB.
    for fname in ["predictions.txt", "predictions.csv", "share_of_shelf.csv"]:
        (out_dir / fname).unlink(missing_ok=True)
    crops_root = out_dir / "crops"
    if crops_root.exists():
        shutil.rmtree(crops_root)
    crops_object = crops_root / "object"

    # ── Stage 1: YOLO detection ──────────────────────────────────────────────
    print(f"\n[1/3] YOLO detection on {args.input}")
    yolo = YOLO(MODEL_PATH)
    # save=False on purpose. With save=True, ultralytics writes its annotated
    # render to <project>/<name>/<source filename> — which for the documented
    # layout `data/<name>/<name>.jpg` IS the input photo, so every run destroyed
    # its own source. We save the render ourselves, under a name that can't
    # collide with the original.
    results = yolo.predict(
        source=args.input,
        save=False,
        save_crop=False,  # we save crops ourselves after merging
        conf=0.5,
        iou=0.5,
    )

    # Extract raw boxes and merge vertically adjacent detections
    result     = results[0]
    raw_boxes  = result.boxes.xyxy.cpu().numpy()   # (N, 4) x1 y1 x2 y2
    raw_confs  = result.boxes.conf.cpu().numpy()   # (N,)

    out_dir.mkdir(parents=True, exist_ok=True)
    annotated_path = out_dir / f"{PATH}_annotated.jpg"
    Image.fromarray(result.plot()[:, :, ::-1]).save(annotated_path)  # plot() is BGR
    print(f"  Annotated render: {annotated_path}")

    if args.no_merge:
        merged_boxes, merged_confs = list(raw_boxes), list(raw_confs)
        print(f"  {len(raw_boxes)} detections (merging disabled)")
    else:
        merged_boxes, merged_confs = merge_adjacent_boxes(raw_boxes, raw_confs)
        print(f"  {len(raw_boxes)} raw detections -> {len(merged_boxes)} after merging")

    # Save merged crops to crops/object/ through the SHARED helper. This loop used
    # to be duplicated here — same padding, same clamping, same naming — which is
    # exactly the drift src/detect.py exists to prevent: shelf_api.py already
    # calls save_crops(), so any future tweak to one copy would make the web app
    # classify crops the pipeline never produces.
    crops     = save_crops(args.input, merged_boxes, crops_object, PATH)
    crop_area = {c["name"]: c["area"] for c in crops}

    # Record which shelf photo every crop came from, now, while it is known for
    # certain. Recovering it later from the filename is what let test crops and KB
    # crops from the same photo look independent to cross-validation.
    manifest_path = write_crop_manifest(out_dir / MANIFEST_NAME, crops)
    print(f"  Crop provenance: {manifest_path}")

    # ── Stage 2: Load model + KB ─────────────────────────────────────────────
    print(f"\n[2/3] Loading {args.model} + knowledge base…")
    img2vec = Img2VecDino2() if args.model == "dino2" else Img2VecResnet18()

    classes, embeddings = load_kb_embeddings(KB_PATH, img2vec)
    index = KBIndex(classes, embeddings)

    print(f"  Knowledge base: {len(index.products)} products, {len(embeddings)} reference images")
    score_kind = "posterior" if args.match_mode == "lda" else "similarity"
    margin_txt = ("off" if args.margin_threshold is None
                  else f"≥ {args.margin_threshold}")
    print(f"  Match mode: {args.match_mode}  ({score_kind} ≥ {args.sim_threshold}, "
          f"margin {margin_txt})")
    for p in index.products:
        print(f"    · {p} ({classes.count(p)} imgs)")

    # ── Optional OCR tie-breaker ─────────────────────────────────────────────
    # Consulted only where the embedding head is undecided, so cost tracks the
    # number of hard crops rather than shelf size.
    ocr_reader = None
    if args.ocr:
        from src.ocr import OcrReader, fuse, should_consult
        try:
            ocr_reader = OcrReader()
            print(f"  OCR tie-breaker: on (margin {args.ocr_margin}, "
                  f"alpha {args.ocr_alpha}, "
                  f"brand-verify {'on' if args.ocr_verify_brand else 'off'})")
        except Exception as e:
            print(f"  OCR disabled ({type(e).__name__}: {e})")
            ocr_reader = None

    # ── Optional OpenAI fallback for rejected crops ──────────────────────────
    # Only rescues crops the local matcher gives up on. The candidate set is the
    # KB's beverage classes (distractors and unknown buckets excluded), so the
    # model can only return a real product or 'unknown'.
    llm = None
    if args.llm_fallback:
        from src.llm_fallback import OpenAIFallback
        # UNKNOWN_LABELS rather than a literal tuple: this list used to be
        # duplicated here, so renaming a bucket in classifier.py silently left
        # the old names behind and the LLM was offered a label the KB no longer had.
        bev_labels = [p for p in index.products
                      if not is_non_beverage(p) and p not in UNKNOWN_LABELS]
        try:
            llm = OpenAIFallback(bev_labels, model=args.llm_model)
            print(f"  LLM fallback: {llm.model} over {len(bev_labels)} beverage labels")
        except (RuntimeError, ValueError) as e:
            print(f"  LLM fallback disabled: {e}")
            llm = None

    # ── Stage 3: Classify each crop ──────────────────────────────────────────
    list_crops = sorted(glob.glob(f"{DATA_PATH}/{PATH}/crops/object/*.jpg"))
    print(f"\n[3/3] Classifying {len(list_crops)} detected crops…")

    if not list_crops:
        print("No crops found — check YOLO detection output.")
        exit(1)

    tta_active = args.tta and args.model == "dino2"
    if tta_active:
        print("  Test-time augmentation enabled (5× per crop)\n")

    n_skipped = 0
    bev_facings = Counter()          # beverage product -> number of facings
    bev_area    = defaultdict(float) # beverage product -> total pixel area
    for IMG_DIR in list_crops:
        img = Image.open(IMG_DIR)
        if tta_active and isinstance(img2vec, Img2VecDino2):
            vec = img2vec.getRobustVec(img)
        else:
            vec = img2vec.getVec(img)
        img.close()

        product, vote_conf, top_sim, margin = classify_full(vec, index,
                                                            mode=args.match_mode)
        # Report the absolute match quality — that's the meaningful signal now.
        confidence = top_sim
        source     = "local"

        crop_name = Path(IMG_DIR).stem

        # ── OCR tie-breaker / brand check ────────────────────────────────────
        # Runs before the gates so a rescued crop is judged on its fused score.
        # fuse() is a no-op when OCR reads nothing it recognises, which on small
        # shelf crops is the common case. Flavour evidence can only break ties;
        # brand evidence can also veto a confident wrong-brand call — see
        # src/ocr.py for why that asymmetry is deliberate.
        if ocr_reader is not None:
            cands = top_matches(vec, index, k=len(index.products),
                                mode=args.match_mode)
            if should_consult(cands, args.ocr_margin,
                              verify_brand=args.ocr_verify_brand):
                signal = ocr_reader.read(IMG_DIR)
                fused  = fuse(cands, signal, alpha=args.ocr_alpha)
                if fused[0][0] != cands[0][0]:
                    print(f"    ↳ OCR re-ranked {crop_name}: "
                          f"{cands[0][0]} → {fused[0][0]}  ({signal.text()[:40]!r})")
                    source = "ocr"
                product, confidence = fused[0][0], fused[0][1]
                vote_conf = 1.0
                # The fused ranking replaces the head's, so the head's margin no
                # longer describes this decision — recompute it from the fused list.
                margin = (fused[0][1] - fused[1][1]) if len(fused) > 1 else 1.0

        product = apply_gates(product, vote_conf, confidence,
                              args.conf_threshold, args.sim_threshold,
                              margin=margin, margin_threshold=args.margin_threshold)

        # ── LLM fallback ─────────────────────────────────────────────────────
        # Second chance for crops the local matcher rejected. Called only on
        # low_confidence, so cost tracks difficulty, not shelf size. A returned
        # beverage label is adopted; 'unknown' leaves the crop as low_confidence.
        if product == "low_confidence" and llm is not None:
            llm_label, llm_conf, llm_reason = llm.classify(IMG_DIR)
            if llm_label != "unknown":
                product    = llm_label
                confidence = llm_conf
                source     = "llm"
                print(f"    ↳ LLM rescued {crop_name} → {llm_label} "
                      f"({llm_conf:.0%}): {llm_reason}")

        # ── Skip non-beverages ──────────────────────────────────────────────
        # A crop that matched a non-beverage distractor class is set aside: it is
        # not a beverage facing, so it stays out of predictions and the count.
        # Set it apart from low_confidence — the latter is for ambiguous crops
        # that may still be (novel) beverages worth reviewing.
        if is_non_beverage(product):
            n_skipped += 1
            skip_dir = out_dir / "crops" / "_skipped_non_beverage"
            skip_dir.mkdir(parents=True, exist_ok=True)
            Path(IMG_DIR).replace(skip_dir / f"{crop_name}.jpg")
            print(f"  – {crop_name:<35} → skipped (non-beverage: {product}) {confidence:.0%}")
            continue

        dest_dir  = out_dir / "crops" / product
        dest_dir.mkdir(parents=True, exist_ok=True)
        Path(IMG_DIR).replace(dest_dir / f"{crop_name}.jpg")

        # Count only confidently-identified beverages toward share of shelf.
        # low_confidence crops stay out of the denominator — they are not
        # confirmed beverages, so folding them in would distort every share.
        if product != "low_confidence":
            bev_facings[product] += 1
            bev_area[product]    += crop_area.get(crop_name, 0)

        flag = "✓" if product != "low_confidence" else "?"
        tag  = "  [llm]" if source == "llm" else ""
        print(f"  {flag} {crop_name:<35} → {product:<35} {confidence:.0%}{tag}")

        with open(out_dir / "predictions.txt", "a", encoding="utf-8") as f:
            f.write(f"{crop_name} -> {product} ({confidence:.0%}) [{source}]\n")
        with open(out_dir / "predictions.csv", "a", encoding="utf-8") as f:
            f.write(f"{crop_name},{product},{confidence:.0%},{source}\n")



    # ── Share of shelf (beverages only) ──────────────────────────────────────
    n_total       = len(list_crops)
    n_identified  = sum(bev_facings.values())
    n_low_conf    = n_total - n_skipped - n_identified
    total_facings = n_identified
    total_area    = sum(bev_area.values())

    print(f"\n{'─' * 60}")
    print("SHARE OF SHELF — beverages")
    print(f"{'─' * 60}")
    if total_facings == 0:
        print("  No beverages confidently identified.")
    else:
        print(f"  {'product':<28}{'facings':>8}{'by facings':>13}{'by space':>11}")
        for product, count in bev_facings.most_common():
            fac_share  = count / total_facings
            area_share = (bev_area[product] / total_area) if total_area else 0
            print(f"  {product:<28}{count:>8}{fac_share:>12.1%}{area_share:>11.1%}")
        print(f"  {'─' * 58}")
        print(f"  {'TOTAL beverage facings':<28}{total_facings:>8}")

    # Persist the share table for downstream use.
    sos_csv = out_dir / "share_of_shelf.csv"
    with open(sos_csv, "w", encoding="utf-8") as f:
        f.write("product,facings,share_by_facings,share_by_space\n")
        for product, count in bev_facings.most_common():
            fac_share  = count / total_facings if total_facings else 0
            area_share = (bev_area[product] / total_area) if total_area else 0
            f.write(f"{product},{count},{fac_share:.4f},{area_share:.4f}\n")

    print(f"\nDetected {n_total} products → {n_identified} beverages identified, "
          f"{n_low_conf} unidentified, {n_skipped} non-beverage skipped.")
    print(f"Share of shelf: {sos_csv}")
    print(f"Per-crop predictions: {out_dir}/predictions.csv")
