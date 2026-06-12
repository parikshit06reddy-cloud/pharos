# Foundry IQ setup

Pharos runs fully offline by default (`RETRIEVAL_PROVIDER=local`). This guide wires the **live**
path: a **Microsoft Foundry IQ** knowledge base over **Azure AI Search**, consumed through the
`FoundryIQProvider` adapter. The safety pipeline does not change — only where evidence comes from.

> Items marked **[VERIFY]** are SDK/portal specifics that move between preview releases. They are
> isolated to `backend/retrieval/foundry_iq.py` and listed at the end so you can confirm them
> against current docs in your tenant before a live demo. Sourcing for every value is in
> [RESEARCH.md](RESEARCH.md) (verified 2026-06-11).

## Prove the adapter offline first (no tenant needed)

Before provisioning Azure you can confirm the integration is real, not aspirational. A captured
GA-shaped Foundry IQ response (`tests/fixtures/foundry_iq_response.json`) is mapped by the **production**
`FoundryIQProvider._to_passage` and driven through the full safety pipeline:

```bash
make test                         # tests/test_foundry_adapter.py: mapping + grounded brief from Foundry data
RETRIEVAL_PROVIDER=foundry_replay make eval   # run the suite on the replayed Foundry response
```

When you have a tenant, one command ingests the corpus into the knowledge base:

```bash
pip install -r requirements-foundry.txt
python -m scripts.foundry_ingest  # builds the Azure AI Search index + knowledge source + knowledge base
```

## Prerequisites

- An Azure subscription with access to **Microsoft Foundry** (Azure AI Foundry) and **Azure AI Search** (Basic tier or higher, with the **semantic ranker** enabled — Foundry IQ agentic retrieval depends on it).
- A Foundry **project** and a deployed chat model.
- Python deps: `pip install -r requirements-foundry.txt` (azure-ai-projects, azure-search-documents `--pre`, azure-identity).

## Step 1 — Create the knowledge base content

Pharos retrieves FDA **drug-label** passages. Build the corpus locally first:

```bash
python scripts/fetch_corpus.py        # writes corpus/labels/*.json from live openFDA
```

Each file is one drug with label sections (`boxed_warning`, `contraindications`,
`drug_interactions`, `warnings`, `use_in_specific_populations`, …). These become your KB documents.

## Step 2 — Stand up Azure AI Search

1. Create an **Azure AI Search** service; enable **Semantic ranker** (Settings → Semantic ranker).
2. Create an index whose fields cover the passage shape Pharos expects: a content/text field, plus
   `drug_name`, `section`, `title`, `url`, and `source_version` as retrievable fields. **[VERIFY]**
   the exact field names against your KB schema and reflect them in `_to_passage()`.
3. Ingest the corpus. Two supported routes — pick one and record it: **(a)** push the JSON files via
   an Azure AI Search **indexer** over Blob storage, or **(b)** index documents directly with the
   SDK. **[VERIFY]** which ingestion route your KB uses.

## Step 3 — Create the Foundry IQ knowledge base

In the Foundry portal, create a **Knowledge Base** (Foundry IQ) bound to the Azure AI Search index
above, and note its name. Foundry IQ wraps the index with **agentic retrieval** (query planning +
semantic ranking).

## Step 4 — Identity & permissions (keyless)

Pharos authenticates with **`DefaultAzureCredential`** (no keys in code or env).

```bash
az login
# Grant your principal read access to the search data plane:
#   role: "Search Index Data Reader"  on the Azure AI Search resource
```

**[VERIFY]** the minimal role set for agentic retrieval in your tenant (Search Index Data Reader is
sufficient for the direct-retrieve path Pharos uses).

## Step 5 — Configure environment & flip the provider

Copy `.env.example` → `.env` and set:

```bash
RETRIEVAL_PROVIDER=foundry_iq
FOUNDRY_PROJECT_ENDPOINT=https://<your-project>.services.ai.azure.com/api/projects/<project>
SEARCH_SERVICE_ENDPOINT=https://<your-search>.search.windows.net
KNOWLEDGE_BASE_NAME=pharos-drug-labels
KNOWLEDGE_SOURCE_NAME=pharos-drug-labels-source
PROJECT_CONNECTION_NAME=<search-connection-name>
FOUNDRY_MODEL_DEPLOYMENT=<chat-model-deployment-name>
SEARCH_API_VERSION=2026-04-01          # GA, extractive; preview is 2026-05-01-preview
```

Then run as usual:

```bash
make eval          # same scorecard, now grounded by Foundry IQ
make run
```

Because both providers return identical `EvidencePassage` objects, the grounding gate, specialists,
triage, and UI are unchanged. If credentials are missing or a call fails, switch
`RETRIEVAL_PROVIDER` back to `local` to restore the offline demo instantly.

## Step 6 — Architecture diagram for submission

The required "architecture diagram showing Foundry" is the live-path view of the diagram in
[README.md](README.md)/[ARCHITECTURE.md](ARCHITECTURE.md): the retrieval adapter calls **Foundry IQ
agentic retrieval** over **Azure AI Search**, returning passages that flow into the grounding gate.

## [VERIFY] checklist — RESOLVED + VERIFIED LIVE (2026-06-12, azure-search-documents 12.0.0)

The full Pharos eval scored **100% on the live `foundry_iq` path** against a real tenant
(see [eval/scorecard_foundry_iq.md](eval/scorecard_foundry_iq.md)). Concrete facts confirmed live:

- **Index needs a semantic configuration** — knowledge sources require it; `scripts/foundry_ingest.py`
  attaches one (`SemanticSearch` / `SemanticConfiguration`).
- **`KnowledgeBase.models` is optional** — no Azure OpenAI deployment is needed for the extractive
  retrieve path.
- **No server-side filter on the retrieve params** — the KB searches the whole corpus; the adapter
  post-filters to the queried drug + sections (and harvests `classes` for the duplication specialist).
- **Ingestion teardown order**: delete knowledge base -> knowledge source -> index, then rebuild
  (`foundry_ingest.py` does this so re-runs are idempotent).

The six original items, for reference:

1. **Retrieve call** — ✅ `azure.search.documents.knowledgebases.KnowledgeBaseRetrievalClient(endpoint, knowledge_base_name, credential, api_version)`, then `client.retrieve(retrieval_request=KnowledgeBaseRetrievalRequest(...))`. The response carries `.response` (compiled extract), `.activity` (query plan), and `.references` (the cited chunks). Pharos reads `.references`. *(Was previously guessed as `azure.search.documents.indexes` — corrected.)*
2. **API version** — ✅ pin `SEARCH_API_VERSION=2026-04-01` (GA, **extractive/minimal** retrieval — exactly Pharos's direct-retrieve design). `2026-05-01-preview` adds answer synthesis + model query planning, which Pharos deliberately does **not** use.
3. **KB field names** — ✅ each reference exposes `reference.source_data` (the backing index document's retrievable fields) and `reference.doc_key`. `_to_passage()` maps `doc_key`→`citation_key`, `source_data.content`→`text`, plus `drug_name`/`section`/`url`/`source_version`. Make those fields **retrievable** on your index.
4. **Ingestion route** — ✅ register a **knowledge source** (e.g. `SearchIndexKnowledgeSource` over an index, or `AzureBlobKnowledgeSource` over the `corpus/` JSON in Blob), then a **knowledge base** that references it; set `KNOWLEDGE_SOURCE_NAME` to that source.
5. **Query planning** — ✅ Pharos passes `intents=[KnowledgeRetrievalSemanticIntent(search=...)]` so retrieval is deterministic and **extractive** (no LLM query planning), keeping the grounding gate in control.
6. **Roles** — ✅ `Search Index Data Reader` on the Azure AI Search resource is sufficient for the direct-retrieve path; keyless via `DefaultAzureCredential`.

Sources: Microsoft Learn *Knowledge Retrieval – Retrieve* (`rest-searchservice-2026-04-01`), the `azure-search-documents` knowledgebases Python reference, and Azure AI Search *What's new* (Foundry IQ knowledge bases GA).
