"""
Vision-LLM identification of unknown-beverage crops (brand, flavour, size).

Used by src/unknown_beverage_pipeline.py. Run it from the repo root:
python -m src.unknown_beverage_pipeline --input data/knowledge_base/crops/object/unknown_beverage

Needs GAPGPT_API_KEY and `pip install openai ddgs`.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

DEFAULT_BASE_URL = "https://api.gapgpt.app/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_SEARCH_BACKEND = "google,brave,duckduckgo,bing"
DEFAULT_SEARCH_REGION = "us-en"
DEFAULT_SEARCH_RESULTS_PER_QUERY = 5
DEFAULT_MAX_SEARCH_RESULTS = 30
DEFAULT_MAX_BRAND_CANDIDATES = 3

SUPPORTED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

GENERIC_FLAVOR_WORDS = {
    "juice", "drink", "beverage", "nectar", "squash", "flavor", "flavour",
    "flavored", "flavoured", "with", "pulp", "pulpy", "nopulp", "withoutpulp",
}

KNOWN_FRUITS = {
    "apple", "apricot", "banana", "blackberry", "blueberry", "cherry", "coconut",
    "cranberry", "dragonfruit", "grape", "grapefruit", "guava", "kiwi", "lemon",
    "lime", "lychee", "mandarin", "mango", "melon", "orange", "passionfruit",
    "peach", "pear", "pineapple", "pomegranate", "raspberry", "strawberry",
    "tangerine", "watermelon", "سیب", "watermelonآلبالو", "پیناکولادا", "انبه", "پرتقال", "توت فرنگی", "هلو", "آناناس", "انار",
}

FRUIT_ALIASES = {
    "passion fruit": "passionfruit",
    "dragon fruit": "dragonfruit",
    "blood orange": "orange",
    "red orange": "orange",
    "pulp orange": "orange",
    "pulpy orange": "orange",
    "orange with pulp": "orange",
    "orange without pulp": "orange",
    "no pulp orange": "orange",
    "sour cherry": "cherry",
}

# Tiny valid PNG used only to test whether a configured vision model is reachable.
HEALTH_CHECK_IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)


@dataclass
class UnknownBeverageResult:
    status: str
    label: Optional[str]
    brand: Optional[str]
    flavor: Optional[str]
    size: Optional[str]
    initial_candidate: dict
    brand_recheck: dict
    brand_candidates: list[str]
    flavor_recheck: dict
    size_recovery: dict
    search_queries: list[dict]
    search_results: list[dict]
    evidence: list[str]
    conflicts: list[str]
    verification_reason: Optional[str] = None

    @property
    def verified(self) -> bool:
        return self.status == "verified" and self.label is not None

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_list(value) -> list:
    return value if isinstance(value, list) else []


def _compact_token(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).translate(DIGIT_TRANSLATION)
    text = text.strip().lower()
    if re.search(r"[\u0600-\u06ff]", text):
        return ""
    return re.sub(r"[^a-z0-9]+", "", text)


def _normalize_size(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).translate(DIGIT_TRANSLATION)
    text = text.lower().replace(",", ".")
    replacements = {
        "milliliters": "ml", "millilitres": "ml", "milliliter": "ml", "millilitre": "ml",
        "liters": "l", "litres": "l", "liter": "l", "litre": "l",
        "میلی لیتر": "ml", "میلی‌لیتر": "ml", "میلیلیتر": "ml",
        "میلی لیتری": "ml", "میلی‌لیتری": "ml", "لیتر": "l", "لیتری": "l",
        "سی سی": "cc", "سی‌سی": "cc", "سیسی": "cc",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", "", text)

    match = re.search(r"(\d+(?:\.\d+)?)\s*(ml|cc|cl|l)\b", text)
    if not match:
        return ""

    amount, unit = float(match.group(1)), match.group(2)
    if amount <= 0:
        return ""
    ml = round(amount * 1000) if unit == "l" else round(amount * 10) if unit == "cl" else round(amount)
    if ml <= 0:
        return ""
    if ml < 1000:
        return f"{ml}ml"

    liters = ml / 1000
    value = str(int(liters)) if liters.is_integer() else f"{liters:.3f}".rstrip("0").rstrip(".")
    return f"{value}L"


def _clean_ascii_words(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).translate(DIGIT_TRANSLATION).lower().strip()
    if re.search(r"[\u0600-\u06ff]", text):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _extract_fruits(value: str) -> list[str]:
    text = _clean_ascii_words(value)
    if not text:
        return []

    found = []
    def add(item: str) -> None:
        if item and item not in found:
            found.append(item)

    for phrase, canonical in FRUIT_ALIASES.items():
        if phrase in text:
            add(canonical)

    words = set(text.split())
    if "orange" in words:
        add("orange")
    if "cherry" in words:
        add("cherry")
    if "passion" in words and "fruit" in words:
        add("passionfruit")
    if "dragon" in words and "fruit" in words:
        add("dragonfruit")

    for fruit in KNOWN_FRUITS - {"orange", "cherry", "passionfruit", "dragonfruit"}:
        if fruit in words:
            add(fruit)
    return found


def _normalize_fruits(values) -> list[str]:
    result = []
    for value in _safe_list(values):
        fruits = _extract_fruits(str(value)) or [_compact_token(str(value))]
        for fruit in fruits:
            if fruit and fruit not in result:
                result.append(fruit)
    return result


def _normalize_flavor(value: str, fruits=None) -> str:
    normalized_fruits = _normalize_fruits(fruits)
    for fruit in _extract_fruits(value):
        if fruit not in normalized_fruits:
            normalized_fruits.append(fruit)

    if len(normalized_fruits) >= 2:
        return "mix"
    if not value:
        return normalized_fruits[0] if normalized_fruits else ""

    text = _clean_ascii_words(value)
    if not text:
        return ""
    if "orange" in text.split():
        return "orange"
    if "sour cherry" in text:
        return "cherry"

    tokens = [t for t in re.findall(r"[a-z0-9]+", text) if t not in GENERIC_FLAVOR_WORDS]
    flavor = "".join(tokens)
    if flavor in {"mixedfruit", "mixedfruits", "fruitmix", "mixed", "mix"}:
        return "mix"
    if len(normalized_fruits) == 1 and flavor.startswith(normalized_fruits[0]):
        return normalized_fruits[0]
    return flavor or (normalized_fruits[0] if normalized_fruits else "")


def _normalize_brand_candidates(values, initial_brand: str = "", max_candidates: int = 3) -> list[str]:
    candidates = []
    for item in _safe_list(values):
        raw = item.get("brand", "") if isinstance(item, dict) else item
        brand = _compact_token(str(raw))
        if brand and brand not in candidates:
            candidates.append(brand)

    initial = _compact_token(initial_brand)
    if initial and initial not in candidates:
        candidates.append(initial)
    return candidates[:max_candidates]


def _image_to_data_url(image_path: str | Path) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")
    mime, _ = mimetypes.guess_type(path.name)
    if mime not in SUPPORTED_IMAGE_MIMES:
        raise ValueError(f"Unsupported image format: {path.name}. Use JPG, JPEG, PNG or WEBP.")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _extract_json_object(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text or "").strip(), flags=re.I)
    if not cleaned:
        raise ValueError("GapGPT returned an empty response.")
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"GapGPT did not return valid JSON: {cleaned[:700]}")
        try:
            value = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"GapGPT returned malformed JSON: {cleaned[:700]}") from exc
    if not isinstance(value, dict):
        raise ValueError("GapGPT response is not a JSON object.")
    return value


def _brand_exact_match(brand: str, *, title: str, snippet: str, url: str) -> bool:
    token = _compact_token(brand)
    return bool(token and token in _compact_token(f"{title} {snippet} {url}"))


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _merge_unique_results(target: list[dict], new_items: list[dict]) -> None:
    seen = {
        (str(x.get("candidate_brand", "")).lower(), str(x.get("url", "")).lower(), str(x.get("title", "")).lower())
        for x in target
    }
    for item in new_items:
        key = (
            str(item.get("candidate_brand", "")).lower(),
            str(item.get("url", "")).lower(),
            str(item.get("title", "")).lower(),
        )
        if key not in seen:
            target.append(item)
            seen.add(key)


class UnknownBeverageClassifier:
    def __init__(
        self,
        model: Optional[str] = None,
        verify_model: Optional[str] = None,
        brand_model: Optional[str] = None,
        flavor_model: Optional[str] = None,
        size_model: Optional[str] = None,
        base_url: Optional[str] = None,
        health_check: bool = True,
        search_backend: Optional[str] = None,
        search_region: Optional[str] = None,
        search_results_per_query: int = DEFAULT_SEARCH_RESULTS_PER_QUERY,
        max_search_results: int = DEFAULT_MAX_SEARCH_RESULTS,
        max_brand_candidates: int = DEFAULT_MAX_BRAND_CANDIDATES,
    ):
        api_key = os.getenv("GAPGPT_API_KEY")
        if not api_key:
            raise RuntimeError("GAPGPT_API_KEY is not set.")

        try:
            from openai import OpenAI
            from ddgs import DDGS
        except ImportError as exc:
            raise RuntimeError("Install dependencies with: pip install -U openai ddgs") from exc

        self.base_url = (base_url or os.getenv("GAPGPT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.getenv("GAPGPT_MODEL") or DEFAULT_MODEL
        self.verify_model = verify_model or os.getenv("GAPGPT_VERIFY_MODEL") or self.model
        self.brand_model = brand_model or os.getenv("GAPGPT_BRAND_MODEL") or self.model
        self.flavor_model = flavor_model or os.getenv("GAPGPT_FLAVOR_MODEL") or self.model
        self.size_model = size_model or os.getenv("GAPGPT_SIZE_MODEL") or self.model
        self.search_backend = search_backend or os.getenv("UB_SEARCH_BACKEND") or DEFAULT_SEARCH_BACKEND
        self.search_region = search_region or os.getenv("UB_SEARCH_REGION") or DEFAULT_SEARCH_REGION
        self.search_results_per_query = max(1, int(search_results_per_query))
        self.max_search_results = max(1, int(max_search_results))
        self.max_brand_candidates = max(1, min(int(max_brand_candidates), 5))
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)
        self.DDGS = DDGS

        if health_check:
            for current_model in dict.fromkeys(
                [self.model, self.brand_model, self.flavor_model, self.size_model, self.verify_model]
            ):
                self._health_check(current_model)

    def _health_check(self, model: str) -> None:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Look at this image. Reply only with OK."},
                        {"type": "image_url", "image_url": {"url": HEALTH_CHECK_IMAGE}},
                    ],
                }],
                temperature=0,
                max_tokens=10,
            )
            if not response.choices[0].message.content:
                raise RuntimeError("empty response")
        except Exception as exc:
            raise RuntimeError(
                f"GapGPT Vision health check failed. Base URL={self.base_url}, model={model}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    def _chat_json(self, *, model: str, prompt: str, image_data_url: str, max_tokens: int = 900) -> dict:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You identify retail beverages from images. Return only one valid JSON object.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data_url}},
                        ],
                    },
                ],
                temperature=0,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise RuntimeError(f"GapGPT request failed: {type(exc).__name__}: {exc}") from exc
        return _extract_json_object(response.choices[0].message.content or "")

    def _identify(self, image_data_url: str) -> dict:
        prompt = """
Identify one beverage SKU from the image. This is open-set: unknown brands are allowed.
Read the package visually; there is no external OCR.

Return brand, semantic flavor, exact package size, fruits, evidence and conflicts.
Rules:
- brand: lowercase Latin; use only visible/logo evidence, not package color.
- flavor: lowercase English. Two or more distinct fruits -> "mix".
- sour cherry -> cherry. Any orange variant -> orange.
- remove generic words such as juice, drink, beverage, nectar and squash.
- size must come from visible package text, never container proportions or nutrition text like "per 100 ml".
- use 1L/1.5L/2L for 1000/1500/2000ml.
- use empty string for a field that cannot be read safely.
- status="candidate" if there is enough information to continue, otherwise "uncertain".

Return only:
{"status":"candidate","brand":"sunstar","flavor":"orange","size":"240ml",
 "fruits":["orange"],"evidence":["brief evidence"],"conflicts":[]}
""".strip()
        return self._chat_json(model=self.model, prompt=prompt, image_data_url=image_data_url)

    def _brand_recheck(self, image_data_url: str) -> dict:
        prompt = f"""
Independently identify only the BRAND from this beverage image. Do not use a previous guess.
Focus on visible logo/text, letter shapes, spacing and logo structure. Ignore flavor, size, colors and popularity.
Open-set brands are allowed. Preserve unreadable characters as ? in visible_text.
Return up to {self.max_brand_candidates} plausible lowercase Latin brand spellings, best first.
Do not invent extra candidates.

Return only:
{{"visible_text":"SUNST?R","brand_candidates":[
  {{"brand":"sunstar","confidence":0.88,"evidence":"brief evidence"}}
],"reason":"brief reason"}}
""".strip()
        return self._chat_json(model=self.brand_model, prompt=prompt, image_data_url=image_data_url, max_tokens=650)

    def _flavor_recheck(
        self,
        *,
        image_data_url: str,
        initial_candidate: dict,
        brand_candidates: list[str],
        search_results: list[dict],
    ) -> dict:
        useful_web = [x for x in search_results if x.get("exact_brand_match") is True][:15]
        prompt = f"""
Independently determine only the canonical FLAVOR of this beverage.
Do not assume the first-pass flavor is correct.

First pass: {_json(initial_candidate)}
Brand candidates: {_json(brand_candidates)}
Exact-brand web results: {_json(useful_web)}

Use visible flavor wording, fruit graphics and compatible web evidence.
Rules: 2+ distinct fruits -> mix; sour cherry -> cherry; any orange variant -> orange;
remove juice/drink/beverage/nectar/squash. Do not use package color alone.
If unsafe, return flavor="" and flavor_supported=false.

Return only:
{{"flavor":"orange","fruits":["orange"],"flavor_supported":true,
 "evidence":["brief evidence"],"conflicts":[],"reason":"brief reason"}}
""".strip()
        return self._chat_json(model=self.flavor_model, prompt=prompt, image_data_url=image_data_url, max_tokens=700)

    def _run_searches(self, queries: list[dict], per_brand_cap: Optional[int] = None) -> list[dict]:
        if not queries:
            return []

        brands = list(dict.fromkeys(q["brand_candidate"] for q in queries))
        cap = per_brand_cap or max(1, self.max_search_results // max(1, len(brands)))
        results, seen = [], set()

        for brand in brands:
            count = 0
            for info in (q for q in queries if q["brand_candidate"] == brand):
                if count >= cap:
                    break
                try:
                    raw = self.DDGS(timeout=10).text(
                        info["query"],
                        region=self.search_region,
                        safesearch="moderate",
                        max_results=min(self.search_results_per_query, cap - count),
                        backend=self.search_backend,
                    )
                except Exception:
                    continue

                for item in raw or []:
                    title = str(item.get("title") or "").strip()
                    url = str(item.get("href") or item.get("url") or "").strip()
                    snippet = str(item.get("body") or item.get("description") or "").strip()
                    if not (title or url or snippet):
                        continue

                    key = (brand.lower(), url.lower(), title.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append({
                        "candidate_brand": brand,
                        "query": info["query"],
                        "purpose": info["purpose"],
                        "title": title,
                        "url": url,
                        "snippet": snippet[:1400],
                        "exact_brand_match": _brand_exact_match(
                            brand, title=title, snippet=snippet, url=url
                        ),
                    })
                    count += 1
                    if count >= cap:
                        break
        return results

    def _initial_search_queries(self, brands: list[str], candidate: dict) -> list[dict]:
        raw_flavor = str(candidate.get("flavor") or "").strip()
        canonical = _normalize_flavor(raw_flavor, candidate.get("fruits"))
        flavors = list(dict.fromkeys(x for x in [raw_flavor, canonical] if x))
        size = _normalize_size(str(candidate.get("size") or ""))
        queries = []

        for brand in brands:
            b = f'"{brand}"'
            for flavor in flavors:
                if size:
                    queries.append({"brand_candidate": brand, "query": f'{b} "{flavor}" "{size}" beverage', "purpose": "brand_flavor_size"})
                queries.append({"brand_candidate": brand, "query": f'{b} "{flavor}" beverage', "purpose": "brand_flavor"})
            if size:
                queries.append({"brand_candidate": brand, "query": f'{b} "{size}" beverage', "purpose": "brand_size"})
            queries.append({"brand_candidate": brand, "query": f"{b} beverage juice", "purpose": "brand_discovery"})
        return queries

    def _flavor_search_queries(self, brands: list[str], flavor_recheck: dict, candidate: dict) -> list[dict]:
        flavor = _normalize_flavor(str(flavor_recheck.get("flavor") or ""), flavor_recheck.get("fruits"))
        if not flavor:
            return []
        size = _normalize_size(str(candidate.get("size") or ""))
        queries = []
        for brand in brands:
            b = f'"{brand}"'
            queries.append({"brand_candidate": brand, "query": f'{b} "{flavor}" beverage', "purpose": "flavor_validation"})
            if size:
                queries.append({"brand_candidate": brand, "query": f'{b} "{flavor}" "{size}" beverage', "purpose": "flavor_validation"})
        return queries

    def _size_search_queries(self, brands: list[str], flavor_recheck: dict) -> list[dict]:
        flavor = _normalize_flavor(str(flavor_recheck.get("flavor") or ""), flavor_recheck.get("fruits"))
        queries = []
        for brand in brands:
            b = f'"{brand}"'
            terms = [f'{b} "{flavor}" ml beverage', f'{b} "{flavor}" volume size'] if flavor else [f"{b} ml beverage"]
            queries.extend({"brand_candidate": brand, "query": q, "purpose": "size_recovery"} for q in terms)
        return queries

    def _recover_size(
        self,
        *,
        image_data_url: str,
        initial_candidate: dict,
        brand_candidates: list[str],
        flavor_recheck: dict,
        search_results: list[dict],
    ) -> dict:
        initial_size = _normalize_size(str(initial_candidate.get("size") or ""))
        if initial_size:
            return {
                "status": "not_needed",
                "size": initial_size,
                "size_supported": True,
                "source": "first_pass",
                "evidence": ["Valid size was already read in the first pass."],
                "conflicts": [],
                "reason": "Size recovery was not required.",
            }

        exact_web = [x for x in search_results if x.get("exact_brand_match") is True][:20]
        prompt = f"""
Recover only the exact package SIZE for this beverage.
First pass: {_json(initial_candidate)}
Brand candidates: {_json(brand_candidates)}
Flavor re-check: {_json(flavor_recheck)}
Exact-brand web results: {_json(exact_web)}

Prefer visible package volume. Web evidence is allowed only for the same brand + same flavor/variant + compatible product.
Never infer size from container proportions, nutrition text such as per-100ml, or another SKU's common size.
Normalize 1000/1500/2000ml to 1L/1.5L/2L.
If unsafe, return status="not_found", size="", size_supported=false.

Return only:
{{"status":"recovered","size":"800ml","size_supported":true,"source":"image",
 "evidence":["brief evidence"],"conflicts":[],"reason":"brief reason"}}
""".strip()
        return self._chat_json(model=self.size_model, prompt=prompt, image_data_url=image_data_url, max_tokens=700)

    def _summarize_web_support(self, brands: list[str], results: list[dict]) -> dict:
        summary = {}
        for brand in brands:
            brand_results = [x for x in results if x.get("candidate_brand") == brand]
            exact = [x for x in brand_results if x.get("exact_brand_match") is True]
            summary[brand] = {
                "result_count": len(brand_results),
                "exact_brand_match_count": len(exact),
                "exact_brand_titles": [x.get("title", "") for x in exact[:5]],
            }
        return summary

    def _final_verify(
        self,
        *,
        image_data_url: str,
        initial_candidate: dict,
        brand_recheck: dict,
        brand_candidates: list[str],
        flavor_recheck: dict,
        size_recovery: dict,
        search_queries: list[dict],
        search_results: list[dict],
    ) -> dict:
        web = {
            "search_queries": search_queries,
            "brand_support_summary": self._summarize_web_support(brand_candidates, search_results),
            "search_results": search_results,
        }
        prompt = f"""
Make the final beverage SKU decision from the image and all evidence below.
The first pass is not authoritative; correct brand, flavor or size when stronger evidence supports it.

First pass: {_json(initial_candidate)}
Brand re-check: {_json({"brand_recheck": brand_recheck, "normalized_brand_candidates": brand_candidates})}
Flavor re-check: {_json(flavor_recheck)}
Size recovery: {_json(size_recovery)}
Web evidence: {_json(web)}

Decision rules:
- Brand must be supported by visible text/logo; spelling-similar web words are not evidence.
- Flavor: 2+ fruits -> mix; sour cherry -> cherry; any orange variant -> orange; remove generic beverage words.
- Size must be exact; never infer from proportions or nutrition text.
- web_status is confirmed, inconclusive or conflicting. Missing/weak web evidence may be inconclusive and does not by itself reject strong image evidence.
- Reject if a required field is guessed, image evidence is too ambiguous, web evidence strongly conflicts, or exact size is unsafe.
- Return lowercase Latin/English semantic fields. Do not build the label; Python does that.

Return only:
{{"verdict":"accept","brand":"sunstar","flavor":"orange","size":"240ml","fruits":["orange"],
 "image_supported":true,"brand_recheck_supported":true,"flavor_recheck_supported":true,
 "size_recovery_supported":true,"web_status":"confirmed","web_supported":true,
 "brand_supported":true,"flavor_supported":true,"size_supported":true,
 "evidence":["brief evidence"],"conflicts":[],"reason":"brief final reason"}}
""".strip()
        return self._chat_json(model=self.verify_model, prompt=prompt, image_data_url=image_data_url, max_tokens=1200)

    def _unresolved(
        self,
        *,
        brand: Optional[str] = None,
        flavor: Optional[str] = None,
        size: Optional[str] = None,
        initial_candidate: Optional[dict] = None,
        brand_recheck: Optional[dict] = None,
        brand_candidates: Optional[list[str]] = None,
        flavor_recheck: Optional[dict] = None,
        size_recovery: Optional[dict] = None,
        search_queries: Optional[list[dict]] = None,
        search_results: Optional[list[dict]] = None,
        evidence: Optional[list[str]] = None,
        conflicts: Optional[list[str]] = None,
        reason: Optional[str] = None,
    ) -> UnknownBeverageResult:
        initial_candidate = initial_candidate or {}
        brand_recheck = brand_recheck or {}
        brand_candidates = brand_candidates or []
        flavor_recheck = flavor_recheck or {}
        size_recovery = size_recovery or {}

        final_brand = _compact_token(brand or "") or (brand_candidates[0] if brand_candidates else "") or _compact_token(initial_candidate.get("brand", ""))
        fruits = flavor_recheck.get("fruits") or initial_candidate.get("fruits") or []
        final_flavor = (
            _normalize_flavor(flavor or "", fruits)
            or _normalize_flavor(flavor_recheck.get("flavor", ""), flavor_recheck.get("fruits"))
            or _normalize_flavor(initial_candidate.get("flavor", ""), initial_candidate.get("fruits"))
        )
        final_size = (
            _normalize_size(size or "")
            or _normalize_size(size_recovery.get("size", ""))
            or _normalize_size(initial_candidate.get("size", ""))
        )

        if final_brand or final_flavor or final_size:
            status = "partial"
            label = f"{final_brand or 'unknownbrand'}_{final_flavor or 'unknownflavor'}_{final_size or 'unknownsize'}"
        else:
            status, label = "unresolved_unknown", None

        return UnknownBeverageResult(
            status=status,
            label=label,
            brand=final_brand or None,
            flavor=final_flavor or None,
            size=final_size or None,
            initial_candidate=initial_candidate,
            brand_recheck=brand_recheck,
            brand_candidates=brand_candidates,
            flavor_recheck=flavor_recheck,
            size_recovery=size_recovery,
            search_queries=search_queries or [],
            search_results=search_results or [],
            evidence=evidence or [],
            conflicts=conflicts or [],
            verification_reason=reason,
        )

    def classify(self, image_path: str) -> UnknownBeverageResult:
        state = {
            "initial_candidate": {}, "brand_recheck": {}, "brand_candidates": [],
            "flavor_recheck": {}, "size_recovery": {}, "search_queries": [], "search_results": [],
        }

        try:
            image = _image_to_data_url(image_path)
            initial = state["initial_candidate"] = self._identify(image)
            initial_evidence = [str(x) for x in _safe_list(initial.get("evidence"))]
            initial_conflicts = [str(x) for x in _safe_list(initial.get("conflicts"))]

            if str(initial.get("status", "")).strip().lower() != "candidate":
                return self._unresolved(
                    **state, evidence=initial_evidence, conflicts=initial_conflicts,
                    reason="The first VLM pass could not form a useful candidate."
                )

            initial_brand = _compact_token(initial.get("brand", ""))
            brand_recheck = state["brand_recheck"] = self._brand_recheck(image)
            brands = state["brand_candidates"] = _normalize_brand_candidates(
                brand_recheck.get("brand_candidates"), initial_brand, self.max_brand_candidates
            )
            if not brands:
                return self._unresolved(
                    **state,
                    evidence=initial_evidence,
                    conflicts=initial_conflicts + ["No usable brand candidate was produced."],
                    reason="Brand identity could not be narrowed to a usable candidate set.",
                )

            initial_queries = self._initial_search_queries(brands, initial)
            state["search_queries"].extend(initial_queries)
            state["search_results"].extend(self._run_searches(initial_queries))

            flavor = state["flavor_recheck"] = self._flavor_recheck(
                image_data_url=image,
                initial_candidate=initial,
                brand_candidates=brands,
                search_results=state["search_results"],
            )

            flavor_queries = self._flavor_search_queries(brands, flavor, initial)
            state["search_queries"].extend(flavor_queries)
            _merge_unique_results(
                state["search_results"],
                self._run_searches(flavor_queries, per_brand_cap=max(2, min(6, self.search_results_per_query + 1))),
            )

            initial_size = _normalize_size(initial.get("size", ""))
            if not initial_size:
                size_queries = self._size_search_queries(brands, flavor)
                state["search_queries"].extend(size_queries)
                _merge_unique_results(
                    state["search_results"],
                    self._run_searches(
                        size_queries,
                        per_brand_cap=max(2, min(8, self.max_search_results // max(1, len(brands)))),
                    ),
                )

            size_recovery = state["size_recovery"] = self._recover_size(
                image_data_url=image,
                initial_candidate=initial,
                brand_candidates=brands,
                flavor_recheck=flavor,
                search_results=state["search_results"],
            )

            verification = self._final_verify(
                image_data_url=image,
                initial_candidate=initial,
                brand_recheck=brand_recheck,
                brand_candidates=brands,
                flavor_recheck=flavor,
                size_recovery=size_recovery,
                search_queries=state["search_queries"],
                search_results=state["search_results"],
            )

            final_brand = _compact_token(verification.get("brand", ""))
            final_fruits = _normalize_fruits(verification.get("fruits")) or _normalize_fruits(flavor.get("fruits"))
            final_flavor = _normalize_flavor(verification.get("flavor") or flavor.get("flavor", ""), final_fruits)
            final_size = _normalize_size(verification.get("size") or size_recovery.get("size", ""))

            stage_evidence = [str(x) for x in _safe_list(flavor.get("evidence")) + _safe_list(size_recovery.get("evidence"))]
            final_evidence = [str(x) for x in _safe_list(verification.get("evidence"))]
            conflicts = [str(x) for x in _safe_list(verification.get("conflicts"))]
            conflicts += [str(x) for x in _safe_list(flavor.get("conflicts")) + _safe_list(size_recovery.get("conflicts"))]
            reason = str(verification.get("reason") or "Final verification rejected the candidate.")

            flavor_ok = flavor.get("flavor_supported") is True and bool(
                _normalize_flavor(flavor.get("flavor", ""), flavor.get("fruits"))
            )
            size_ok = bool(initial_size) or (
                size_recovery.get("status") == "recovered"
                and size_recovery.get("size_supported") is True
                and bool(_normalize_size(size_recovery.get("size", "")))
            )
            core_ok = all([
                verification.get("image_supported") is True,
                verification.get("brand_recheck_supported") is True,
                flavor_ok,
                size_ok,
                verification.get("brand_supported") is True,
                verification.get("flavor_supported") is True,
                verification.get("size_supported") is True,
            ])
            web_status = str(verification.get("web_status", "")).strip().lower()
            web_ok = web_status == "inconclusive" or (
                web_status == "confirmed" and verification.get("web_supported") is True
            )
            accepted = (
                str(verification.get("verdict", "")).strip().lower() == "accept"
                and core_ok and web_ok and not conflicts
                and final_brand and final_flavor and final_size
            )

            evidence = initial_evidence + stage_evidence + final_evidence
            if not accepted:
                missing = []
                if not final_brand:
                    missing.append("Final brand could not be normalized safely.")
                if not final_flavor:
                    missing.append("Final flavor could not be normalized safely.")
                if not final_size:
                    missing.append("Final package size could not be normalized safely.")
                return self._unresolved(
                    **state,
                    brand=final_brand or initial_brand or None,
                    flavor=final_flavor or None,
                    size=final_size or None,
                    evidence=evidence,
                    conflicts=initial_conflicts + conflicts + missing,
                    reason=reason,
                )

            label = f"{final_brand}_{final_flavor}_{final_size}"
            return UnknownBeverageResult(
                status="verified",
                label=label,
                brand=final_brand,
                flavor=final_flavor,
                size=final_size,
                **state,
                evidence=evidence,
                conflicts=[],
                verification_reason=reason,
            )

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            return self._unresolved(**state, conflicts=[error], reason=error)
