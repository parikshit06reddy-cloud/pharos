"""Model card — intended use, scope, limitations, regulatory framing."""

from __future__ import annotations

MODEL_CARD = {
    "name": "Pharos",
    "version": "pharos-0.1.0",
    "intended_use": "Point-of-care medication decision support for licensed clinicians, on synthetic cases. "
    "Surfaces cited, severity-triaged safety considerations; informs, does not prescribe.",
    "out_of_scope": [
        "Autonomous prescribing, dosing, or discontinuation decisions.",
        "Use with real patient data / PHI.",
        "Emergency medical guidance in place of contacting emergency services.",
        "Any clinical use — this is a research prototype.",
    ],
    "data_sources": "Public openFDA drug labels and RxNorm (curated, abbreviated excerpts in offline mode); "
    "optionally a Microsoft Foundry IQ knowledge base over Azure AI Search.",
    "reasoning": "Retrieve → six parallel safety specialists → synthesize → grounding gate → triage.",
    "safety_mechanisms": [
        "Grounding gate: every clinical claim is graded against its cited passage; unsupported claims are dropped.",
        "Abstention when evidence is missing, insufficient, or conflicting.",
        "Prompt-injection guard treats retrieved text as data, not instructions.",
        "Consent gate (synthetic + no-PHI) and PII scrubbing at intake.",
        "Hash-chained, PHI-free audit log with one-tap session delete.",
    ],
    "limitations": [
        "Offline corpus is a small, abbreviated subset of public labeling.",
        "Interaction reasoning reflects label text, not a curated interaction database.",
        "Grounding is overlap-based offline; neither mode replaces clinical judgment.",
    ],
    "regulatory_framing": "Designed to align with the FDA non-device Clinical Decision Support pattern: "
    "informs rather than drives the decision and shows the basis (cited source) for "
    "independent clinician review. Not a cleared medical device. Not medical advice.",
}


def model_card() -> dict:
    return dict(MODEL_CARD)
