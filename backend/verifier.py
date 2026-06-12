"""Verifier — the grounding gate + abstention (pipeline step 5).

For every clinical sentence, classify it GROUNDED / INFERRED / UNSUPPORTED against its
cited passage; drop UNSUPPORTED findings; compute the grounded share; ABSTAIN when the
question is unanswerable, the grounded share is below threshold, or sources conflict.
This is the safety core: Pharos never emits an ungrounded clinical claim, and never
fabricates a citation.

Grounding is measured by lexical overlap between the claim and its cited passage. We
deliberately do NOT require the drug name to appear in the snippet, because FDA section
text frequently refers to the drug by class or as "this drug"; the drug linkage is
already established by retrieval (the passage's drug_name).
"""

from __future__ import annotations

import os
import re

from .retrieval.base import tokenize
from .schemas import Confidence, EvidencePassage, Grounding, SafetyFinding

GROUNDING_THRESHOLD = float(os.getenv("GROUNDING_THRESHOLD", "0.6"))
GROUNDED_AT = float(os.getenv("GROUNDED_AT", "0.45"))
INFERRED_AT = float(os.getenv("INFERRED_AT", "0.2"))

_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "with",
    "for",
    "is",
    "are",
    "may",
    "be",
    "this",
    "that",
    "at",
    "on",
    "by",
    "as",
    "patient",
    "drug",
}
_AVOID = {"contraindicated", "avoid", "not", "interact", "interaction", "warning", "risk", "hyperkalemia"}

# Contradiction guard: a claim that ASSERTS safety / no-risk while citing RISK-bearing evidence is a
# false-reassurance fabrication (e.g. "fluconazole does not interact with warfarin; no INR monitoring"
# citing the interaction warning). Pure lexical overlap would call that GROUNDED because the words
# match — so we explicitly catch the inversion. This can only make the gate STRICTER (force UNSUPPORTED);
# it never keeps a claim the overlap test would have dropped.
_SAFETY_ASSERTION = re.compile(
    r"(completely safe|perfectly safe|totally safe|safe at any|safe to (use|take) at any|"
    r"harmless|no (known )?(interaction|interactions|risk|risks|monitoring|need|adverse|side)|"
    r"does not (interact|require|cause|pose)|do not (interact|need)|not contraindicated|"
    r"never (causes?|harm|interacts?)|zero (side effects|risk)|requires? no monitoring|"
    r"no (dose )?adjustment is ever|no overdose)",
    re.IGNORECASE,
)
_RISK_EVIDENCE = re.compile(
    r"(contraindicat|interact|\brisk\b|monitor|avoid|warning|boxed|fatal|death|hyperkalemia|"
    r"bleeding|hemorrhage|teratogen|birth defect|lactic acidosis|prolong|hypersensitiv|"
    r"suicidal|respiratory depression|overdose|toxic)",
    re.IGNORECASE,
)


def _content(text: str) -> set[str]:
    return {t for t in tokenize(text) if t not in _STOP and len(t) > 2}


def _overlap(statement: str, passage_text: str, exclude: frozenset[str] = frozenset()) -> float:
    # Exclude the cited drug's own name: retrieval already established the drug linkage, so
    # grounding must come from CLINICAL content, not from the claim merely naming the drug.
    # (Otherwise an off-topic claim like "drug X cures hay fever" gets free overlap from "X".)
    s = _content(statement) - exclude
    if not s:
        return 0.0
    return len(s & (_content(passage_text) - exclude)) / len(s)


def _contradicts(statement: str, cited: list[EvidencePassage]) -> bool:
    """True if the claim asserts safety/no-risk but its cited evidence is risk-bearing."""
    if not _SAFETY_ASSERTION.search(statement):
        return False
    return any(_RISK_EVIDENCE.search(p.text) for p in cited)


def classify(statement: str, citation_keys: list[str], by_key: dict[str, EvidencePassage]) -> Grounding:
    cited = [by_key[k] for k in citation_keys if k in by_key]
    if not cited:
        return Grounding.unsupported  # a claim with no resolvable citation is never allowed
    if _contradicts(statement, cited):
        return Grounding.unsupported  # false reassurance against risk-bearing evidence
    drug_tokens = frozenset(t for p in cited for t in tokenize(p.drug_name or "") if len(t) > 2)
    best = max(_overlap(statement, p.text, drug_tokens) for p in cited)
    if best >= GROUNDED_AT:
        return Grounding.grounded
    if best >= INFERRED_AT:
        return Grounding.inferred
    return Grounding.unsupported


def _conflict(findings: list[SafetyFinding]) -> bool:
    by_subject: dict[str, list[SafetyFinding]] = {}
    for f in findings:
        by_subject.setdefault((f.subject.interacting_with or f.subject.detail or "").lower(), []).append(f)
    for group in by_subject.values():
        directives = set()
        for f in group:
            toks = set(tokenize(f.statement))
            if toks & _AVOID:
                directives.add("avoid")
            if "safe" in toks or ("no" in toks and "interaction" in toks):
                directives.add("safe")
        if {"avoid", "safe"} <= directives:
            return True
    return False


def verify(draft: dict, passages: list[EvidencePassage], drug_terms: set[str]) -> dict:
    by_key = {p.citation_key: p for p in passages}

    # 1) Re-grade findings; drop UNSUPPORTED (fabricated/unsupported claims are removed).
    kept: list[SafetyFinding] = []
    for f in draft["findings"]:
        g = classify(f.statement, f.citation_keys, by_key)
        if g == Grounding.unsupported:
            continue
        f.grounding = g
        kept.append(f)

    # 2) Grade clinical answer sentences; compute grounded share over positive claims.
    clinical = [s for s in draft["answer_sentences"] if s["clinical"]]
    if clinical:
        grades = [classify(s["text"], s["citation_keys"], by_key) for s in clinical]
        grounded_share = sum(1 for g in grades if g == Grounding.grounded) / len(grades)
    else:
        grounded_share = 1.0  # no positive clinical claim -> nothing ungrounded

    conflict = _conflict(kept)
    abstain = (not draft["answerable"]) or (grounded_share < GROUNDING_THRESHOLD) or conflict

    if abstain:
        if not draft["answerable"] and draft["answer_reason"] == "no_evidence":
            answer = (
                "I don't have reliable information to answer this safely: no applicable label or guideline "
                "passages were retrieved for the requested drug. Please consult a current drug reference "
                "or a pharmacist."
            )
        elif not draft["answerable"] and draft["answer_reason"] == "insufficient":
            answer = (
                f"I don't have reliable information on {draft['uncovered_entity']} in the available sources, "
                f"so I can't responsibly assess that specific question. I am abstaining rather than guessing; "
                f"please verify with a current drug-interaction reference or a pharmacist."
            )
        elif conflict:
            answer = (
                "Retrieved sources conflict on this question, so I am abstaining rather than presenting a "
                "potentially misleading conclusion. Please consult a pharmacist or current guideline."
            )
        else:
            answer = (
                "Too little of the available evidence could be grounded to a source, so I am abstaining rather "
                "than guessing. Please consult a current drug reference or a pharmacist."
            )
        level = "low"
    else:
        clinical_text = " ".join(s["text"] for s in draft["answer_sentences"] if s["clinical"])
        procedural = " ".join(s["text"] for s in draft["answer_sentences"] if not s["clinical"])
        answer = (clinical_text + " " + procedural).strip()
        level = "high" if grounded_share >= 0.85 else "moderate"

    conf: Confidence = draft["confidence"]
    conf.grounded_share = round(grounded_share, 3)
    conf.level = level  # type: ignore[assignment]
    if conflict:
        conf.gaps = ["Sources conflict on the key question."] + conf.gaps

    return {
        "abstained": abstain,
        "answer": answer,
        "findings": kept,
        "options": draft["options"] if not abstain else [],
        "confidence": conf,
        "conflict": conflict,
    }
