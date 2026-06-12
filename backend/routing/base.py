"""Routing adapter contract.

A `RouterProvider` ranks specialists for a case and returns `SpecialistMatch` objects
with a grounded rationale (which expertise terms matched). Routing always produces
suggestions for a human to confirm — never an automatic, unreviewable assignment
(clinician-in-command).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class RoutingContext:
    question: str = ""
    candidate_drug: str = ""
    drug_terms: list[str] = field(default_factory=list)
    drug_classes: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    finding_types: list[str] = field(default_factory=list)
    finding_text: str = ""
    emergency: bool = False

    def query_text(self) -> str:
        parts = [
            self.question,
            self.candidate_drug,
            *self.drug_terms,
            *self.drug_classes,
            *self.conditions,
            *self.finding_types,
            self.finding_text,
        ]
        return " ".join(p for p in parts if p).lower()


@dataclass
class SpecialistMatch:
    specialist_id: int
    name: str
    specialty: str
    score: float  # 0..1, relative confidence
    matched_terms: list[str] = field(default_factory=list)
    rationale: str = ""
    capacity: int = 0
    current_load: int = 0
    available: bool = True

    def as_dict(self) -> dict:
        return {
            "specialist_id": self.specialist_id,
            "name": self.name,
            "specialty": self.specialty,
            "score": self.score,
            "matched_terms": self.matched_terms,
            "rationale": self.rationale,
            "capacity": self.capacity,
            "current_load": self.current_load,
            "available": self.available,
        }


@runtime_checkable
class RouterProvider(Protocol):
    def route(self, context: RoutingContext, specialists: list[dict], *, top_n: int = 5) -> list[SpecialistMatch]: ...
