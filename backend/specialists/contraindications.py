"""Contraindication specialist — pregnancy, renal threshold, and condition matches in
the candidate's contraindications text. Pregnancy contraindications are critical; others
are serious."""

from __future__ import annotations

from ..schemas import SafetyFinding, Severity, Subject
from .base import SpecialistContext, egfr_threshold, excerpt, mentions, patient_egfr

NAME = "contraindications"


def analyze(ctx: SpecialistContext) -> list[SafetyFinding]:
    findings: list[SafetyFinding] = []
    case = ctx.case
    pregnant = (case.demographics.pregnancy_status or "").lower() == "pregnant"
    egfr = patient_egfr(case)

    for p in ctx.candidate_passages(("contraindications",)):
        low = p.text.lower()
        detail = None
        severity = Severity.serious

        if pregnant and ("pregnan" in low or "teratogen" in low or "fetal" in low):
            detail, severity = "pregnancy", Severity.critical
        else:
            thr = egfr_threshold(p.text)
            if egfr is not None and thr is not None and egfr < thr:
                detail, severity = f"renal impairment (eGFR {egfr:g} < {thr:g})", Severity.serious
            else:
                for cond in case.conditions:
                    if mentions(p.text, cond.name):
                        detail, severity = cond.name, Severity.serious
                        break
        if detail is None:
            continue
        findings.append(
            SafetyFinding(
                type="contraindication",
                severity=severity,
                subject=Subject(kind="contraindication", detail=detail),
                statement=excerpt(p.text),
                citation_keys=[p.citation_key],
                rationale=f"Applies to this patient via: {detail}.",
                specialist=NAME,
            )
        )
    return findings
