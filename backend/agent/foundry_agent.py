"""FoundryAgent — LIVE tool-calling navigation agent via Azure OpenAI / Microsoft Foundry.

================  FOUNDRY INTEGRATION POINT (agent)  ================
A ReAct-style tool-calling loop: the Foundry-hosted chat model is given the app tool
schemas (from tools.REGISTRY), reasons over the user's request, and emits tool calls.
Read-only tools execute inline; state-changing tools (assign_case) are returned as a
proposed action for the human to confirm — the model never assigns autonomously.

[VERIFY] before flipping AGENT_PROVIDER=foundry:
  1. Azure OpenAI chat-completions client + function/tool-calling schema for your SDK.
  2. Deployment name (FOUNDRY_MODEL_DEPLOYMENT) and keyless DefaultAzureCredential RBAC.
The offline LocalAgent stays the default so the demo needs zero credentials.
=====================================================================
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session

from ..models import User
from .local_agent import LocalAgent


class FoundryAgent:
    """Stub that delegates to the deterministic agent until live wiring is verified.

    The real implementation builds tool schemas from tools.REGISTRY, runs the model's
    tool-calling loop, executes read-only tools, and surfaces state-changing tools as
    proposed actions. Until credentials are configured it falls back so the app still works.
    """

    def __init__(self) -> None:
        self._fallback = LocalAgent()

    def respond(self, session: Session, user: User, message: str, history: list[dict]) -> Iterator[dict]:
        # [VERIFY] replace with the Azure OpenAI tool-calling loop; see module docstring.
        yield from self._fallback.respond(session, user, message, history)
