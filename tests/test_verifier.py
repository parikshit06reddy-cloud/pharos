"""The grounding gate — the safety core. Tested adversarially: a confident, ungrounded
claim that cites a REAL passage must be dropped, the grounded share must fall, and the
brief must abstain. This proves the gate bites rather than rubber-stamps."""

from __future__ import annotations

from backend import verifier
from backend.schemas import Confidence, EvidencePassage, Grounding, SafetyFinding, Subject

_PASSAGE = EvidencePassage(
    citation_key="warfarin:drug_interactions",
    source_id="openfda:warfarin",
    title="warfarin — drug interactions",
    section="drug_interactions",
    drug_name="warfarin",
    text=(
        "Inhibitors of CYP2C9 such as fluconazole can increase warfarin exposure, prolong "
        "prothrombin time, and elevate INR, increasing the risk of bleeding."
    ),
)


def _grounded_finding() -> SafetyFinding:
    return SafetyFinding(
        type="interaction",
        subject=Subject(interacting_with="fluconazole"),
        statement="Fluconazole can increase warfarin exposure, prolong prothrombin time, and elevate INR.",
        citation_keys=["warfarin:drug_interactions"],
    )


def _fabricated_finding() -> SafetyFinding:
    # Cites a real passage but the claim is unsupported by its text.
    return SafetyFinding(
        type="interaction",
        subject=Subject(interacting_with="fluconazole"),
        statement="This combination is completely harmless and guaranteed safe forever; no monitoring needed.",
        citation_keys=["warfarin:drug_interactions"],
    )


def test_ungrounded_claim_dropped_and_share_drops():
    draft = {
        "answerable": True,
        "answer_reason": "ok",
        "uncovered_entity": "",
        "findings": [_grounded_finding(), _fabricated_finding()],
        "options": [],
        "answer_sentences": [
            {"text": _grounded_finding().statement, "clinical": True, "citation_keys": ["warfarin:drug_interactions"]},
            {
                "text": "This combination is completely harmless and guaranteed safe forever.",
                "clinical": True,
                "citation_keys": ["warfarin:drug_interactions"],
            },
            {
                "text": "There is absolutely no need to monitor anything ever again.",
                "clinical": True,
                "citation_keys": ["warfarin:drug_interactions"],
            },
        ],
        "confidence": Confidence(),
    }
    out = verifier.verify(draft, [_PASSAGE], drug_terms={"warfarin", "fluconazole"})

    kept_statements = [f.statement for f in out["findings"]]
    assert len(out["findings"]) == 1, "fabricated finding should be dropped"
    assert "harmless" not in " ".join(kept_statements).lower()
    assert out["confidence"].grounded_share < 0.6
    assert out["abstained"] is True


def test_claim_with_unresolvable_citation_is_unsupported():
    f = SafetyFinding(type="interaction", statement="Anything at all.", citation_keys=["does:not_exist"])
    assert verifier.classify(f.statement, f.citation_keys, {}) == Grounding.unsupported


def test_grounded_only_draft_does_not_abstain():
    draft = {
        "answerable": True,
        "answer_reason": "ok",
        "uncovered_entity": "",
        "findings": [_grounded_finding()],
        "options": [],
        "answer_sentences": [
            {"text": _grounded_finding().statement, "clinical": True, "citation_keys": ["warfarin:drug_interactions"]},
        ],
        "confidence": Confidence(),
    }
    out = verifier.verify(draft, [_PASSAGE], drug_terms={"warfarin"})
    assert out["abstained"] is False
    assert out["findings"][0].grounding == Grounding.grounded
    assert out["confidence"].grounded_share == 1.0


def test_no_evidence_draft_abstains():
    draft = {
        "answerable": False,
        "answer_reason": "no_evidence",
        "uncovered_entity": "",
        "findings": [],
        "options": [],
        "answer_sentences": [],
        "confidence": Confidence(),
    }
    out = verifier.verify(draft, [], drug_terms=set())
    assert out["abstained"] is True
    assert "reliable information" in out["answer"].lower()
