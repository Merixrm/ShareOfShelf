"""OpenAI vision fallback for crops the local matcher can't place.

The DINOv2/ResNet + knowledge-base matcher in `classifier.py` can only name a
product it already has reference crops for; everything else it rejects to
`low_confidence`. This module gives those rejects a second chance: it shows the
crop to an OpenAI vision model and asks it to pick from the *same* known label
set (or say `unknown`). It never invents a label — the response is constrained to
an enum — so a novel product still lands as `unknown` rather than a confident
guess.

Design intent (see README): this is a *fallback*, not the primary classifier.
It is only ever called on crops the free/local path already gave up on, so cost
scales with difficulty, not with shelf size. If no API key is present or the
`openai` package is missing, the pipeline runs exactly as before.

Environment:
  OPENAI_API_KEY   required to use the fallback (raise a clear error otherwise)
  OPENAI_MODEL     optional, defaults to 'gpt-4.1'
"""

import os
import base64
import json
from pathlib import Path

DEFAULT_MODEL = "gpt-4.1"

# Returned when the model declines to match any known product. Kept identical to
# the local matcher's reject bucket so downstream code (share-of-shelf, counts)
# needs no special case.
UNKNOWN = "unknown"


class OpenAIFallback:
    """Lazily-initialised OpenAI vision classifier constrained to known labels.

    Parameters
    ----------
    candidate_labels : list[str]
        The beverage product labels the model may choose from (typically the KB's
        beverage classes, minus non-beverage distractors and unknown buckets).
    model : str, optional
        OpenAI model id. Falls back to $OPENAI_MODEL then 'gpt-4.1'.
    """

    def __init__(self, candidate_labels, model=None):
        self.candidate_labels = list(candidate_labels)
        if not self.candidate_labels:
            raise ValueError("OpenAIFallback needs at least one candidate label.")
        self.model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Export your key to enable --llm-fallback, "
                "e.g.  export OPENAI_API_KEY=sk-...  (the pipeline runs fine without it, "
                "it just won't rescue low_confidence crops)."
            )

        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError(
                "The 'openai' package is required for --llm-fallback. "
                "Install it with:  pip install openai"
            ) from e

        self.client = OpenAI(api_key=api_key)

        # Constrain the answer to the known labels + 'unknown' via a strict JSON
        # schema. The enum is the guardrail that stops the model from returning a
        # plausible-but-unlisted brand.
        self._schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "product_match",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {
                            "type": "string",
                            "enum": self.candidate_labels + [UNKNOWN],
                            "description": "The single best matching product, or "
                                           "'unknown' if none clearly matches.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "0-1 self-assessed confidence in the label.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief justification (visible text, colour, shape).",
                        },
                    },
                    "required": ["label", "confidence", "reason"],
                },
            },
        }

    # ── internals ────────────────────────────────────────────────────────────

    @staticmethod
    def _encode(image_path):
        data = Path(image_path).read_bytes()
        return base64.b64encode(data).decode("ascii")

    def _prompt(self):
        listing = "\n".join(f"  - {lab}" for lab in self.candidate_labels)
        return (
            "You are identifying a single retail beverage product from a cropped "
            "shelf photo. Read any visible brand text, logo, colour and container "
            "shape.\n\n"
            "Choose the ONE best match from this exact list of known products:\n"
            f"{listing}\n\n"
            f"If the crop is not clearly one of these (a different product, a "
            f"non-beverage, or too blurry/occluded to tell), answer '{UNKNOWN}'. "
            "Do not guess a listed product just because it is similar — only match "
            "when the visible evidence supports it."
        )

    # ── public API ───────────────────────────────────────────────────────────

    def classify(self, image_path):
        """Return (label, confidence, reason).

        `label` is one of `candidate_labels` or 'unknown'. On any API/parse error
        this returns ('unknown', 0.0, <error>) so the caller can keep the crop as
        low_confidence rather than crashing the run.
        """
        try:
            b64 = self._encode(image_path)
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self._prompt()},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64}",
                                    "detail": "low",  # crops are small; 'low' is cheaper
                                },
                            },
                        ],
                    }
                ],
                response_format=self._schema,
                max_tokens=200,
                temperature=0,
            )
            payload = json.loads(resp.choices[0].message.content)
            label = payload.get("label", UNKNOWN)
            if label not in self.candidate_labels:
                label = UNKNOWN
            conf = float(payload.get("confidence", 0.0))
            reason = str(payload.get("reason", ""))
            return label, conf, reason
        except Exception as e:  # network, quota, parse — degrade gracefully
            return UNKNOWN, 0.0, f"fallback error: {e}"
