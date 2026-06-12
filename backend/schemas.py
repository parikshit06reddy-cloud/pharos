"""Pydantic v2 data contracts shared across every pipeline stage.

The `citation_key` on an `EvidencePassage` is the contract between retrieval, the
specialists, and the verifier: a finding may only stand if its citation_keys resolve
to a retrieved passage. See ARCHITECTURE.md.
"""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    info = "info"
    caution = "caution"
    serious = "serious"
    critical = "critical"


class Grounding(str, Enum):
    grounded = "GROUNDED"
    inferred = "INFERRED"
    unsupported = "UNSUPPORTED"


class TriageTier(str, Enum):
    urgent = "urgent"
    review_recommended = "review_recommended"
    informational = "informational"


# --- intake / patient context -------------------------------------------------
class Consent(BaseModel):
    synthetic: bool = False
    no_phi: bool = False


class Demographics(BaseModel):
    age_years: float | None = None
    sex: str | None = None
    pregnancy_status: str | None = None


class Condition(BaseModel):
    name: str


class Medication(BaseModel):
    name: str
    rxcui: str | None = None


class Allergy(BaseModel):
    substance: str


class Lab(BaseModel):
    name: str
    value: float
    unit: str | None = None


class Drug(BaseModel):
    name: str
    rxcui: str | None = None


class PatientCase(BaseModel):
    case_id: str = Field(default_factory=lambda: f"case_{uuid.uuid4().hex[:8]}")
    session_id: str | None = None
    demographics: Demographics = Field(default_factory=Demographics)
    conditions: list[Condition] = Field(default_factory=list)
    current_medications: list[Medication] = Field(default_factory=list)
    allergies: list[Allergy] = Field(default_factory=list)
    labs: list[Lab] = Field(default_factory=list)
    candidate_drug: Drug
    question: str = ""
    consent: Consent = Field(default_factory=Consent)


# --- evidence -----------------------------------------------------------------
class EvidencePassage(BaseModel):
    citation_key: str
    source_id: str
    source_type: str = "fda_label"
    title: str
    section: str
    drug_name: str | None = None
    drug_rxcui: str | None = None
    text: str
    source_version: str | None = None
    url: str | None = None
    provider: str = "local_corpus"


# --- findings / brief ---------------------------------------------------------
class Subject(BaseModel):
    """What a finding is *about* (used for de-duplication and conflict detection)."""

    kind: str | None = None
    interacting_with: str | None = None
    detail: str | None = None


class SafetyFinding(BaseModel):
    finding_id: str = Field(default_factory=lambda: f"f_{uuid.uuid4().hex[:8]}")
    type: str
    severity: Severity = Severity.caution
    subject: Subject = Field(default_factory=Subject)
    statement: str
    citation_keys: list[str] = Field(default_factory=list)
    grounding: Grounding = Grounding.inferred
    rationale: str | None = None
    specialist: str = ""


class Option(BaseModel):
    option: str
    citation_keys: list[str] = Field(default_factory=list)


class Confidence(BaseModel):
    level: str = "moderate"  # low | moderate | high
    grounded_share: float = 0.0
    gaps: list[str] = Field(default_factory=list)


class DecisionBrief(BaseModel):
    case_id: str
    model_version: str = "pharos-0.1.0"
    latency_ms: int = 0
    triage_tier: TriageTier = TriageTier.informational
    abstained: bool = False
    answer: str = ""
    findings: list[SafetyFinding] = Field(default_factory=list)
    options: list[Option] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=Confidence)
    handoff_summary: str = ""
    citations: list[EvidencePassage] = Field(default_factory=list)
    emergency_resources: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Research prototype — not medical advice, not a cleared medical device.",
            "Reasoning reflects curated/abbreviated public FDA label excerpts, not a full interaction database.",
        ]
    )
    safety_flags: dict = Field(default_factory=dict)
