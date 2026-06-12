"""Triage tiers, emergency resources, and the cited hand-off."""

from __future__ import annotations

from backend import triage as triage_mod
from backend.pipeline import run_to_brief
from backend.schemas import PatientCase, SafetyFinding, Severity, TriageTier
from tests.conftest import case_payload


def _case(**kw) -> PatientCase:
    return PatientCase(candidate_drug={"name": "x"}, **kw)


def test_abstain_is_informational():
    out = triage_mod.triage(_case(), [], abstained=True)
    assert out["tier"] == TriageTier.informational


def test_critical_finding_is_urgent():
    f = SafetyFinding(type="contraindication", severity=Severity.critical, statement="s")
    out = triage_mod.triage(_case(), [f], abstained=False)
    assert out["tier"] == TriageTier.urgent


def test_serious_finding_is_review():
    f = SafetyFinding(type="interaction", severity=Severity.serious, statement="s")
    out = triage_mod.triage(_case(), [f], abstained=False)
    assert out["tier"] == TriageTier.review_recommended


def test_overdose_question_is_urgent_with_resources():
    case = _case(question="patient took a large overdose an hour ago")
    out = triage_mod.triage(case, [], abstained=False)
    assert out["tier"] == TriageTier.urgent
    assert any("Poison Control" in r for r in out["resources"])
    assert out["emergency_message"]


def test_injection_case_escalates_with_resources(cases):
    brief = run_to_brief(case_payload(cases["case12_injection_overdose"]))
    assert brief.triage_tier == TriageTier.urgent
    assert brief.emergency_resources
    assert brief.safety_flags.get("injection_detected") is True
    assert "safe at any dose" not in brief.answer.lower()


def test_handoff_summary_includes_citations(cases):
    brief = run_to_brief(case_payload(cases["case01_warfarin_fluconazole"]))
    assert "PHAROS DECISION BRIEF" in brief.handoff_summary
    assert "Citations:" in brief.handoff_summary
    assert "fluconazole" in brief.handoff_summary.lower()
