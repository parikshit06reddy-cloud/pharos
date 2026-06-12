"""LocalRouter — offline expert routing by expertise overlap + capacity.

Scores each specialist by how many of their expertise terms (keywords, drug classes,
specialty) appear in the case query, then breaks ties by availability and spare capacity.
This is the offline analogue of embedding-based specialty routing (cf. Stanford eConsult
RAG): a transparent, grounded match with an explainable rationale. Zero credentials.
"""

from __future__ import annotations

from ..retrieval.base import tokenize
from .base import RoutingContext, SpecialistMatch

_CAPACITY_WEIGHT = 0.5  # tiebreak only; expertise match dominates


def _matched_terms(terms: list[str], query_text: str, query_tokens: set[str]) -> list[str]:
    hits = []
    for term in terms:
        t = (term or "").lower().strip()
        if not t:
            continue
        if (" " in t and t in query_text) or (t in query_tokens):
            hits.append(t)
    return hits


class LocalRouter:
    def route(self, context: RoutingContext, specialists: list[dict], *, top_n: int = 5) -> list[SpecialistMatch]:
        query_text = context.query_text()
        query_tokens = set(tokenize(query_text))

        scored: list[SpecialistMatch] = []
        for s in specialists:
            terms = list(s.get("expertise_keywords", [])) + list(s.get("drug_classes", [])) + [s.get("specialty", "")]
            matched = _matched_terms(terms, query_text, query_tokens)
            match_count = len(set(matched))
            capacity = max(int(s.get("capacity", 1)), 1)
            load = int(s.get("current_load", 0))
            available = bool(s.get("available", True))
            capacity_factor = max(0.0, 1.0 - load / capacity) if available else 0.0
            scored.append(
                SpecialistMatch(
                    specialist_id=int(s["id"]),
                    name=s.get("name", ""),
                    specialty=s.get("specialty", ""),
                    score=float(match_count),  # raw for now; normalized below
                    matched_terms=sorted(set(matched)),
                    capacity=capacity,
                    current_load=load,
                    available=available,
                    rationale="",
                )
            )
            # stash capacity factor on the object for sorting
            scored[-1]._capacity_factor = capacity_factor  # type: ignore[attr-defined]

        # Rank: most expertise matches, then available, then most spare capacity.
        scored.sort(key=lambda m: (m.score, m.available, getattr(m, "_capacity_factor", 0.0)), reverse=True)

        best = scored[0].score if scored and scored[0].score > 0 else 0.0
        for m in scored:
            cap_factor = getattr(m, "_capacity_factor", 0.0)
            base = (m.score / best) if best > 0 else 0.0
            # Blend expertise (dominant) with a small capacity nudge, clamp to 1.0.
            m.score = round(min(1.0, base + (_CAPACITY_WEIGHT * cap_factor * base if base else 0.0)), 3)
            if m.matched_terms:
                m.rationale = f"Matched {', '.join(m.matched_terms[:5])} -> {m.specialty}"
            else:
                m.rationale = f"No specific expertise match; {m.specialty} considered as fallback."

        return scored[:top_n]
