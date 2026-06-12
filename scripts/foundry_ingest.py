"""Build the Foundry IQ knowledge base for Pharos from corpus/labels/*.json.

This is the runnable, credential-gated companion to FOUNDRY_SETUP.md. With Azure access it:
  1. creates an Azure AI Search index whose retrievable fields match FoundryIQProvider._to_passage,
  2. uploads each (drug, section) label excerpt as a document,
  3. registers a knowledge source over that index and a Foundry IQ knowledge base over the source.

Then `RETRIEVAL_PROVIDER=foundry_iq make eval` runs the same safety pipeline grounded by Foundry IQ.

Auth is keyless via DefaultAzureCredential. Requires: pip install -r requirements-foundry.txt and
the .env Foundry vars. Runs nothing destructive without those; it prints a clear message and exits.

Field mapping (index field -> EvidencePassage via _to_passage):
  id (key)        -> citation_key      (sanitized 'slug__section'; ':' is not a valid Azure key char)
  content         -> text
  drug_name       -> drug_name
  section         -> section
  title           -> title
  url             -> url
  source_version  -> source_version

[VERIFY] The knowledge-source / knowledge-base creation classes (SearchIndexKnowledgeSource,
KnowledgeBase) live in azure.search.documents.indexes (GA REST 2026-04-01). Confirm the exact
constructor field names against your installed azure-search-documents version before a live run;
the index + upload steps use the stable SearchIndexClient/SearchClient APIs.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS_DIR = ROOT / "corpus" / "labels"


def _docs() -> list[dict]:
    docs = []
    for path in sorted(LABELS_DIR.glob("*.json")):
        doc = json.loads(path.read_text())
        slug = path.stem
        drug = doc.get("drug_name") or slug
        for section, text in (doc.get("sections") or {}).items():
            if not str(text).strip():
                continue
            docs.append(
                {
                    "id": re.sub(r"[^A-Za-z0-9_\-]", "__", f"{slug}:{section}"),
                    "citation_key": f"{slug}:{section}",
                    "content": str(text).strip(),
                    "drug_name": drug,
                    "section": section,
                    "title": f"{drug} - {section.replace('_', ' ')}",
                    "url": doc.get("url") or "",
                    "source_version": doc.get("source_version") or "",
                    "classes": [str(c) for c in (doc.get("classes") or [])],
                }
            )
    return docs


SEMANTIC_CONFIG = "pharos-semantic"


def _build_index(endpoint: str, index_name: str, credential):
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="citation_key", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchableField(name="drug_name", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="section", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SimpleField(name="url", type=SearchFieldDataType.String),
        SimpleField(name="source_version", type=SearchFieldDataType.String),
        SearchField(
            name="classes",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
            facetable=True,
        ),
    ]
    # Agentic retrieval / knowledge sources require a semantic configuration on the index.
    semantic = SemanticSearch(
        default_configuration_name=SEMANTIC_CONFIG,
        configurations=[
            SemanticConfiguration(
                name=SEMANTIC_CONFIG,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[SemanticField(field_name="drug_name")],
                ),
            )
        ],
    )
    from azure.core.exceptions import ResourceNotFoundError

    client = SearchIndexClient(endpoint=endpoint, credential=credential)
    # Drop-and-recreate so re-runs are idempotent even when a field's attributes change
    # (Azure AI Search forbids altering an existing field in place). Safe: synthetic corpus.
    try:
        client.delete_index(index_name)
    except ResourceNotFoundError:
        pass
    client.create_or_update_index(SearchIndex(name=index_name, fields=fields, semantic_search=semantic))
    print(f"  index '{index_name}' (re)created ({len(fields)} fields, semantic config '{SEMANTIC_CONFIG}').")


def _upload(endpoint: str, index_name: str, credential, docs: list[dict]):
    from azure.search.documents import SearchClient

    client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
    client.upload_documents(documents=docs)
    print(f"  uploaded {len(docs)} label-section documents.")


def _build_knowledge_base(endpoint: str, index_name: str, ks_name: str, kb_name: str, credential):
    # Verified against azure-search-documents 12.0.0 (GA). KnowledgeBase.models is optional,
    # so no Azure OpenAI deployment is required for the extractive (intents) retrieve path.
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes import models as m

    fields = ("id", "citation_key", "content", "drug_name", "section", "title", "url", "source_version", "classes")
    client = SearchIndexClient(endpoint=endpoint, credential=credential)
    ks = m.SearchIndexKnowledgeSource(
        name=ks_name,
        search_index_parameters=m.SearchIndexKnowledgeSourceParameters(
            search_index_name=index_name,
            source_data_fields=[m.SearchIndexFieldReference(name=f) for f in fields],
            semantic_configuration_name=SEMANTIC_CONFIG,
        ),
    )
    client.create_or_update_knowledge_source(ks)
    kb = m.KnowledgeBase(name=kb_name, knowledge_sources=[m.KnowledgeSourceReference(name=ks_name)])
    client.create_or_update_knowledge_base(kb)
    print(f"  knowledge source '{ks_name}' + knowledge base '{kb_name}' created.")


def main() -> int:
    from backend.envload import load_env

    load_env()  # load .env (real env vars win; no-op if absent)
    endpoint = os.getenv("SEARCH_SERVICE_ENDPOINT")
    if not endpoint:
        print(
            "SEARCH_SERVICE_ENDPOINT not set. Configure .env (see FOUNDRY_SETUP.md) and install "
            "requirements-foundry.txt before running. Nothing was created.",
            file=sys.stderr,
        )
        return 2
    index_name = os.getenv("SEARCH_INDEX_NAME", "pharos-drug-labels-index")
    ks_name = os.getenv("KNOWLEDGE_SOURCE_NAME", "pharos-drug-labels-source")
    kb_name = os.getenv("KNOWLEDGE_BASE_NAME", "pharos-drug-labels")

    try:
        from azure.identity import DefaultAzureCredential
    except ImportError:
        print("azure-identity not installed. Run: pip install -r requirements-foundry.txt", file=sys.stderr)
        return 2

    credential = DefaultAzureCredential()
    docs = _docs()
    print(f"Ingesting {len(docs)} documents from {LABELS_DIR} into Foundry IQ...")
    _teardown(endpoint, ks_name, kb_name, credential)
    _build_index(endpoint, index_name, credential)
    _upload(endpoint, index_name, credential, docs)
    _build_knowledge_base(endpoint, index_name, ks_name, kb_name, credential)
    print("Done. Set RETRIEVAL_PROVIDER=foundry_iq and run `make eval` to ground via Foundry IQ.")
    return 0


def _teardown(endpoint: str, ks_name: str, kb_name: str, credential):
    """Delete the knowledge base then the knowledge source so the index can be (re)built.
    Order matters: a KB references a KS, and a KS references the index."""
    from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
    from azure.search.documents.indexes import SearchIndexClient

    client = SearchIndexClient(endpoint=endpoint, credential=credential)
    for kind, fn, name in (
        ("knowledge base", client.delete_knowledge_base, kb_name),
        ("knowledge source", client.delete_knowledge_source, ks_name),
    ):
        try:
            fn(name)
            print(f"  removed existing {kind} '{name}'.")
        except ResourceNotFoundError:
            pass
        except HttpResponseError as e:
            print(f"  ({kind} '{name}' not removed: {e.message or e})")


if __name__ == "__main__":
    raise SystemExit(main())
