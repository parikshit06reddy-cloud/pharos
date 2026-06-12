"""Each specialist fires on its scenario and grounds its finding in a cited passage."""

from __future__ import annotations

from backend.pipeline import run_to_brief
from tests.conftest import case_payload


def _types(case):
    brief = run_to_brief(case_payload(case))
    return brief, {f.type for f in brief.findings}


def test_interactions_fires(cases):
    _, types = _types(cases["case01_warfarin_fluconazole"])
    assert "interaction" in types


def test_contraindication_and_dose_fire(cases):
    _, types = _types(cases["case05_metformin_renal"])
    assert {"contraindication", "dose_special_population"} <= types


def test_allergy_fires(cases):
    _, types = _types(cases["case03_sulfa_allergy"])
    assert "allergy" in types


def test_duplication_fires(cases):
    _, types = _types(cases["case04_benzo_duplication"])
    assert "duplication" in types


def test_boxed_is_condition_gated_pregnancy(cases):
    brief, types = _types(cases["case06_isotretinoin_pregnancy"])
    assert {"boxed_warning", "contraindication"} <= types
    assert any(f.severity.value == "critical" for f in brief.findings)


def test_boxed_not_fired_without_trigger(cases):
    # Lorazepam has an opioid boxed warning, but the patient is on no opioid → no boxed flag.
    _, types = _types(cases["case08_lorazepam_geriatric"])
    assert "boxed_warning" not in types
    assert "dose_special_population" in types


def test_every_finding_is_grounded_and_cited(cases):
    for name, case in cases.items():
        brief = run_to_brief(case_payload(case))
        for f in brief.findings:
            assert f.citation_keys, f"{name}: finding has no citation"
            assert f.grounding.value == "GROUNDED", f"{name}: finding not grounded"
