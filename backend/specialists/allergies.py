"""Allergy / cross-sensitivity specialist. Maps a patient's stated allergy (incl. common
cross-reactive classes) onto a hypersensitivity statement in the candidate's label."""

from __future__ import annotations

from ..retrieval.base import normalize_name
from ..schemas import SafetyFinding, Severity, Subject
from .base import SpecialistContext, excerpt, mentions

NAME = "allergies"

# Cross-reactivity expansions: a stated allergy implies these label terms.
_CROSS: dict[str, list[str]] = {
    "sulfa": ["sulfonamide", "sulfonamides"],
    "sulfa drugs": ["sulfonamide", "sulfonamides"],
    "penicillin": ["penicillin", "penicillins", "beta-lactam"],
    "amoxicillin": ["penicillin", "penicillins", "beta-lactam"],
    "cephalosporin": ["beta-lactam", "cephalosporin"],
    "aspirin": ["nsaid", "salicylate"],
}


def analyze(ctx: SpecialistContext) -> list[SafetyFinding]:
    findings: list[SafetyFinding] = []
    passages = ctx.candidate_passages(("contraindications", "warnings"))
    seen: set[str] = set()

    for allergy in ctx.case.allergies:
        sub = allergy.substance
        if normalize_name(sub) in seen:
            continue
        terms = [sub, *_CROSS.get(normalize_name(sub), [])]
        hit = next(
            (
                p
                for p in passages
                if mentions(p.text, *terms) and ("hypersensitiv" in p.text.lower() or "allerg" in p.text.lower())
            ),
            None,
        )
        if hit is None:
            continue
        seen.add(normalize_name(sub))
        findings.append(
            SafetyFinding(
                type="allergy",
                severity=Severity.serious,
                subject=Subject(kind="allergy", detail=sub),
                statement=excerpt(hit.text),
                citation_keys=[hit.citation_key],
                rationale=f"Patient reports a {sub} allergy; the candidate label flags cross-sensitivity.",
                specialist=NAME,
            )
        )
    return findings
