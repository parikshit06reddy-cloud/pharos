"""Triage / escalation (pipeline step 7) + the clinician hand-off summary.

Tiers the brief (urgent / review_recommended / informational), surfaces emergency
resources for suspected overdose/poisoning, and builds a copyable, cited synopsis.
Pharos escalates and informs — it never issues an order. See SAFETY.md §1.
"""

from __future__ import annotations

import re

from .schemas import DecisionBrief, PatientCase, SafetyFinding, Severity, TriageTier

_EMERGENCY_RE = re.compile(
    r"\b(overdose|overdosed|over-dose|poison(ing|ed)?|ingest(ed|ion)|took too (much|many)|"
    r"od'?d|toxic ingestion|swallowed (a )?bottle)\b",
    re.IGNORECASE,
)
_POISON_CONTROL = "Poison Control (US): 1-800-222-1222"
_EMERGENCY_SERVICES = "Call emergency services (e.g. 911) immediately for a suspected overdose or poisoning."


def _is_emergency(case: PatientCase) -> bool:
    return bool(_EMERGENCY_RE.search(case.question or ""))


def triage(case: PatientCase, findings: list[SafetyFinding], abstained: bool) -> dict:
    if abstained:
        return {"tier": TriageTier.informational, "resources": [], "emergency_message": ""}

    emergency = _is_emergency(case)
    has_critical = any(f.severity == Severity.critical for f in findings)
    has_actionable = any(f.severity in (Severity.serious, Severity.caution) for f in findings)

    if emergency or has_critical:
        tier = TriageTier.urgent
    elif has_actionable:
        tier = TriageTier.review_recommended
    else:
        tier = TriageTier.informational

    resources, message = [], ""
    if emergency:
        resources = [_POISON_CONTROL, _EMERGENCY_SERVICES]
        message = (
            "Possible overdose or poisoning indicated — contact Poison Control "
            "(1-800-222-1222) and emergency services immediately. "
        )
    return {"tier": tier, "resources": resources, "emergency_message": message}


def _fmt_list(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def _fmt_lab(lab) -> str:
    unit = lab.unit or ""
    return f"{lab.name}={lab.value:g}{unit}"


def build_handoff(brief: DecisionBrief, case: PatientCase) -> str:
    d = case.demographics
    lines = [
        "PHAROS DECISION BRIEF — synthetic, not for clinical use.",
        f"Candidate drug: {case.candidate_drug.name}",
        f"Triage: {brief.triage_tier.value}" + ("  | ABSTAINED" if brief.abstained else ""),
        f"Patient: age {d.age_years if d.age_years is not None else '—'}, "
        f"{d.sex or '—'}, pregnancy {d.pregnancy_status or 'n/a'}",
        f"Conditions: {_fmt_list([c.name for c in case.conditions])}",
        f"Current meds: {_fmt_list([m.name for m in case.current_medications])}",
        f"Allergies: {_fmt_list([a.substance for a in case.allergies])}",
        f"Labs: {_fmt_list([_fmt_lab(lab) for lab in case.labs])}",
        "",
        f"Answer: {brief.answer}",
    ]
    if brief.emergency_resources:
        lines += ["", "EMERGENCY RESOURCES:"] + [f" - {r}" for r in brief.emergency_resources]
    if brief.findings:
        lines += ["", "Safety flags:"]
        for f in brief.findings:
            lines.append(
                f" - [{f.severity.value.upper()}][{f.type}] {f.statement} (cite: {', '.join(f.citation_keys)})"
            )
    if brief.options:
        lines += ["", "Options to weigh (you decide):"] + [f" - {o.option}" for o in brief.options]
    lines += ["", f"Confidence: {brief.confidence.level} ({round(brief.confidence.grounded_share * 100)}% grounded)"]
    if brief.confidence.gaps:
        lines += ["Gaps:"] + [f" - {g}" for g in brief.confidence.gaps]
    if brief.citations:
        lines += ["", "Citations:"] + [
            f" - {c.citation_key}: {c.title}" + (f" ({c.url})" if c.url else "") for c in brief.citations
        ]
    return "\n".join(lines)
