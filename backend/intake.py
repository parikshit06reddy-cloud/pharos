"""Intake / de-identification (pipeline step 1).

Enforces the consent gate (synthetic + no-PHI), scrubs PII from free text, drops
identity-named fields, and validates the raw payload into a `PatientCase`. Each
redaction is recorded by *type*, never by value. Privacy by design (SAFETY.md §5).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from .schemas import PatientCase

# Identity-named fields that must never be processed or persisted.
_IDENTITY_FIELDS = {
    "patient_name",
    "name",
    "mrn",
    "medical_record_number",
    "ssn",
    "dob",
    "date_of_birth",
    "address",
    "phone",
    "email",
    "insurance_id",
}

_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("phone", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("mrn", re.compile(r"\bMRN[:#\s-]*\d+\b", re.IGNORECASE)),
    ("dob", re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")),
    ("long_id", re.compile(r"\b[A-Z0-9]{10,}\b")),
]


class ConsentError(ValueError):
    """Raised when the synthetic + no-PHI consent gate is not satisfied."""


@dataclass
class IntakeResult:
    case: PatientCase
    redactions: list[str] = field(default_factory=list)
    rxcui_resolved: bool = False


def _scrub_text(text: str, redactions: list[str]) -> str:
    if not text:
        return text
    out = text
    for kind, pat in _PII_PATTERNS:
        if pat.search(out):
            redactions.append(kind)
            out = pat.sub("[REDACTED]", out)
    return out


def run_intake(raw_case: dict) -> IntakeResult:
    raw = copy.deepcopy(raw_case or {})
    redactions: list[str] = []

    # 1) Consent gate — both must be true or nothing is processed.
    consent = raw.get("consent") or {}
    if not (consent.get("synthetic") and consent.get("no_phi")):
        raise ConsentError(
            "Consent gate not satisfied: consent.synthetic and consent.no_phi must both be true. "
            "Pharos processes synthetic, no-PHI cases only."
        )

    # 2) Drop identity-named fields.
    for fld in list(raw.keys()):
        if fld.lower() in _IDENTITY_FIELDS:
            raw.pop(fld, None)
            redactions.append(f"field:{fld.lower()}")

    # 3) Scrub PII from free text fields.
    if "question" in raw:
        raw["question"] = _scrub_text(str(raw.get("question") or ""), redactions)

    # 4) Validate into the typed case (Pydantic strips unknown identity fields too).
    case = PatientCase.model_validate(raw)

    # Offline mode performs no live RxNorm resolution.
    return IntakeResult(case=case, redactions=sorted(set(redactions)), rxcui_resolved=False)
