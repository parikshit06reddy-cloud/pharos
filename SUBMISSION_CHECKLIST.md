# Submission checklist — Microsoft Agents League @ AI Skills Fest 2026

Track: **Reasoning Agents** · Grounding: **Microsoft Foundry + Foundry IQ**
Entry window: May 19 – June 14, 2026 (11:59pm PT).

## Required deliverables

| Requirement | Status | Where |
|---|---|---|
| Public GitHub repo | ✅ live | https://github.com/parikshit06reddy-cloud/pharos (MIT, no secrets, synthetic data only) |
| Project description | ✅ | [README.md](README.md) — pitch, problem, persona, features |
| Architecture diagram showing Foundry | ✅ | [README.md](README.md) + [ARCHITECTURE.md](ARCHITECTURE.md); live Foundry path in [FOUNDRY_SETUP.md](FOUNDRY_SETUP.md) |
| Demo video ≤5 min (own work) | ⏳ record before submit | runbook in [DEMO_SCRIPT.md](DEMO_SCRIPT.md); placeholder link in README |
| Uses Microsoft Foundry / Foundry IQ | ✅ | `backend/retrieval/foundry_iq.py` (agentic retrieval over Azure AI Search), flip via `RETRIEVAL_PROVIDER=foundry_iq` |
| Reasoning-agent behavior | ✅ | multi-step pipeline: retrieve → 6 parallel specialists → synthesize → grounding gate → triage |
| Reproducible | ✅ | `make setup && make eval && make test && make run`; offline by default (no cloud account) |

## Rubric mapping

| Criterion | Weight | How Pharos earns it |
|---|---|---|
| **Accuracy & Relevance** | 20% | Patient-specific reasoning over real FDA label text; every clinical claim cited; 100% must-flag coverage and citation coverage on the eval suite ([eval/scorecard.md](eval/scorecard.md)). |
| **Reasoning & Multi-step** | 20% | Eight-stage pipeline with six parallel safety specialists, a synthesizer, and a verifier; live reasoning is streamed stage-by-stage ([ARCHITECTURE.md](ARCHITECTURE.md)). |
| **Creativity & Originality** | 15% | The thesis — *a medication agent that knows when to abstain* — plus a grounding gate that drops fabricated citations, a condition-gated boxed-warning specialist, and a lighthouse-themed reasoning UI. |
| **UX & Presentation** | 15% | Calm clinical-instrument UI; severity as the organizing visual language; one-click source drawer; live reasoning stream; copyable hand-off; accessible (keyboard focus, reduced-motion). |
| **Reliability & Safety** | 20% | Grounding gate + abstention (tested adversarially), prompt-injection defense, consent gate, PII scrubbing, hash-chained audit log, one-tap delete; 100% on abstention, escalation, and injection-defense metrics. |
| **Community vote** | 10% | Clear story + working demo + honest framing; the abstention and injection demos are memorable. |

## Prize-category fit

- **Best Reasoning Agent** — the multi-specialist + grounding-gate pipeline is the core pitch.
- **Best use of Foundry IQ tools** — the retrieval adapter targets Foundry IQ agentic retrieval; [FOUNDRY_SETUP.md](FOUNDRY_SETUP.md) is a complete runbook.
- **Hack for Good** — clinician safety at the point of care, built privacy-first on public data.
- **Accessibility** — keyboard-navigable, visible focus, `prefers-reduced-motion` respected, high-contrast severity palette.

## The five non-negotiable principles — evidence

| Principle | Evidence |
|---|---|
| 1. Clinician-in-command | Options-not-orders framing; no prescribe/dose/discontinue instructions ([SAFETY.md](SAFETY.md) §1). |
| 2. Grounding gate + abstention | `backend/verifier.py`; `tests/test_verifier.py` drops a fabricated citation; `case10`/`case11` abstain. |
| 3. Public + synthetic data only | openFDA/RxNorm; consent gate in `backend/intake.py`; corpus marked *not for clinical use*. |
| 4. Prompt-injection defense | `backend/injection_guard.py`; `examplamine` label + `case12` prove neutralization + flagging. |
| 5. Privacy by design | PII scrub at intake; in-memory only; hash-only audit; `DELETE /session/{id}`. |

## Hardening completed (verified)

- [x] `LICENSE` (MIT), `RESEARCH.md`, `PLAN.md` added — no broken README/FOUNDRY_SETUP links.
- [x] Non-circular evaluation: curated suite + adversarial **held-out** suite + labeled **grounding-gate benchmark** (fabrication drop-recall 100%, incl. false-reassurance attacks) + **live openFDA** robustness probe. `make eval` gates all three offline.
- [x] Foundry IQ proven offline: `tests/test_foundry_adapter.py` maps a captured GA-shaped response through the production adapter and runs the full pipeline; `scripts/foundry_ingest.py` is the one-command live ingestion.
- [x] Grounding gate hardened (contradiction guard + drug-name-excluded overlap) — strictly stricter, never looser.
- [x] No secrets/PHI tracked: `.env`, `audit_log.jsonl`, `*.db`, caches, `node_modules/`, `dist/` all gitignored.

## Pre-submission punch list (human-only)

- [ ] Record and link the demo video (≤5 min) — follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
- [x] Push to a **public** GitHub repo — https://github.com/parikshit06reddy-cloud/pharos
- [ ] Re-run `make verify` on a clean checkout (lint + types + tests + eval + frontend build).
- [ ] (Optional) Provision Foundry IQ per [FOUNDRY_SETUP.md](FOUNDRY_SETUP.md), run `python -m scripts.foundry_ingest`, set `RETRIEVAL_PROVIDER=foundry_iq`, and re-run `make eval` for the live grounding path.
- [ ] Confirm the architecture diagram renders in the README on GitHub.
