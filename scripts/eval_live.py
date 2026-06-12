"""Robustness probe: fetch REAL openFDA label text into a scratch corpus and re-run the case
suites against it. This proves the pipeline is not overfit to the curated corpus's phrasing.

It is informational (never hard-fails CI): real label text legitimately shifts soft numbers,
and where lexical matching on raw labels under-detects, that is an honest finding that motivates
the Foundry IQ semantic-ranker path. Writes `eval/scorecard_live.md` (gitignored; informational only).

Run: python -m scripts.eval_live   (requires network for api.fda.gov)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(os.getenv("CORPUS_OUT", str(Path(tempfile.gettempdir()) / "pharos_live_corpus")))

# Point BOTH the fetcher output and the retrieval provider at the scratch corpus BEFORE importing
# backend retrieval (so the provider loads real labels, not the committed curated corpus).
os.environ["CORPUS_OUT"] = str(SCRATCH)
os.environ["CORPUS_DIR"] = str(SCRATCH)
os.environ.setdefault("AUDIT_LOG_PATH", str(ROOT / "eval" / ".eval_live_audit.jsonl"))


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    from scripts import fetch_corpus

    # Fetch every drug the synthetic cases reference (so they have a fair chance on real labels).
    drugs = sorted(
        {
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
            "sulfamethoxazole",
            "trimethoprim",
        }
    )
    rc = fetch_corpus.main(drugs)
    if rc != 0:
        print("Live fetch unavailable (no network / api.fda.gov blocked). Skipping live probe.", file=sys.stderr)
        return 0

    # Preserve the synthetic injection fixture so the injection case still has its label.
    src = ROOT / "corpus" / "labels" / "examplamine.json"
    if src.exists():
        shutil.copy(src, SCRATCH / "examplamine.json")

    from scripts.score import CASES_DIR, HOLDOUT_DIR, _suite_table, run

    curated = run(CASES_DIR)
    holdout = run(HOLDOUT_DIR) if HOLDOUT_DIR.exists() and any(HOLDOUT_DIR.glob("*.json")) else None

    lines = [
        "# Pharos LIVE-corpus probe (real openFDA label text)",
        "",
        "Corpus: freshly fetched openFDA labels in a scratch directory "
        "(override with `CORPUS_OUT`; informational; not a CI gate). "
        "Divergences from the curated suite are expected and reported honestly — they show the "
        "pipeline is evaluated on real text, and where raw-label lexical matching under-detects, "
        "the Foundry IQ semantic ranker is the intended mitigation.",
        "",
    ]
    lines += _suite_table("Curated cases over LIVE corpus", curated)
    if holdout:
        lines += _suite_table("Held-out cases over LIVE corpus", holdout)
    out = ROOT / "eval" / "scorecard_live.md"
    out.write_text("\n".join(lines) + "\n")

    audit = Path(os.environ["AUDIT_LOG_PATH"])
    if audit.exists():
        audit.unlink()

    print("\n".join(lines))
    print(f"\nWrote {out}. Live probe is informational; curated/held-out/gate remain the CI gates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
