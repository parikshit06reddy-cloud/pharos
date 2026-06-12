"""Drug-drug interaction specialist. Matches a current medication BY NAME in the
candidate's interaction text (or vice-versa) — class-level overlap is handled by the
duplication specialist, so this one stays specific to named pairs."""

from __future__ import annotations

from ..retrieval.base import normalize_name
from ..schemas import SafetyFinding, Severity, Subject
from .base import SpecialistContext, excerpt, mentions

NAME = "interactions"


def analyze(ctx: SpecialistContext) -> list[SafetyFinding]:
    findings: list[SafetyFinding] = []
    cand = ctx.case.candidate_drug.name
    cand_int = ctx.candidate_passages(("drug_interactions",))
    seen: set[str] = set()

    for med in ctx.case.current_medications:
        med_norm = normalize_name(med.name)
        if med_norm == ctx.candidate_norm or med_norm in seen:
            continue
        hit = next((p for p in cand_int if mentions(p.text, med.name)), None)
        if hit is None:
            hit = next((p for p in ctx.passages_for(med.name, ("drug_interactions",)) if mentions(p.text, cand)), None)
        if hit is None:
            continue
        seen.add(med_norm)
        findings.append(
            SafetyFinding(
                type="interaction",
                severity=Severity.serious,
                subject=Subject(kind="interaction", interacting_with=med.name),
                statement=excerpt(hit.text),
                citation_keys=[hit.citation_key],
                rationale=f"Patient is currently taking {med.name}; candidate drug is {cand}.",
                specialist=NAME,
            )
        )
    return findings
