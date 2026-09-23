import torch
import numpy as np
from transformers import AutoImageProcessor, AutoModel
from PIL import Image, ImageEnhance


class Img2VecDino2():
    """DINOv2 embeddings for shelf-product crops.

    Preprocessing note — this is the single highest-impact detail in the file.
    The stock `AutoImageProcessor` resizes the shortest edge to 256 and then
    CENTER-CROPS to 224. A shelf crop of a bottle is roughly 95x282, so that
    pipeline resized it to 256x759 and kept the middle 224 rows: about 30% of the
    bottle. Cap, shoulder, brand text and base were thrown away before the model
    ever ran, leaving only the part that looks identical across every flavour of
    the same SKU. That is why look-alike variants were unseparable.

    We letterbox to a square instead, so the whole crop survives with its aspect
    ratio intact. Measured on the 34-crop test set with the LDA head, this moved
    overall accuracy 82.4% -> 97.1%, and the badly-affected 750ml family
    66.7% -> 94.4%. Padding beat squashing, extra vertical resolution, and
    tiled thirds; see git history for the full sweep.
    """

    # Bump whenever anything here changes the output vectors. The KB embedding
    # cache keys on this — without it, changing preprocessing would silently
    # reuse stale vectors computed by the previous version.
    EMBED_VERSION = 2

    # Tried and rejected: capping the long side to 400px before letterboxing.
    # There IS a real domain gap between the two kinds of reference image —
    # real shelf crops are 40-600px, while the studio/e-commerce references are
    # 700-2200px, and same-class cosine similarity ACROSS those two domains is
    # 0.65-0.80 versus 0.81-0.92 within either one. Equalising resolution is
    # the obvious fix and it does nothing: grouped CV 71.3% -> 71.6%, and
    # scored on real shelf crops only, 73.8% -> 73.8%. So the gap is driven by
    # viewpoint, lighting and background (white studio sweep vs cluttered
    # shelf), not by pixel count. Don't re-try the resolution angle; closing it
    # needs references shot on real shelves.

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.modelName = "facebook/dinov2-base"
        self.processor = AutoImageProcessor.from_pretrained(self.modelName)
        self.model = AutoModel.from_pretrained(self.modelName).to(self.device)
        self.model.eval()
        # Reuse the checkpoint's own normalisation statistics; only the geometry
        # (resize + center-crop) is being replaced, not the colour handling.
        self._mean = np.array(self.processor.image_mean, dtype=np.float32)
        self._std  = np.array(self.processor.image_std,  dtype=np.float32)

    # ── Preprocessing ───────────────────────────────────────────────────────

    @staticmethod
    def _letterbox(img, size=224):
        """Pad to square on a white field, then resize. Keeps the entire crop."""
        w, h = img.size
        side = max(w, h)
        canvas = Image.new("RGB", (side, side), (255, 255, 255))
        canvas.paste(img, ((side - w) // 2, (side - h) // 2))
        return canvas.resize((size, size), Image.BICUBIC)

    def _to_tensor(self, img):
        arr = np.asarray(img, dtype=np.float32) / 255.0
        arr = (arr - self._mean) / self._std
        return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)

    # ── Embedding ───────────────────────────────────────────────────────────

    def getVec(self, img):
        if img.mode != 'RGB':
            img = img.convert('RGB')
        tensor = self._to_tensor(self._letterbox(img)).to(self.device)
        with torch.no_grad():
            outputs = self.model(tensor, interpolate_pos_encoding=True)
            # CLS token + mean of patch tokens → richer than CLS alone
            cls_token  = outputs.last_hidden_state[:, 0, :]
            patch_mean = outputs.last_hidden_state[:, 1:, :].mean(dim=1)
            emb = (cls_token + patch_mean) / 2
        emb = torch.nn.functional.normalize(emb, dim=-1)
        return emb.squeeze().cpu().numpy()

    def getRobustVec(self, img, include_flip=True):
        """Average embeddings over several augmentations (test-time augmentation).

        More robust to glare, reflections, and lighting differences on shelf photos.

        `include_flip` exists so the horizontal flip can be ablated on its own. It is
        the one view here that is not obviously safe: the discriminative signal for
        these products is brand text and label layout, both of which are CHIRAL.
        Averaging an image with its mirror pulls the embedding toward the
        flip-invariant subspace, which suppresses exactly the text-like features that
        separate look-alike flavours. The other four views (identity, two brightness,
        one contrast) only perturb photometry, which is the nuisance variable TTA is
        supposed to average out.

        Apply this to the KNOWLEDGE BASE as well as to queries. Embedding queries
        with a 5-view average while references get a single view leaves the two in
        measurably different distributions: averaging shrinks the components where
        the views disagree, so a TTA query is systematically closer to its own class
        mean than an un-augmented reference is. Worse, the LDA head is FITTED on
        single-view reference vectors and then applied to averaged query vectors,
        which is a train/serve mismatch in the classifier's input.
        """
        if img.mode != 'RGB':
            img = img.convert('RGB')
        augmented = [
            img,
            ImageEnhance.Brightness(img).enhance(1.25),
            ImageEnhance.Brightness(img).enhance(0.75),
            ImageEnhance.Contrast(img).enhance(1.2),
        ]
        if include_flip:
            augmented.insert(1, img.transpose(Image.FLIP_LEFT_RIGHT))
        vecs = np.stack([self.getVec(aug) for aug in augmented])
        avg = vecs.mean(axis=0)
        norm = np.linalg.norm(avg)
        return avg / norm if norm > 0 else avg
