"""Synthesizer (pipeline step 4→5). Assembles a draft answer, options, confidence, and
an answerability judgement from the specialists' findings. It does NOT decide grounding
or abstention — that is the verifier's job. Clinical answer sentences are built directly
from grounded findings so the grounding gate can confirm them.
"""

from __future__ import annotations

from .retrieval.base import normalize_name
from .schemas import Confidence, EvidencePassage, Option, PatientCase, SafetyFinding, Severity

_SEV_ORDER = {Severity.critical: 3, Severity.serious: 2, Severity.caution: 1, Severity.info: 0}

_OPTION_BY_TYPE = {
    "interaction": "Weigh an alternative agent or co-manage with monitoring/dose adjustment for the named interaction.",
    "contraindication": "Reconsider this candidate given the contraindication, or address the contraindicating factor.",
    "allergy": "Consider a non-cross-reactive alternative, or evaluate the allergy history before proceeding.",
    "duplication": "Avoid stacking same-class agents; consolidate therapy or taper the duplicate.",
    "dose_special_population": "Adjust the dose for this population and monitor per the cited label section.",
    "boxed_warning": "Review the boxed-warning conditions for this patient before initiating.",
}


def _drug_has_evidence(name: str, pool: list[EvidencePassage]) -> bool:
    norm = normalize_name(name)
    return any(normalize_name(p.drug_name or "") == norm for p in pool)


def synthesize(case: PatientCase, findings: list[SafetyFinding], pool: list[EvidencePassage]) -> dict:
    candidate = case.candidate_drug.name
    findings = sorted(findings, key=lambda f: _SEV_ORDER.get(f.severity, 0), reverse=True)

    uncovered_meds = [m.name for m in case.current_medications if not _drug_has_evidence(m.name, pool)]

    answerable = True
    answer_reason = "ok"
    uncovered_entity = ""
    if not _drug_has_evidence(candidate, pool):
        answerable, answer_reason = False, "no_evidence"
    elif not findings and uncovered_meds:
        answerable, answer_reason = False, "insufficient"
        uncovered_entity = uncovered_meds[0]

    # Clinical sentences mirror grounded findings (the verifier re-grades them).
    answer_sentences: list[dict] = []
    for f in findings:
        answer_sentences.append({"text": f.statement, "clinical": True, "citation_keys": f.citation_keys})

    if answerable and not findings:
        answer_sentences.append(
            {
                "text": f"No patient-specific safety flags were identified for {candidate} "
                "in the retrieved label sections.",
                "clinical": False,
                "citation_keys": [],
            }
        )
    if answerable:
        answer_sentences.append(
            {
                "text": "Review these findings against the full current label and the patient's "
                "complete record; Pharos informs, you decide.",
                "clinical": False,
                "citation_keys": [],
            }
        )

    options = [
        Option(
            option=_OPTION_BY_TYPE.get(f.type, "Review this finding with the cited source."),
            citation_keys=f.citation_keys,
        )
        for f in findings
    ]
    # De-duplicate options while preserving order.
    seen_opt: set[str] = set()
    deduped: list[Option] = []
    for o in options:
        if o.option not in seen_opt:
            seen_opt.add(o.option)
            deduped.append(o)
    options = deduped

    gaps: list[str] = []
    if uncovered_meds:
        gaps.append(f"No label evidence retrieved for: {', '.join(uncovered_meds)}.")
    gaps.append("Offline corpus is a curated, abbreviated subset of public FDA labeling.")

    return {
        "answerable": answerable,
        "answer_reason": answer_reason,
        "uncovered_entity": uncovered_entity,
        "findings": findings,
        "options": options,
        "answer_sentences": answer_sentences,
        "confidence": Confidence(level="moderate", grounded_share=0.0, gaps=gaps),
    }
