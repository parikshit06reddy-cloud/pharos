"""Condition-gated boxed-warning specialist. A boxed warning is only surfaced as a finding
when it is relevant to THIS patient (e.g. a teratogen warning for a pregnant patient,
suicidality for a young patient, opioid co-prescribing when an opioid is present)."""

from __future__ import annotations

from ..schemas import SafetyFinding, Severity, Subject
from .base import SpecialistContext, excerpt

NAME = "boxed"
_OPIOIDS = {
    "morphine",
    "oxycodone",
    "hydrocodone",
    "fentanyl",
    "tramadol",
    "codeine",
    "hydromorphone",
    "methadone",
    "oxymorphone",
}


def analyze(ctx: SpecialistContext) -> list[SafetyFinding]:
    findings: list[SafetyFinding] = []
    case = ctx.case
    age = case.demographics.age_years
    pregnant = (case.demographics.pregnancy_status or "").lower() == "pregnant"
    on_opioid = any(m.name.lower() in _OPIOIDS or "opioid" in ctx.classes_of(m.name) for m in case.current_medications)

    for p in ctx.candidate_passages(("boxed_warning",)):
        low = p.text.lower()
        detail = None
        severity = Severity.serious

        if pregnant and ("teratogen" in low or "birth defect" in low or "fetal" in low or "pregnan" in low):
            detail, severity = "pregnancy / teratogenicity", Severity.critical
        elif "suicid" in low and age is not None and age < 25:
            detail, severity = f"suicidality risk in young patient (age {age:g})", Severity.serious
        elif "opioid" in low and on_opioid:
            detail, severity = "concomitant opioid use", Severity.serious

        if detail is None:
            continue
        findings.append(
            SafetyFinding(
                type="boxed_warning",
                severity=severity,
                subject=Subject(kind="boxed_warning", detail=detail),
                statement=excerpt(p.text),
                citation_keys=[p.citation_key],
                rationale=f"Boxed warning is relevant to this patient: {detail}.",
                specialist=NAME,
            )
        )
    return findings
