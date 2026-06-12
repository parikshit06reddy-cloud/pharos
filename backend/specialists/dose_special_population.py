"""Dose / special-population specialist — renal, geriatric, and pediatric dose-adjustment
signals in the candidate's label, gated by the patient's age and renal function."""

from __future__ import annotations

from ..schemas import SafetyFinding, Severity, Subject
from .base import SpecialistContext, excerpt, patient_egfr

NAME = "dose_special_population"
_RENAL_EGFR_REVIEW = 45.0  # reassess/adjust at or below this eGFR


def analyze(ctx: SpecialistContext) -> list[SafetyFinding]:
    findings: list[SafetyFinding] = []
    case = ctx.case
    age = case.demographics.age_years
    egfr = patient_egfr(case)

    def add(passage, detail):
        findings.append(
            SafetyFinding(
                type="dose_special_population",
                severity=Severity.serious,
                subject=Subject(kind="dose_special_population", detail=detail),
                statement=excerpt(passage.text),
                citation_keys=[passage.citation_key],
                rationale=f"Dose adjustment relevant for this patient: {detail}.",
                specialist=NAME,
            )
        )

    # Renal
    if egfr is not None and egfr <= _RENAL_EGFR_REVIEW:
        for p in ctx.candidate_passages(("use_in_specific_populations", "dosage_and_administration")):
            if "egfr" in p.text.lower() or "renal" in p.text.lower():
                add(p, f"renal function (eGFR {egfr:g})")
                break

    # Geriatric
    if age is not None and age >= 65:
        ger = ctx.candidate_passages(("geriatric_use",))
        if ger:
            add(ger[0], f"geriatric (age {age:g})")

    # Pediatric
    if age is not None and age < 18:
        ped = ctx.candidate_passages(("pediatric_use",))
        if ped:
            add(ped[0], f"pediatric (age {age:g})")

    return findings
