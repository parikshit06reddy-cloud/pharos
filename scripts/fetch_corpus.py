"""Fetch real drug-label passages from openFDA (+ RxNorm RxCUIs) into corpus/labels/*.json.

Writes the SAME shape that backend/retrieval/local_corpus.py parses, so the offline
provider works against freshly fetched data. Synthetic fixtures (e.g. examplamine, any
file marked "synthetic": true) are NEVER overwritten.

Uses only the standard library (no extra deps). openFDA data is public and is NOT
validated for clinical use.

Run: python -m scripts.fetch_corpus            # default drug set
     python -m scripts.fetch_corpus warfarin metformin
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:  # Use certifi's CA bundle if available (fixes macOS python.org SSL cert errors).
    import certifi

    _SSL_CTX: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover - certifi optional
    _SSL_CTX = None

ROOT = Path(__file__).resolve().parents[1]
# Override with CORPUS_OUT to fetch into a scratch dir (e.g. to validate without
# clobbering the curated, deterministic offline corpus).
LABELS_DIR = Path(os.getenv("CORPUS_OUT", ROOT / "corpus" / "labels"))
OPENFDA_URL = "https://api.fda.gov/drug/label.json"
RXNORM_URL = "https://rxnav.nlm.nih.gov/REST/rxcui.json"
_NOTE = (
    "Curated, abbreviated representative excerpt of public openFDA labeling. "
    "Not verbatim, not current. Not for clinical use."
)
_MAX_SECTION_CHARS = 700

# Label fields we map 1:1 into our section keys (these are openFDA field names).
SECTION_FIELDS = [
    "boxed_warning",
    "contraindications",
    "drug_interactions",
    "warnings",
    "warnings_and_cautions",
    "use_in_specific_populations",
    "dosage_and_administration",
    "geriatric_use",
    "pediatric_use",
    "pregnancy",
    "overdosage",
]

DEFAULT_DRUGS = [
    "warfarin",
    "fluconazole",
    "spironolactone",
    "lisinopril",
    "metformin",
    "isotretinoin",
    "sertraline",
    "lorazepam",
    "alprazolam",
    "diazepam",
    "acetaminophen",
    "amoxicillin",
    # Broader coverage:
    "atorvastatin",
    "clarithromycin",
    "ibuprofen",
    "tramadol",
]


def slugify(name: str) -> str:
    return name.lower().strip().replace(" ", "_").replace("/", "_").replace("-", "_")


def _get(url: str, params: dict) -> dict | None:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full, timeout=20, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:  # network blocked, 404, rate limit, etc.
        print(f"  ! request failed: {e}")
        return None


def _first_text(field) -> str:
    if isinstance(field, list):
        return " ".join(str(x) for x in field).strip()
    return str(field or "").strip()


def _abbreviate(text: str) -> str:
    text = " ".join(text.split())
    if len(text) > _MAX_SECTION_CHARS:
        text = text[:_MAX_SECTION_CHARS].rsplit(" ", 1)[0] + "…"
    return text


def rxcui_for(name: str) -> str | None:
    data = _get(RXNORM_URL, {"name": name})
    if not data:
        return None
    ids = (data.get("idGroup") or {}).get("rxnormId") or []
    return ids[0] if ids else None


def fetch_label(name: str) -> dict | None:
    query = f'openfda.generic_name:"{name}" OR openfda.brand_name:"{name}"'
    data = _get(OPENFDA_URL, {"search": query, "limit": 1})
    if not data or not data.get("results"):
        print(f"  ! no openFDA label for {name}")
        return None
    result = data["results"][0]
    openfda = result.get("openfda", {})

    sections: dict[str, str] = {}
    for field in SECTION_FIELDS:
        text = _first_text(result.get(field))
        if not text:
            continue
        key = "warnings" if field == "warnings_and_cautions" and "warnings" not in sections else field
        sections[key] = _abbreviate(text)
    if not sections:
        print(f"  ! label for {name} had none of the expected sections")
        return None

    classes = []
    for pc in ("pharm_class_epc", "pharm_class_moa", "pharm_class_cs"):
        classes += [c.lower() for c in openfda.get(pc, [])]
    rxcui = (openfda.get("rxcui") or [None])[0] or rxcui_for(name)
    generic = (openfda.get("generic_name") or [name])[0].lower()

    return {
        "drug_name": generic,
        "rxcui": rxcui,
        "classes": sorted(set(classes)),
        "source_id": f"openfda:{slugify(name)}",
        "source_version": result.get("effective_time"),
        "url": "https://labels.fda.gov/",
        "sections": sections,
        "_note": _NOTE,
    }


def _is_protected(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text()).get("synthetic"))
    except Exception:
        return False


def main(drugs: list[str]) -> int:
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    written, skipped, failed = 0, 0, 0
    for name in drugs:
        slug = slugify(name)
        path = LABELS_DIR / f"{slug}.json"
        if _is_protected(path):
            print(f"= skip {name}: synthetic fixture, never overwritten")
            skipped += 1
            continue
        print(f"- fetching {name} …")
        doc = fetch_label(name)
        if doc is None:
            failed += 1
            continue
        path.write_text(json.dumps(doc, indent=2) + "\n")
        written += 1
        time.sleep(0.3)  # be polite to the public API

    print(f"\nDone. written={written} skipped={skipped} failed={failed}")
    if written == 0 and failed > 0:
        print("No labels fetched — is the network reachable? The offline corpus is unchanged.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or DEFAULT_DRUGS))
