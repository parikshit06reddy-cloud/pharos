# Plan & design rationale

How Pharos is built and why, so a reviewer can follow the decisions behind the code.

## Thesis

A medication agent's hard problem is trustworthiness under uncertainty: a confident wrong answer is
worse than an honest "I don't know." Pharos is organized so that **every clinical claim is grounded in
a retrieved source or it is dropped**, and the agent **abstains** when too little is grounded.

## Architecture in one line

Synthetic patient context → intake (consent + PII scrub) → retrieval (the one Foundry seam) → injection
guard → six parallel safety specialists → synthesizer → **grounding gate / abstention (the safety core)**
→ triage/escalation → cited Decision Brief. The brief is wrapped in a hospital case-management workflow
(intake → route → assign → review) with a tool-calling assistant. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Design decisions (and why)

- **Adapter seams, offline by default.** Retrieval (`RetrievalProvider`), routing (`RouterProvider`), and
  the agent (`AgentProvider`) each have an offline default and a Foundry/Azure live implementation,
  selected by env. The demo and full evaluation run with zero cloud credentials; flipping one env var
  grounds on Foundry IQ without changing the safety pipeline.
- **Grounding by content, not by name.** The verifier measures lexical overlap of a claim against its
  cited passage, **excluding the drug's own name** (retrieval already established the drug linkage), and
  adds a **contradiction guard** that drops false-reassurance claims ("no interaction… no monitoring")
  against risk-bearing evidence. The gate can only get stricter, never looser.
- **Condition-gated specialists.** Boxed warnings and dose/special-population findings only fire when
  relevant to *this* patient (pregnancy, pediatric, geriatric, renal), reducing noise.
- **Human-in-command everywhere.** Routing suggests; the agent proposes state-changing actions for
  confirmation; the brief presents options, never orders.
- **Non-circular evaluation.** Beyond the curated suite, the scorecard includes an adversarial held-out
  suite, a labeled grounding-gate benchmark (incl. false-reassurance attacks), and a live-openFDA
  robustness probe — so 100% is earned across independent views, and real-label divergence is reported
  honestly. See `scripts/score.py`, `scripts/eval_live.py`, `eval/gate_benchmark.json`.

## Build order (delivered)

1. Schemas + retrieval adapter + curated corpus + the eight-stage pipeline + grounding gate.
2. Six specialists + synthesizer + triage + governance (hash-chained audit, data passport, model card).
3. FastAPI surface; synthetic case suite; scorecard.
4. Enterprise workflow: SQLite persistence, roles/auth, case lifecycle, expert routing, role dashboards,
   tool-calling assistant with human-in-the-loop.
5. Award hardening: de-circularized evaluation, Foundry IQ replay proof + ingest script, submission
   package, reproducibility, honest reporting.

## Out of scope / human-only

- Live Azure tenant run (provision per [FOUNDRY_SETUP.md](FOUNDRY_SETUP.md), run `scripts/foundry_ingest.py`).
- The ≤5-minute demo video ([DEMO_SCRIPT.md](DEMO_SCRIPT.md)).
- Real PHI / clinical validation — explicitly out of scope; synthetic + public data only.
