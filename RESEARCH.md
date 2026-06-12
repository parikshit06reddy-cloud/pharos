# Research & sourcing

Sourcing for the design decisions and the version-sensitive Foundry facts. Foundry/Azure
specifics were verified against Microsoft Learn on 2026-06-11; re-confirm before a live run as
preview SDK surfaces move (see the `[VERIFY]` checklist in [FOUNDRY_SETUP.md](FOUNDRY_SETUP.md)).

## Foundry IQ / Azure AI Search agentic retrieval (verified 2026-06-11)

- **Knowledge Retrieval – Retrieve, REST API** (`rest-searchservice-2026-04-01`), Microsoft Learn —
  `POST {endpoint}/knowledgebases('{kb}')/retrieve?api-version=2026-04-01`; request supports `intents`
  (`{"search": ..., "type": "semantic"}`) and `knowledgeSourceParams` (`includeReferences`,
  `includeReferenceSourceData`, `rerankerThreshold`); response is `response` / `activity` / `references`,
  where each reference carries `source_data` + `docKey` + `rerankerScore`.
- **`azure.search.documents.knowledgebases.KnowledgeBaseRetrievalClient`** (Python SDK reference) —
  constructor `(endpoint, knowledge_base_name, credential, api_version="2026-04-01")`; method
  `retrieve(retrieval_request=KnowledgeBaseRetrievalRequest(...))`.
- **`KnowledgeBaseRetrievalRequest`** (Python SDK reference) — `intents`, `knowledge_source_params`,
  `include_activity`, `max_output_size_in_tokens`.
- **What's new in Azure AI Search** + **Microsoft Foundry blog, "Build smarter agents faster with
  Foundry IQ"** — knowledge bases are GA on the stable `2026-04-01` REST API with **minimal, extractive**
  retrieval; query planning / answer synthesis remain preview (`2026-05-01-preview`). Pharos uses the
  GA extractive path so its own grounding gate decides what reaches the clinician.

These map directly onto [backend/retrieval/foundry_iq.py](backend/retrieval/foundry_iq.py); the six
resolved `[VERIFY]` items are in [FOUNDRY_SETUP.md](FOUNDRY_SETUP.md). The adapter mapping is exercised
offline by `tests/test_foundry_adapter.py` against `tests/fixtures/foundry_iq_response.json` (a captured
GA-shaped response), and ingestion is scripted in `scripts/foundry_ingest.py`.

## Expert routing

- **"Right Patient, Right Specialist, Right Time: Retrieval-Augmented Generation for Specialty Referral
  Routing"** (PMC12919621; Stanford SAGE). Embedding/similarity routing of clinical questions to
  specialist domains achieved ~87% success@1 and ~99% success@3 across five specialties. Pharos's
  `LocalRouter` is the offline analogue: transparent expertise-overlap matching with a grounded
  rationale, plus skill/capacity tie-breaking.
- **Skill-based routing**: Microsoft Dynamics 365 unified routing (exact/closest skill match, capacity,
  round-robin) and Sprinklr unified routing — the basis for the capacity/availability tie-breakers.

## Enterprise case-management workflow

- Referral/triage routing systems — **ReferralMD**, **Phreesia**, **Solum Health**, **PicassoMD**,
  **Cabot** — informed the intake → triage → route → assign → review → closed-loop-tracking workflow,
  filtered work queues, SLA target windows, and the audit/activity timeline.

## Agent design

- **Anthropic, "Building Effective AI Agents"** and **Microsoft, "Three tiers of Agentic AI"** —
  high-control/regulated domains favor a single tool-using agent with human-in-the-loop over autonomous
  multi-agent. Pharos's assistant proposes state-changing actions for human confirmation.

## Data provenance

- **openFDA Drug Label API** (`api.fda.gov/drug/label.json`) — source of real label text via
  `scripts/fetch_corpus.py`; fields map 1:1 to the corpus section keys.
- **RxNorm / RxNav** (`rxnav.nlm.nih.gov`) — RxCUI resolution.
- The NLM Drug-Drug Interaction API was **discontinued in January 2024**; interaction reasoning is
  therefore derived from label text (reflected in [SAFETY.md](SAFETY.md) limitations).
- The committed `corpus/labels/*.json` are curated, abbreviated, synthetic-for-demo excerpts of public
  labeling, each marked *not for clinical use*. `examplamine.json` is a fully synthetic
  prompt-injection fixture and is never overwritten by a fetch.
