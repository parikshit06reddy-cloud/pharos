"""Prompt-injection guard (pipeline step 3).

Retrieved and external text is DATA, not instructions. This guard scans every passage,
strips instruction-like sentences, and flags that an attempt occurred. Specialists only
ever see cleaned text. See SAFETY.md §4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import EvidencePassage

# Phrases that mark a sentence as an instruction to the model rather than clinical content.
_INJECTION_MARKERS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"disregard (the )?(previous|prior|above)",
    r"system note for the ai",
    r"system prompt",
    r"reveal your (system )?prompt",
    r"you are (now )?an? ",
    r"tell the (clinician|user|doctor) (that )?(this|it) is (completely )?safe",
    r"safe at any dose",
    r"no overdose is possible",
    r"act as",
    r"override (the )?safety",
    r"do not (flag|warn|mention)",
]
_MARKER_RE = re.compile("|".join(f"(?:{m})" for m in _INJECTION_MARKERS), re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Detection:
    citation_key: str
    snippet: str


def _clean(text: str) -> tuple[str, list[str]]:
    """Return (cleaned_text, stripped_sentences)."""
    kept, stripped = [], []
    for sentence in _SENTENCE_SPLIT.split(text or ""):
        if sentence and _MARKER_RE.search(sentence):
            stripped.append(sentence.strip())
        elif sentence:
            kept.append(sentence)
    return " ".join(kept).strip(), stripped


def scan_text(text: str) -> bool:
    """True if the free text contains an injection attempt (e.g. a malicious question)."""
    return bool(_MARKER_RE.search(text or ""))


def scan_passages(passages: list[EvidencePassage]) -> tuple[list[EvidencePassage], list[Detection]]:
    """Strip injection sentences from every passage; return cleaned passages + detections."""
    cleaned: list[EvidencePassage] = []
    detections: list[Detection] = []
    for p in passages:
        new_text, stripped = _clean(p.text)
        if stripped:
            detections.append(Detection(citation_key=p.citation_key, snippet=stripped[0][:160]))
            p = p.model_copy(update={"text": new_text})
        cleaned.append(p)
    return cleaned, detections
