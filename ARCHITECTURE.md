# Architecture

Pharos is a deterministic, auditable reasoning pipeline. Data flows in one direction; every
stage is a small typed function; the only cloud-dependent seam is the retrieval adapter.

## Pipeline stages (and the SSE events they emit)

| # | Stage | Module | Streams event | Responsibility |
|---|-------|--------|---------------|----------------|
| 1 | Intake / de-identify | `backend/intake.py` | `intake` | Scrub PII, enforce synthetic + no-PHI consent, validate into `PatientCase`, optional RxCUI resolution. |
| 2 | Retrieval | `backend/retrieval/` | `retrieval` | Fetch evidence passages for the candidate + current meds. **Foundry IQ seam.** |
| 3 | Injection guard | `backend/injection_guard.py` | `injection_scan` | Strip instruction-like sentences from retrieved text; flag attempts. |
| 4 | Safety specialists ×6 | `backend/specialists/` | `specialist` (×6) | Reason **only** over retrieved passages; emit findings with citation keys + severity. Run in parallel. |
| 5 | Synthesizer | `backend/synthesizer.py` | `synthesis` | Assemble answer sentences, options, confidence, answerability. |
| 6 | Verifier (grounding gate) | `backend/verifier.py` | `verifier` | Grade every clinical sentence vs its cited passage; drop UNSUPPORTED; abstain if grounded share < threshold or sources conflict. **Safety core.** |
| 7 | Triage / escalation | `backend/triage.py` | `triage` | Tier the brief; attach emergency resources; build cited hand-off. |
| 8 | Decision Brief | `backend/pipeline.py` | `brief` | Final assembled `DecisionBrief`. |

`backend/pipeline.run_pipeline()` is a generator yielding `{event, data}` dicts; the FastAPI
layer (`backend/app.py`) relays them as Server-Sent Events so the UI shows reasoning as it
happens. `run_to_brief()` consumes the generator and returns the final brief (used by evals/tests).

## Data contracts (`backend/schemas.py`, Pydantic v2)

- **`PatientCase`** — demographics, conditions, current_medications, allergies, labs, candidate_drug, question, consent.
- **`EvidencePassage`** — `citation_key`, `source_id`, `source_type`, `title`, `section`, `drug_name`, `drug_rxcui`, `text`, `source_version`, `url`, `provider`. The citation key is the contract between retrieval, specialists, and the verifier.
- **`SafetyFinding`** — `type`, `severity` (info/caution/serious/critical), `subject`, `statement`, `citation_keys`, `grounding` (GROUNDED/INFERRED/UNSUPPORTED), `rationale`, `specialist`.
- **`DecisionBrief`** — `triage_tier`, `abstained`, `answer`, `findings`, `options`, `confidence`, `handoff_summary`, `citations`, `emergency_resources`, `limitations`, `safety_flags`.

## The retrieval adapter — the one Foundry IQ seam

```
RetrievalProvider (Protocol)              backend/retrieval/base.py
  .retrieve(query, *, drug_rxcuis, drug_names, sections, k) -> list[EvidencePassage]
        ├── LocalCorpusProvider           backend/retrieval/local_corpus.py   (default, offline BM25)
        └── FoundryIQProvider             backend/retrieval/foundry_iq.py     (live, agentic retrieval)
get_provider() picks by env RETRIEVAL_PROVIDER (local | foundry_iq)
```

Both providers return the **same** `EvidencePassage` shape, so stages 3–8 are identical regardless
of source. Matching is by RxCUI when available and by normalized drug name otherwise (the reliable
key offline). Every Foundry-specific integration point in `foundry_iq.py` is commented and marked
`[VERIFY]`; see [FOUNDRY_SETUP.md](FOUNDRY_SETUP.md). Pharos uses Foundry IQ's **direct retrieve**
action (not a fully autonomous answer) so the grounding gate decides what reaches the clinician.

## The grounding gate (verifier) algorithm

For each clinical sentence and its cited passage(s):

1. If no cited key resolves to a retrieved passage → **UNSUPPORTED** (a claim with no citation is never allowed).
2. **Contradiction guard:** if the claim asserts safety / no-risk (e.g. "no interaction", "safe at any dose", "no monitoring") while its cited passage is risk-bearing → **UNSUPPORTED**. This catches false-reassurance fabrications that pure lexical overlap would pass.
3. Compute content-word overlap between the sentence and the passage text, **excluding the cited drug's own name** (retrieval already established the drug linkage, so naming the drug is not evidence).
4. overlap ≥ 0.45 → **GROUNDED**; ≥ 0.20 → **INFERRED**; else → **UNSUPPORTED**.

Steps 2–3 can only make the gate *stricter*; they never keep a claim the overlap test would drop. The gate is measured on a labeled benchmark (`eval/gate_benchmark.json`): fabrication drop-recall and precision are both 100%, including adversarial contradiction attacks. UNSUPPORTED findings are dropped. `grounded_share` = fraction of clinical answer sentences that are
GROUNDED. Pharos **abstains** when the question is unanswerable (no/insufficient evidence), or
`grounded_share < GROUNDING_THRESHOLD` (default 0.6), or sources directly conflict (one passage says
*avoid/contraindicated* while another says *safe*). Grounding intentionally does **not** require the
drug name to appear literally in the snippet — FDA section text often refers to a drug by class —
because the drug linkage is already established by retrieval.

## Parallelism

The six specialists are independent pure functions over the same `SpecialistContext`; the pipeline
runs them in a `ThreadPoolExecutor` and merges their findings. This is genuine concurrency, and the
design scales to additional specialists without touching orchestration.

## Governance (cross-cutting)

- **Audit log** (`governance/audit_log.py`) — append-only, hash-chained JSONL. Each entry stores a SHA-256 **fingerprint** of the case (never raw PHI), the candidate drug, citation keys used, triage tier, flags, timestamp, and the previous entry's hash. `verify_chain()` detects tampering; `purge_case()` removes a case and re-chains.
- **Data passport** (`governance/data_passport.py`) — declares what is and isn't collected, retention (in-memory per session), no secondary use, hash-only telemetry, session-deletable.
- **Model card** (`governance/model_card.py`) — intended use, out-of-scope uses, data sources, limitations, regulatory framing.
- **Session delete** — `DELETE /session/{id}` drops in-memory state and purges the session's audit rows; the chain stays valid.

## Enterprise workflow layer (v0.2)

The Decision Brief pipeline above is wrapped in a multi-role case-management workflow. New pieces
follow the same adapter discipline as retrieval (offline default + Foundry seam, swapped by env):

| Concern | Module | Notes |
|---|---|---|
| Persistence | `backend/db.py`, `backend/models.py` | SQLite via SQLModel: `User`, `Case`, `CaseEvent`. Synthetic, no-PHI. |
| Auth & roles | `backend/auth.py`, `backend/seed.py`, `data/seed/` | Demo signed-token auth + role guards (front_desk / doctor / admin); seeded staff roster. Seam for hospital SSO. |
| Case lifecycle | `backend/cases/service.py` | State machine `new -> triaged -> routed -> assigned -> in_review -> completed/returned/escalated`; creates the brief at intake and records a `CaseEvent` timeline. |
| Expert routing | `backend/routing/` | `RouterProvider`: `local_router` (expertise overlap + spare capacity, grounded rationale) by default; `foundry_router` (LLM) via `ROUTER_PROVIDER`. Always suggests; a human confirms. |
| Navigation agent | `backend/agent/` | Single tool-calling agent (`tools.py` registry). Read-only tools run inline; state-changing tools (assign) are returned as a **proposed action** the user confirms (`/api/agent/confirm`). `local_agent` (deterministic) default; `foundry_agent` (ReAct) via `AGENT_PROVIDER`. |
| HTTP surface | `backend/api/` | `auth`, `cases`, `dashboard`, `agent` routers under `/api`. |

Workflow actions are appended to the same hash-chained audit log (`append_event`, no PHI) and also
stored as `CaseEvent` rows for the per-case activity timeline. The routing engine is evaluated with
a new **route@1 / route@3** accuracy metric in `scripts/score.py`.

```
RouterProvider.route(context, specialists) -> [SpecialistMatch]      backend/routing/base.py
  ├── LocalRouter      expertise overlap + capacity      (default, offline)
  └── FoundryRouter    LLM ranking over the roster        (ROUTER_PROVIDER=foundry)

AgentProvider.respond(session, user, message, history) -> events     backend/agent/base.py
  ├── LocalAgent       deterministic intent -> tool       (default, offline)
  └── FoundryAgent     ReAct tool-calling loop            (AGENT_PROVIDER=foundry)
```

## Why this maps to the rubric

Accuracy & Reasoning come from patient-specific multi-specialist analysis grounded in real label
text, plus expert routing measured at 100% route@1; Reliability & Safety from the grounding gate,
abstention, injection defense, role-gated workflow, and hash-chained audit trail (now covering every
workflow action); Creativity from the "agent that knows when to abstain" thesis, the condition-gated
specialists, and a tool-calling assistant that proposes — never performs — state changes; UX from the
live reasoning stream, one-click citations, dual-pane worklists, and the docked assistant. See
[SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md).
