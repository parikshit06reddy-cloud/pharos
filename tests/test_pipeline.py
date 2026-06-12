"""Pipeline-level invariants: event stream shape and brief assembly."""

from __future__ import annotations

from backend.pipeline import run_pipeline, run_to_brief
from tests.conftest import case_payload


def test_run_pipeline_yields_expected_events(cases):
    events = [ev["event"] for ev in run_pipeline(case_payload(cases["case01_warfarin_fluconazole"]))]
    assert events[0] == "intake"
    assert "retrieval" in events and "injection_scan" in events
    assert events.count("specialist") == 6
    assert events[-1] == "brief"


def test_verifier_event_surfaces_critic_filtering(cases):
    """The verifier (critic) step exposes how many candidate findings it considered/kept/dropped,
    so the reasoning is visible in the UI."""
    verifier_ev = next(
        ev for ev in run_pipeline(case_payload(cases["case01_warfarin_fluconazole"])) if ev["event"] == "verifier"
    )
    d = verifier_ev["data"]
    assert "findings_considered" in d and "findings_kept" in d and "dropped_unsupported" in d
    assert d["dropped_unsupported"] == d["findings_considered"] - d["findings_kept"]
    assert d["dropped_unsupported"] >= 0


def test_brief_citations_resolve_to_findings(cases):
    brief = run_to_brief(case_payload(cases["case05_metformin_renal"]))
    cited_keys = {c.citation_key for c in brief.citations}
    used_keys = {k for f in brief.findings for k in f.citation_keys}
    assert used_keys <= cited_keys, "every finding citation must appear in the brief's citation list"


def test_abstain_case_has_no_options(cases):
    brief = run_to_brief(case_payload(cases["case11_abstain_insufficient"]))
    assert brief.abstained is True
    assert brief.options == []
    assert "abstain" in brief.answer.lower() or "don't have" in brief.answer.lower()


def test_audit_row_written_per_run(cases):
    from backend.governance import audit_log

    audit_log.reset()
    run_to_brief(case_payload(cases["case01_warfarin_fluconazole"]))
    rows = audit_log.entries()
    assert len(rows) == 1
    assert rows[0]["candidate_drug"] == "fluconazole"
    assert "question" not in rows[0]  # no PHI / free text persisted
