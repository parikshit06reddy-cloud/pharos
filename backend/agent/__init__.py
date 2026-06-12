"""In-app navigation/help agent. Offline deterministic by default; flip to a Foundry/LLM
ReAct agent via AGENT_PROVIDER. State-changing tools always require human confirmation."""

from __future__ import annotations

import os

from .base import AgentProvider

__all__ = ["get_agent", "AgentProvider"]


def get_agent() -> AgentProvider:
    choice = os.getenv("AGENT_PROVIDER", "local").lower()
    if choice in ("foundry", "foundry_iq", "llm"):
        from .foundry_agent import FoundryAgent

        return FoundryAgent()
    from .local_agent import LocalAgent

    return LocalAgent()
