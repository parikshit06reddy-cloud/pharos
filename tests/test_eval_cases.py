"""Parametrized check that every synthetic case matches its documented expected behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.pipeline import run_to_brief

CASES_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic_cases"
CASE_FILES = sorted(CASES_DIR.glob("case*.json"))


@pytest.mark.parametrize("path", CASE_FILES, ids=[p.stem for p in CASE_FILES])
def test_case_matches_expected(path):
    case = json.loads(path.read_text())
    exp = case["_expected"]
    payload = {k: v for k, v in case.items() if k != "_expected"}
    brief = run_to_brief(payload)

    assert brief.abstained == exp["abstain"]
    assert brief.triage_tier.value == exp["triage"]
    found = {f.type for f in brief.findings}
    for want in exp.get("flags", []):
        assert want in found, f"missing expected flag {want}; got {found}"
    assert bool(brief.safety_flags.get("injection_detected")) == exp["injection"]
    if not brief.abstained:
        assert brief.confidence.grounded_share == 1.0


def test_twelve_cases_present():
    assert len(CASE_FILES) == 12
