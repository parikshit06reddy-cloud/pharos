"""FoundryIQProvider — LIVE retrieval from a Microsoft Foundry IQ knowledge base.

================  FOUNDRY IQ INTEGRATION POINT  ================
This is the ONLY module that talks to Foundry IQ. Everything it returns is normalized
into Pharos `EvidencePassage` objects, so the rest of the engine is unchanged.

VERIFIED LIVE against a real tenant on 2026-06-12 (azure-search-documents 12.0.0, REST 2026-04-01).
The full Pharos suite scored 100% on this path; see eval/scorecard_foundry_iq.md.
  * SDK: `azure.search.documents.knowledgebases.KnowledgeBaseRetrievalClient`
    .retrieve(retrieval_request=KnowledgeBaseRetrievalRequest(intents=[...],
    knowledge_source_params=[SearchIndexKnowledgeSourceParams(...)])) -> response whose
    `.references` each carry `.source_data` (the index doc fields) + `.doc_key`.
  * GA `2026-04-01` is MINIMAL/EXTRACTIVE (no answer synthesis) — exactly Pharos's design;
    we pass `intents=[KnowledgeRetrievalSemanticIntent(search=...)]` (no LLM query planning).
  * The retrieve params expose NO server-side filter, and the KB searches the whole corpus,
    so we scope results to the queried drug + sections HERE (post-filter by normalized
    drug_name), matching the offline provider, and harvest `classes` for the duplication
    specialist. The backing index must carry a SEMANTIC CONFIGURATION; KnowledgeBase.models
    is optional (no Azure OpenAI deployment needed for the extractive path).
  * Auth: keyless via DefaultAzureCredential; the identity needs `Search Index Data Reader`
    (retrieve) and Contributor roles for ingestion (see scripts/foundry_ingest.py).
===============================================================
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from ..schemas import EvidencePassage
from .base import normalize_name


class FoundryIQProvider:
    def __init__(self) -> None:
        self.search_endpoint = os.environ["SEARCH_SERVICE_ENDPOINT"]
        self.knowledge_base = os.environ["KNOWLEDGE_BASE_NAME"]
        # The knowledge source (the backing Search index/blob source) registered in the KB.
        self.knowledge_source = os.getenv("KNOWLEDGE_SOURCE_NAME", "pharos-drug-labels-source")
        self.api_version = os.getenv("SEARCH_API_VERSION", "2026-04-01")  # GA, extractive
        self.reranker_threshold = float(os.getenv("FOUNDRY_RERANKER_THRESHOLD", "0"))
        # Drug-class metadata accumulated from returned source_data, so the duplication
        # specialist works the same as offline (the pipeline reads provider.drug_classes).
        self.drug_classes: dict[str, list[str]] = {}
        self._client: Any = None  # lazy

    def _get_client(self):
        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient

            self._client = KnowledgeBaseRetrievalClient(
                endpoint=self.search_endpoint,
                knowledge_base_name=self.knowledge_base,
                credential=DefaultAzureCredential(),
                api_version=self.api_version,
            )
        return self._client

    def retrieve(
        self,
        query: str,
        *,
        drug_rxcuis: Sequence[str] = (),
        drug_names: Sequence[str] = (),
        sections: Sequence[str] = (),
        k: int = 8,
    ) -> list[EvidencePassage]:
        from azure.search.documents.knowledgebases.models import (
            KnowledgeBaseRetrievalRequest,
            KnowledgeRetrievalSemanticIntent,
            SearchIndexKnowledgeSourceParams,
        )

        # Scope the semantic intent with drug + section hints (no LLM query planning).
        scope = " ".join(filter(None, [query, *drug_names, *sections]))
        request = KnowledgeBaseRetrievalRequest(
            intents=[KnowledgeRetrievalSemanticIntent(search=scope)],
            knowledge_source_params=[
                SearchIndexKnowledgeSourceParams(
                    knowledge_source_name=self.knowledge_source,
                    include_references=True,
                    include_reference_source_data=True,
                    reranker_threshold=self.reranker_threshold,
                )
            ],
            include_activity=False,
        )
        result = self._get_client().retrieve(retrieval_request=request)

        # The KB does semantic search across the whole corpus; scope the results to the queried
        # drug(s) + sections exactly as the offline provider does (matching by normalized drug
        # name), and harvest class metadata for the duplication specialist along the way.
        wanted = {normalize_name(n) for n in drug_names if n}
        secs = set(sections)
        out: list[EvidencePassage] = []
        for ref in self._references(result):
            passage = self._to_passage(ref)
            classes = self._ref_classes(ref)
            if passage.drug_name and classes:
                self.drug_classes[normalize_name(passage.drug_name)] = classes
            if wanted and normalize_name(passage.drug_name or "") not in wanted:
                continue
            if secs and passage.section not in secs:
                continue
            out.append(passage)
        return out[:k]

    @staticmethod
    def _ref_classes(ref) -> list[str]:
        src = getattr(ref, "source_data", None)
        if src is None and isinstance(ref, dict):
            src = ref.get("source_data") or ref.get("sourceData")
        if src is None:
            return []
        classes = src.get("classes") if isinstance(src, dict) else getattr(src, "classes", None)
        return [str(c).lower() for c in classes] if classes else []

    # --- normalization helpers (the adapter contract) ---------------------
    @staticmethod
    def _references(result) -> list:
        """Pull the `references` collection from a retrieve response (SDK object or JSON dict)."""
        refs = getattr(result, "references", None)
        if refs is None and isinstance(result, dict):
            refs = result.get("references")
        return list(refs or [])

    @staticmethod
    def _to_passage(ref) -> EvidencePassage:
        # Each reference carries `source_data` (the backing index document's retrievable
        # fields) and a `doc_key`. Align these field names with your index schema.
        src = getattr(ref, "source_data", None)
        if src is None and isinstance(ref, dict):
            src = ref.get("source_data") or ref.get("sourceData")
        src = src or {}

        def g(key, default=None):
            if isinstance(src, dict):
                return src.get(key, default)
            return getattr(src, key, default)

        doc_key = getattr(ref, "doc_key", None) or (ref.get("docKey") if isinstance(ref, dict) else None)
        return EvidencePassage(
            citation_key=str(doc_key or g("id") or g("citation_key") or "foundry_iq:0"),
            source_id=str(g("source_id") or "foundry_iq"),
            source_type="fda_label",
            title=str(g("title") or "Knowledge base reference"),
            section=str(g("section") or "knowledge_base"),
            drug_name=g("drug_name"),
            drug_rxcui=str(g("drug_rxcui")) if g("drug_rxcui") else None,
            text=str(g("content") or g("page_chunk") or g("text") or ""),
            source_version=g("source_version"),
            url=g("url") or g("source_url"),
            provider="foundry_iq",
        )
