"""Named reasoning-agent roles for SSE traces, /health, and judge-facing docs.

Maps pipeline stages to the competition rubric vocabulary (planner/executor/critic)
without changing orchestration logic.
"""

from __future__ import annotations

from typing import Any

# Full roster — order matches the live pipeline stream.
REASONING_AGENTS: list[dict[str, str]] = [
    {
        "id": "gatekeeper",
        "stage": "intake",
        "role": "Gatekeeper",
        "pattern": "guardrail",
        "description": "Consent gate, PII scrub, validate synthetic patient context.",
    },
    {
        "id": "researcher",
        "stage": "retrieval",
        "role": "Researcher",
        "pattern": "tool-use",
        "description": "Retrieve evidence via RetrievalProvider (Foundry IQ agentic retrieval or offline BM25).",
    },
    {
        "id": "shield",
        "stage": "injection_scan",
        "role": "Prompt Shield",
        "pattern": "guardrail",
        "description": "Treat retrieved text as data; strip instruction-like sentences (Prompt-Shields-style).",
    },
    {
        "id": "specialists",
        "stage": "specialist",
        "role": "Safety Analyst",
        "pattern": "parallel-executor",
        "description": "Six parallel specialists reason only from retrieved passages; each emits cited findings.",
    },
    {
        "id": "assembler",
        "stage": "synthesis",
        "role": "Draft Assembler",
        "pattern": "executor",
        "description": "Assemble answer sentences, options, and confidence from specialist findings.",
    },
    {
        "id": "critic",
        "stage": "verifier",
        "role": "Critic / Grounding Gate",
        "pattern": "critic-verifier",
        "description": "Grade every clinical claim vs its cited passage; drop UNSUPPORTED; abstain if ungrounded.",
    },
    {
        "id": "escalation",
        "stage": "triage",
        "role": "Escalation Officer",
        "pattern": "executor",
        "description": "Severity triage, emergency resources, cited clinician hand-off.",
    },
]

_STAGE_ROLE: dict[str, str] = {a["stage"]: a["role"] for a in REASONING_AGENTS}


def role_for_event(event: str, data: dict[str, Any] | None = None) -> str:
    if event == "specialist" and data and data.get("specialist"):
        return f"Safety Analyst · {data['specialist']}"
    return _STAGE_ROLE.get(event, event.replace("_", " ").title())


def active_providers() -> dict[str, str]:
    import os

    return {
        "retrieval": os.getenv("RETRIEVAL_PROVIDER", "local"),
        "router": os.getenv("ROUTER_PROVIDER", "local"),
        "agent": os.getenv("AGENT_PROVIDER", "local"),
    }
