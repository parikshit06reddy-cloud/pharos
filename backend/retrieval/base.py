"""Retrieval adapter contract + shared text utilities.

`RetrievalProvider` is the ONLY seam that varies between offline and live (Foundry IQ).
Both providers return identical `EvidencePassage` objects, so pipeline stages 3-8 never
change when the provider changes. See ARCHITECTURE.md.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from ..schemas import EvidencePassage

_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens. The single tokenizer used by retrieval and the verifier."""
    return _WORD.findall((text or "").lower())


def normalize_name(name: str) -> str:
    """Normalize a drug name for matching: lowercase, collapse whitespace, drop salts."""
    n = (name or "").lower().strip()
    n = re.sub(r"\s+", " ", n)
    # Drop common salt/ester suffixes so "warfarin sodium" matches "warfarin".
    n = re.sub(r"\b(sodium|hydrochloride|hcl|sulfate|potassium|calcium|maleate|mesylate)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


@runtime_checkable
class RetrievalProvider(Protocol):
    def retrieve(
        self,
        query: str,
        *,
        drug_rxcuis: Sequence[str] = (),
        drug_names: Sequence[str] = (),
        sections: Sequence[str] = (),
        k: int = 8,
    ) -> list[EvidencePassage]: ...
