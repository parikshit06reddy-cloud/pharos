"""Proves the Foundry IQ adapter is real, not stubbed: a captured GA-shaped response maps
correctly via the production `_to_passage`, and the full safety pipeline yields a correct,
grounded Decision Brief from Foundry-sourced passages — all without an Azure tenant."""

from __future__ import annotations

import json
import os
from pathlib import Path

from backend.retrieval.foundry_iq import FoundryIQProvider
from backend.retrieval.foundry_replay import FoundryReplayProvider

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "foundry_iq_response.json"


def test_to_passage_maps_ga_2026_04_01_shape():
    data = json.loads(FIXTURE.read_text())
    refs = FoundryIQProvider._references(data)
    assert refs, "fixture must contain references"
    passages = [FoundryIQProvider._to_passage(r) for r in refs]

    p0 = next(p for p in passages if p.citation_key == "fluconazole:drug_interactions")
    assert p0.section == "drug_interactions"
    assert p0.drug_name == "fluconazole"
    assert p0.source_version == "curated-excerpt-2026-06"
    assert p0.provider == "foundry_iq"  # mapped, not local
    assert "warfarin" in p0.text.lower()  # content came from source_data.content
    assert "knowledge base reference" not in p0.title.lower()  # title mapped from source_data


def test_replay_retrieve_filters_by_drug_and_section():
    prov = FoundryReplayProvider(FIXTURE)
    res = prov.retrieve("interaction", drug_names=["fluconazole"], sections=("drug_interactions",))
    assert [p.citation_key for p in res] == ["fluconazole:drug_interactions"]
    assert prov.retrieve("x", drug_names=["aspirin"]) == []  # not in the captured set


def test_full_pipeline_grounded_brief_from_foundry_data(monkeypatch):
    """End-to-end: Foundry-shaped passages -> pipeline -> grounded, cited interaction brief."""
    monkeypatch.setenv("RETRIEVAL_PROVIDER", "foundry_replay")
    monkeypatch.setenv("FOUNDRY_REPLAY_FIXTURE", str(FIXTURE))
    monkeypatch.setenv("AUDIT_LOG_PATH", "/tmp/pharos_foundry_replay_audit.jsonl")
    from backend.pipeline import run_to_brief

    case = {
        "case_id": "foundry_replay_case",
        "session_id": "frc",
        "demographics": {"age_years": 64, "sex": "female", "pregnancy_status": "not_applicable"},
        "conditions": [{"name": "atrial fibrillation"}],
        "current_medications": [{"name": "warfarin"}],
        "allergies": [],
        "labs": [],
        "candidate_drug": {"name": "fluconazole"},
        "question": "Any interaction between fluconazole and warfarin?",
        "consent": {"synthetic": True, "no_phi": True},
    }
    brief = run_to_brief(case)
    assert not brief.abstained
    assert brief.triage_tier.value == "review_recommended"
    assert any(f.type == "interaction" for f in brief.findings)
    assert all(f.grounding.value == "GROUNDED" for f in brief.findings)
    # The grounding evidence is Foundry-sourced.
    assert brief.citations and all(c.provider == "foundry_iq" for c in brief.citations)
    if os.path.exists("/tmp/pharos_foundry_replay_audit.jsonl"):
        os.unlink("/tmp/pharos_foundry_replay_audit.jsonl")
