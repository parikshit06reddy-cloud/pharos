"""Shared context + helpers for the safety specialists.

Specialists build finding `statement`s primarily from the cited passage text so the
verifier's grounding gate can confirm them; patient-specific linkage goes in `rationale`
(which is not grounding-graded). This keeps every emitted finding grounded by design.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..retrieval.base import normalize_name
from ..schemas import EvidencePassage, PatientCase

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class SpecialistContext:
    case: PatientCase
    passages: list[EvidencePassage]
    class_index: dict[str, list[str]] = field(default_factory=dict)

    @property
    def candidate_norm(self) -> str:
        return normalize_name(self.case.candidate_drug.name)

    def passages_for(self, drug_name: str, sections: tuple[str, ...] | None = None) -> list[EvidencePassage]:
        norm = normalize_name(drug_name)
        out = []
        for p in self.passages:
            if normalize_name(p.drug_name or "") != norm:
                continue
            if sections and p.section not in sections:
                continue
            out.append(p)
        return out

    def candidate_passages(self, sections: tuple[str, ...] | None = None) -> list[EvidencePassage]:
        return self.passages_for(self.case.candidate_drug.name, sections)

    def classes_of(self, drug_name: str) -> list[str]:
        return self.class_index.get(normalize_name(drug_name), [])


def excerpt(text: str, n_sentences: int = 2, max_chars: int = 300) -> str:
    """First n sentences of a passage, capped — the grounded basis for a statement."""
    sentences = _SENTENCE_SPLIT.split(text.strip())
    out = " ".join(sentences[:n_sentences]).strip()
    if len(out) > max_chars:
        out = out[:max_chars].rsplit(" ", 1)[0] + "…"
    return out


def mentions(text: str, *terms: str) -> bool:
    """True if any term appears in the passage text. Substring match (terms are drug/class
    names long enough to be unambiguous), so singular/plural forms both match."""
    low = text.lower()
    for term in terms:
        term = (term or "").lower().strip()
        if len(term) < 4:
            continue
        if term in low:
            return True
    return False


def patient_egfr(case: PatientCase) -> float | None:
    for lab in case.labs:
        if "egfr" in lab.name.lower() or "glomerular" in lab.name.lower():
            return float(lab.value)
    return None


_THRESHOLD_RE = re.compile(r"(?:below|under|less than|<)\s*(?:an eGFR of\s*)?(\d{1,3})", re.IGNORECASE)


def egfr_threshold(text: str) -> float | None:
    """Pull a numeric eGFR threshold (e.g. 'eGFR below 30') from label text."""
    if "egfr" not in text.lower() and "glomerular" not in text.lower():
        return None
    m = _THRESHOLD_RE.search(text)
    return float(m.group(1)) if m else None
