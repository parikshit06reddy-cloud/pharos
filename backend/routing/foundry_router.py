"""FoundryRouter — LIVE expert routing via an Azure OpenAI / Microsoft Foundry model.

================  FOUNDRY INTEGRATION POINT (routing)  ================
This is the only routing module that talks to Azure. It asks a Foundry-hosted chat model
to rank the candidate specialists for a case and returns the same `SpecialistMatch`
objects as the offline router, so the service, API, and UI are unchanged.

The model receives ONLY de-identified, synthetic case context + the specialist roster.
It returns suggestions for a human to confirm — never an automatic assignment.

[VERIFY] before flipping ROUTER_PROVIDER=foundry:
  1. Azure OpenAI chat client/version (azure-ai-projects / openai SDK) and deployment name.
  2. Auth: keyless via DefaultAzureCredential (Azure AI Developer / Cognitive Services User).
The offline LocalRouter remains the default so the demo needs zero credentials.
=====================================================================
"""

from __future__ import annotations

import json
import os
from typing import Any

from .base import RoutingContext, SpecialistMatch
from .local_router import LocalRouter


class FoundryRouter:
    def __init__(self) -> None:
        self.endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
        self.deployment = os.environ["FOUNDRY_MODEL_DEPLOYMENT"]
        self._client: Any = None
        self._fallback = LocalRouter()  # used if the model response can't be parsed

    def _get_client(self):
        if self._client is None:
            # [VERIFY] exact client/import for your Azure OpenAI / Foundry setup.
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential

            self._client = AIProjectClient(
                endpoint=self.endpoint,
                credential=DefaultAzureCredential(),
            )
        return self._client

    def route(self, context: RoutingContext, specialists: list[dict], *, top_n: int = 5) -> list[SpecialistMatch]:
        roster = [
            {
                "id": s["id"],
                "specialty": s.get("specialty"),
                "expertise": s.get("expertise_keywords", []),
                "load": s.get("current_load", 0),
                "capacity": s.get("capacity", 0),
            }
            for s in specialists
        ]
        prompt = (
            "You route a SYNTHETIC medication case to the best specialist. Return strict JSON: "
            '{"ranking":[{"id":int,"score":0..1,"reason":str}]}. Consider expertise match first, '
            "then spare capacity. Do not invent specialists.\n"
            f"CASE: {json.dumps(context.__dict__)}\nROSTER: {json.dumps(roster)}"
        )
        try:
            client = self._get_client()
            # [VERIFY] chat completion call shape for your SDK/deployment.
            completion = client.inference.get_chat_completions(  # type: ignore[attr-defined]
                model=self.deployment,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            ranking = json.loads(completion.choices[0].message.content)["ranking"]
            by_id = {s["id"]: s for s in specialists}
            out: list[SpecialistMatch] = []
            for r in ranking[:top_n]:
                s = by_id.get(r["id"])
                if not s:
                    continue
                out.append(
                    SpecialistMatch(
                        specialist_id=s["id"],
                        name=s.get("name", ""),
                        specialty=s.get("specialty", ""),
                        score=float(r.get("score", 0)),
                        matched_terms=[],
                        rationale=r.get("reason", ""),
                        capacity=s.get("capacity", 0),
                        current_load=s.get("current_load", 0),
                        available=bool(s.get("available", True)),
                    )
                )
            return out or self._fallback.route(context, specialists, top_n=top_n)
        except Exception:
            # Never fail routing because the live model is unavailable — fall back offline.
            return self._fallback.route(context, specialists, top_n=top_n)
