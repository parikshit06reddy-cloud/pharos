"""LocalCorpusProvider — offline retrieval over curated public FDA-label excerpts.

Loads corpus/labels/*.json (one file per drug, with label sections), turns each
(drug, section) into an `EvidencePassage`, and ranks matches with a small BM25-style
scorer. Matching is by RxCUI when available and by normalized drug name otherwise
(the reliable key offline). Zero network, zero cloud credentials.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Sequence
from pathlib import Path

from ..schemas import EvidencePassage
from .base import normalize_name, tokenize

_CORPUS_DIR = Path(os.getenv("CORPUS_DIR", Path(__file__).resolve().parents[2] / "corpus" / "labels"))


class LocalCorpusProvider:
    def __init__(self, corpus_dir: Path | None = None) -> None:
        self.corpus_dir = Path(corpus_dir) if corpus_dir else _CORPUS_DIR
        self.passages: list[EvidencePassage] = []
        self.drug_classes: dict[str, list[str]] = {}
        self._by_name: dict[str, list[int]] = {}
        self._by_rxcui: dict[str, list[int]] = {}
        self._df: dict[str, int] = {}
        self._avg_len: float = 1.0
        self._load()

    # --- loading --------------------------------------------------------------
    def _load(self) -> None:
        if not self.corpus_dir.exists():
            return
        for path in sorted(self.corpus_dir.glob("*.json")):
            try:
                doc = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            self._ingest(doc, path.stem)
        self._build_index()

    def _ingest(self, doc: dict, slug: str) -> None:
        drug_name = doc.get("drug_name") or slug
        norm = normalize_name(drug_name)
        rxcui = doc.get("rxcui")
        classes = [c.lower() for c in doc.get("classes", [])]
        if classes:
            self.drug_classes[norm] = classes
        source_id = doc.get("source_id", f"openfda:{slug}")
        version = doc.get("source_version")
        url = doc.get("url")
        for section, text in (doc.get("sections") or {}).items():
            if not text or not str(text).strip():
                continue
            idx = len(self.passages)
            self.passages.append(
                EvidencePassage(
                    citation_key=f"{slug}:{section}",
                    source_id=source_id,
                    source_type="fda_label",
                    title=f"{drug_name} — {section.replace('_', ' ')}",
                    section=section,
                    drug_name=drug_name,
                    drug_rxcui=str(rxcui) if rxcui else None,
                    text=str(text).strip(),
                    source_version=version,
                    url=url,
                    provider="local_corpus",
                )
            )
            self._by_name.setdefault(norm, []).append(idx)
            if rxcui:
                self._by_rxcui.setdefault(str(rxcui), []).append(idx)

    def _build_index(self) -> None:
        total_len = 0
        for p in self.passages:
            toks = set(tokenize(p.text))
            total_len += len(tokenize(p.text))
            for t in toks:
                self._df[t] = self._df.get(t, 0) + 1
        self._avg_len = (total_len / len(self.passages)) if self.passages else 1.0

    # --- retrieval ------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        *,
        drug_rxcuis: Sequence[str] = (),
        drug_names: Sequence[str] = (),
        sections: Sequence[str] = (),
        k: int = 8,
    ) -> list[EvidencePassage]:
        candidate_idx: set[int] = set()
        for rx in drug_rxcuis:
            if rx and rx in self._by_rxcui:
                candidate_idx.update(self._by_rxcui[rx])
        for name in drug_names:
            norm = normalize_name(name)
            if norm in self._by_name:
                candidate_idx.update(self._by_name[norm])
        if not candidate_idx:
            return []

        wanted = set(sections)
        scored: list[tuple[float, int]] = []
        q_tokens = tokenize(query)
        for idx in candidate_idx:
            p = self.passages[idx]
            if wanted and p.section not in wanted:
                continue
            scored.append((self._bm25(q_tokens, p.text), idx))

        scored.sort(key=lambda s: s[0], reverse=True)
        return [self.passages[idx] for _, idx in scored[:k]]

    def _bm25(self, q_tokens: list[str], text: str, k1: float = 1.5, b: float = 0.75) -> float:
        toks = tokenize(text)
        if not toks:
            return 0.0
        n = len(self.passages) or 1
        freq: dict[str, int] = {}
        for t in toks:
            freq[t] = freq.get(t, 0) + 1
        score = 0.0
        for qt in set(q_tokens):
            f = freq.get(qt, 0)
            if not f:
                continue
            df = self._df.get(qt, 1)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            denom = f + k1 * (1 - b + b * len(toks) / self._avg_len)
            score += idf * (f * (k1 + 1)) / denom
        return score
