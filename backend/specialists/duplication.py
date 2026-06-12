"""Therapeutic-duplication specialist. Flags when the candidate and a current medication
share a therapeutic class, citing a candidate passage that names that class."""

from __future__ import annotations

from ..retrieval.base import normalize_name
from ..schemas import SafetyFinding, Severity, Subject
from .base import SpecialistContext, excerpt, mentions

NAME = "duplication"


def analyze(ctx: SpecialistContext) -> list[SafetyFinding]:
    findings: list[SafetyFinding] = []
    cand_classes = ctx.classes_of(ctx.case.candidate_drug.name)
    if not cand_classes:
        return findings
    passages = ctx.candidate_passages(("warnings", "drug_interactions", "boxed_warning"))
    seen: set[str] = set()

    for med in ctx.case.current_medications:
        med_norm = normalize_name(med.name)
        if med_norm == ctx.candidate_norm or med_norm in seen:
            continue
        shared = [c for c in cand_classes if c in ctx.classes_of(med.name)]
        if not shared:
            continue
        # Cite a candidate passage that actually names the shared class (so it grounds).
        hit = None
        cls = None
        for c in shared:
            head = c.split()[0]  # e.g. "benzodiazepine" from "benzodiazepine"
            hit = next((p for p in passages if mentions(p.text, c, head)), None)
            if hit:
                cls = c
                break
        if hit is None:
            continue
        seen.add(med_norm)
        findings.append(
            SafetyFinding(
                type="duplication",
                severity=Severity.serious,
                subject=Subject(kind="duplication", interacting_with=med.name, detail=cls),
                statement=excerpt(hit.text),
                citation_keys=[hit.citation_key],
                rationale=f"Both {ctx.case.candidate_drug.name} and {med.name} are in the {cls} class.",
                specialist=NAME,
            )
        )
    return findings
