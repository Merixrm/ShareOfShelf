"""OCR signal: read label text off a crop and turn it into brand/flavour evidence.

Why this exists
---------------
The embedding classifier fails in two ways that pixels alone cannot fix:

  * FLAVOUR confusion inside one brand's family. Those packs are identical in
    shape, sleeve layout and cap; only the fruit graphic and the flavour word
    separate them.
  * BRAND confusion across families. The knowledge base is closed-set — every
    named class is a Sunich SKU — so a competitor pack with a similar fruit
    graphic is handed the nearest Sunich label instead of landing in
    `unknown_beverage`. That one is the expensive error: a rival's facing counted
    as ours inflates Sunich share-of-shelf directly.

OCR reads the brand word and the flavour word, so it is complementary evidence
rather than more of the same.

What it is NOT
--------------
It is not a classifier, and it is not always-on by default. Measured on this
hardware EasyOCR costs roughly 6-12s per crop and returns nothing usable on small
shelf crops (a 116px-wide pack simply has too few pixels on the label). A shelf
photo with 44 detections would add minutes per image. So the intended use is
targeted: run it where the embedding head is undecided, or — with
`--ocr-verify-brand` — on every crop about to be counted as a named product. See
`should_consult` and `--ocr` in main.py.

Language
--------
The packs here are bilingual: one face carries Persian text, the opposite face
carries English, and which one is visible depends purely on how the facing was
stacked. Both must be readable.

EasyOCR maps `fa` onto its `arabic.pth` recogniser, which is one of the two model
files cached on this machine (the other is the CRAFT detector), so this runs fully
offline. Adding `en` to the language list keeps that same model file — easyocr's
arabic script group is declared compatible with English (`easyocr/easyocr.py`,
`setModelLanguage('arabic', ..., arabic_lang_list + ['en'])`), so nothing extra is
downloaded.

`en` is NOT optional, and an earlier version of this module was wrong to call
Latin coverage automatic. easyocr builds `lang_char` from the per-language
character files and passes everything OUTSIDE it to the decoder as `ignore_char`.
`fa_char.txt` contains zero Latin letters, so with `langs=("fa",)` the recogniser
is actively forbidden from emitting a-z — the English face of a pack comes back as
punctuation noise. Measured on the Sun Star peach pack in
data/PXL_20260807_132315005.MP (116px wide):

    langs=("fa",)        -> [('؟$', 0.18), ('?٤ه=؟', 0.02)]
    langs=("fa", "en")   -> [('S', 0.43), ('Peaer', 0.35)]     # 'Peaer' -> peach

Safety property
---------------
`fuse` is a no-op when OCR finds nothing it recognises: if no lexicon term matches
above `min_match`, every candidate keeps its score and the ranking is returned
unchanged.

Note the one deliberate exception. Flavour evidence is bonus-only — a candidate
whose flavour was not read is never penalised, so a missed word cannot push the
right answer down. BRAND evidence is signed: a confidently-read brand that
contradicts a candidate's brand demotes it, and promotes `unknown_beverage` when
no KB class carries the brand we read. That is the whole point — a bonus-only
scheme can never fix "right flavour, wrong brand", because the fruit graphic the
embedding keyed on really is orange. To keep that power from firing on noise, the
brand gate is stricter than the flavour gate: the winning brand must clear
`min_match` AND beat the runner-up brand by `brand_margin`.
"""

import re
import math
import difflib
import unicodedata

from .classifier import UNKNOWN_LABELS

# Label used for "a beverage we detect but deliberately do not name". Derived from
# classifier.py rather than hardcoded so renaming the bucket there cannot silently
# leave `fuse` promoting a class the knowledge base no longer has.
UNKNOWN_LABEL = sorted(UNKNOWN_LABELS)[0]

# ── Persian text normalisation ──────────────────────────────────────────────
# OCR output is not character-stable: it returns Arabic yeh/kaf where Persian
# yeh/kaf were printed, drops the zero-width non-joiner, and loses spaces
# ("سن ایچ" comes back as "سنایچ"). Normalising both the OCR output and the
# lexicon into the same reduced form is what makes matching work at all.
_CHAR_MAP = {
    "ي": "ی",  # arabic yeh    -> persian yeh
    "ى": "ی",  # alef maksura  -> persian yeh
    "ك": "ک",  # arabic kaf    -> persian kaf
    "ة": "ه",  # teh marbuta   -> heh
    "أ": "ا", "إ": "ا", "آ": "ا",  # hamza forms -> alef
}
_DIACRITICS = re.compile(r"[ً-ْٰ]")


def normalize(text):
    """Reduce Persian/Latin text to a comparable form: no spaces, no diacritics."""
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _CHAR_MAP.items():
        text = text.replace(src, dst)
    text = text.replace("‌", "")            # ZWNJ
    text = _DIACRITICS.sub("", text)
    text = re.sub(r"[\s\W_]+", "", text)
    return text.lower()


# ── Lexicon ─────────────────────────────────────────────────────────────────
# Keys match the tokens used in knowledge-base folder names (brand_size_flavour),
# so a new KB class only needs an entry here to become OCR-addressable.
#
# A brand listed here does NOT need a KB class. Listing a competitor is what lets
# `fuse` recognise "this is somebody else's pack" and route it to
# `unknown_beverage` instead of to the nearest-looking Sunich SKU. Both Persian
# and Latin spellings belong in the list — the two faces of one pack carry
# different scripts, and which face is on display is an accident of stacking.
BRAND_TERMS = {
    "sunich":  ["سن ایچ", "سنایچ", "sunich"],
    # Sun Star (سان استار) — 240ml tetra packs. Same fruit photography as the
    # Sunich cartons, which is exactly why the embedding head mistakes them for
    # sunich_1L_orange / sunich_1L_peach.
    "sunstar": ["سان استار", "سانستار", "sun star", "sunstar", "sun-star"],
}

FLAVOUR_TERMS = {
    "apple":       ["سیب", "apple"],
    "cherry":      ["آلبالو", "گیلاس", "cherry"],
    "mango":       ["انبه", "mango"],
    # "پرتقال تو سرخ" is blood orange; the "پرتقال" stem carries the match.
    "orange":      ["پرتقال", "orange", "blood orange"],
    "peach":       ["هلو", "peach"],
    "pineapple":   ["آناناس", "pineapple"],
    "pomegranate": ["انار", "pomegranate"],
    "mix":         ["میکس", "مخلوط", "مولتی ویتامین", "mix", "multi"],
    "pinacolada":  ["پیناکولادا", "پینا کولادا", "pinacolada", "colada"],
    "tropical":    ["گرمسیری", "استوایی", "tropical"],
}

_BRAND_NORM   = {b: [normalize(t) for t in ts] for b, ts in BRAND_TERMS.items()}
_FLAVOUR_NORM = {f: [normalize(t) for t in ts] for f, ts in FLAVOUR_TERMS.items()}

# "انار" (pomegranate) is a substring of nothing here, but "انبه" (mango) and
# "انار" share a prefix, and short tokens fuzzy-match each other far too easily.
# Terms at or below this length must match (near-)exactly.
_SHORT_TERM_LEN = 4


def _match(token, term):
    """Fuzzy similarity in [0,1], with short terms held to a stricter standard."""
    if not token or not term:
        return 0.0
    ratio = difflib.SequenceMatcher(None, token, term).ratio()
    if len(term) <= _SHORT_TERM_LEN and ratio < 1.0:
        # Allow a containment hit (label words are often glued to neighbours by
        # the recogniser) but nothing looser, or انبه/انار start trading places.
        return 1.0 if term in token else 0.0
    return ratio


def _best_over_terms(tokens, terms):
    return max((_match(tok, term) for tok in tokens for term in terms), default=0.0)


# ── OCR result ──────────────────────────────────────────────────────────────

class OcrSignal:
    """Normalised OCR evidence for one crop."""

    __slots__ = ("tokens", "raw", "brand_scores", "flavour_scores")

    def __init__(self, raw):
        self.raw    = raw                                   # [(text, conf)]
        self.tokens = [normalize(t) for t, _c in raw]
        self.tokens = [t for t in self.tokens if t]
        self.brand_scores   = {b: _best_over_terms(self.tokens, ts)
                               for b, ts in _BRAND_NORM.items()}
        self.flavour_scores = {f: _best_over_terms(self.tokens, ts)
                               for f, ts in _FLAVOUR_NORM.items()}

    def best_flavour(self):
        if not self.flavour_scores:
            return None, 0.0
        f = max(self.flavour_scores, key=self.flavour_scores.get)
        return f, self.flavour_scores[f]

    def best_brand(self):
        if not self.brand_scores:
            return None, 0.0
        b = max(self.brand_scores, key=self.brand_scores.get)
        return b, self.brand_scores[b]

    def brand_ranked(self):
        """(brand, score, runner_up_score) — the margin matters, not just the score.

        Brand evidence is the only signed signal in `fuse`, so a false positive
        costs a correct answer rather than merely failing to fix a wrong one. The
        normalised Persian brand strings are close enough to confuse each other on
        a garbled read — سنایچ vs ساناستار scores 0.46 on difflib alone — so the
        caller gates on `score - runner_up`, which collapses to ~0 exactly when the
        recogniser produced mush that resembles every brand equally.
        """
        if not self.brand_scores:
            return None, 0.0, 0.0
        ranked = sorted(self.brand_scores.items(), key=lambda kv: kv[1], reverse=True)
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        return ranked[0][0], ranked[0][1], runner_up

    def __bool__(self):
        return bool(self.tokens)

    def text(self):
        return " ".join(t for t, _c in self.raw)


# ── Reader ──────────────────────────────────────────────────────────────────

class OcrReader:
    """Lazy EasyOCR wrapper, pinned offline.

    `download_enabled=False` on purpose: this machine has no network, and a silent
    download attempt would hang rather than fail. If the cached models are missing
    we want a clear error at construction time.
    """

    # canvas_size/mag_ratio picked by sweep over the test set: yield rises
    # monotonically with magnification (any-text 5->12 of 34 from mag 1 to 4) and
    # so does cost (2.9s -> 8.5s per crop). Since --ocr is opt-in and only fires
    # on undecided crops, the high-yield end is the right default here.
    # langs defaults to BOTH scripts. These packs are bilingual — one face
    # Persian, the other English — so a Persian-only reader is blind to roughly
    # half the facings on a shelf. `en` costs nothing: easyocr's arabic script
    # group already covers it, so this still loads only the cached arabic.pth.
    # See the module docstring for the measurement.
    def __init__(self, langs=("fa", "en"), gpu=False, min_conf=0.20,
                 canvas_size=1280, mag_ratio=4.0):
        import easyocr
        self.min_conf    = min_conf
        self.canvas_size = canvas_size
        self.mag_ratio   = mag_ratio
        self._reader = easyocr.Reader(list(langs), gpu=gpu,
                                      download_enabled=True, verbose=False)

    def read(self, image):
        """`image` is a PIL image or a path. Returns an OcrSignal (never raises)."""
        import numpy as np
        from PIL import Image

        if not hasattr(image, "convert"):
            image = Image.open(image)
        arr = np.array(image.convert("RGB"))
        try:
            res = self._reader.readtext(arr, detail=1, paragraph=False,
                                        canvas_size=self.canvas_size,
                                        mag_ratio=self.mag_ratio)
        except Exception:
            # A crop too small for the detector raises inside easyocr. That is a
            # normal outcome here, not an error worth failing the pipeline over.
            res = []
        return OcrSignal([(t, float(c)) for _box, t, c in res if c >= self.min_conf])


# ── Label parsing + fusion ──────────────────────────────────────────────────

def split_label(label):
    """'sunich_750ml_mix' -> ('sunich', 'mix'). Non-product labels -> (None, None)."""
    parts = label.split("_")
    if len(parts) < 3:
        return None, None
    return parts[0], parts[-1]


def should_consult(candidates, margin=0.35, verify_brand=False):
    """True when OCR is worth its ~8s on this crop.

    Two independent reasons to look:

    * The embedding head is UNDECIDED — top-2 gap below `margin`. This is the
      original, cost-bounded trigger: on a 44-crop shelf photo only the genuinely
      close calls pay the latency, and that is where flavour confusions live.

    * `verify_brand` and the head is about to name a specific product. A confident
      score is no evidence at all about brand: the head scores a Sun Star pack at
      99% `sunich_1L_orange` precisely because it keys on the orange graphic, and
      99% puts it nowhere near the margin gate. Anything counted toward a brand's
      share-of-shelf is worth one read; bucket labels (`unknown_beverage`,
      `non_beverage*`) are not, since they claim no brand to contradict.
    """
    if not candidates:
        return False
    if verify_brand and split_label(candidates[0][0])[0] is not None:
        return True
    if len(candidates) < 2:
        return False
    return (candidates[0][1] - candidates[1][1]) < margin


# Multiplier applied to a candidate whose brand OCR has contradicted. It is a
# veto, not a penalty, and it is a veto for a concrete reason: the scores coming
# in are LDA posteriors, and LDA here is pathologically overconfident — the head
# rates the Sun Star blood-orange pack 0.99 `sunich_1L_orange` against 0.003 for
# `unknown_beverage`, a 330:1 prior. Any exp(-alpha * score) penalty that could
# overturn 330:1 also swamps every other signal in the ranking, and the alpha
# that does it depends on LDA_TEMPERATURE, which is fitted separately. A
# multiplicative floor sidesteps the calibration problem entirely: contradicted
# candidates rank below every surviving one, and keep their order among
# themselves so a ranked candidate list can still show them.
_BRAND_VETO = 1e-6


def fuse(candidates, signal, alpha=1.5, min_match=0.60,
         brand_alpha=3.0, brand_margin=0.15, unknown_label=UNKNOWN_LABEL):
    """Re-rank `candidates` [(label, prob)] using OCR evidence.

    The two kinds of evidence act differently, on purpose:

    FLAVOUR — a soft, bonus-only multiplier, exp(alpha * score), applied when the
    candidate's own flavour token is the one OCR read. A candidate whose flavour
    was not read gets nothing rather than a penalty, so a word the recogniser
    missed can never push the right answer down. This is the tie-breaker the
    module was originally built for.

    BRAND — a constraint. Bonus-only fusion is structurally incapable of fixing
    the error that costs the most here: a competitor pack carrying the same fruit
    photography. The flavour really IS orange, so every flavour-driven term agrees
    with the wrong answer, and the brand word is the only evidence that disagrees.
    So a brand read that clears the gate below is treated as fact:

        candidate's brand == brand read  ->  kept
        candidate's brand != brand read  ->  vetoed  (see _BRAND_VETO)
        bucket label (`unknown_beverage`,
        `non_beverage*`)                 ->  kept; it claims no brand to contradict
        `unknown_label`, and no candidate
        carries the brand we read        ->  promoted by exp(brand_alpha * score)

    That last case is the open-set escape, and it is the one that matters for
    share-of-shelf. Reading "sunstar" off a pack when the knowledge base has no
    Sun Star class must not fall through to the nearest Sunich SKU — a rival's
    facing counted as ours inflates our share directly. It should say "a beverage,
    but not one of ours". Add a `sunstar_240ml_peach` folder to the KB and this
    same code routes the crop to that real label instead, with no change here.

    Because brand evidence can overturn a confident prediction, it is gated harder
    than flavour: the winning brand must clear `min_match` AND beat the runner-up
    brand by `brand_margin`. A garbled read that resembles every brand about
    equally fails the margin test, and the brand term drops out entirely.

    Returns the input unchanged when there is no usable evidence.
    """
    if not signal:
        return candidates

    flavour, f_score = signal.best_flavour()
    use_flavour = flavour is not None and f_score >= min_match

    brand, b_score, b_runner_up = signal.brand_ranked()
    use_brand = (brand is not None and b_score >= min_match
                 and (b_score - b_runner_up) >= brand_margin)

    if not (use_flavour or use_brand):
        return candidates

    # Brands the knowledge base can actually name. Anything else we read is by
    # definition off-brand, and `unknown_label` is where such a crop belongs.
    kb_brands = {split_label(l)[0] for l, _p in candidates} - {None}
    brand_is_known = use_brand and brand in kb_brands

    scored = []
    for label, prob in candidates:
        lab_brand, lab_flavour = split_label(label)
        weight = prob

        if use_flavour and lab_flavour and lab_flavour == flavour:
            weight *= math.exp(alpha * f_score)

        if use_brand:
            if lab_brand is not None and lab_brand != brand:
                weight *= _BRAND_VETO
            elif label == unknown_label and not brand_is_known:
                weight *= math.exp(brand_alpha * b_score)

        scored.append((label, weight))

    total = sum(w for _l, w in scored) or 1.0
    scored = [(l, w / total) for l, w in scored]
    scored.sort(key=lambda kv: kv[1], reverse=True)
    return scored
