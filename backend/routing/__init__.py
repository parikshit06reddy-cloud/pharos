"""Expert-routing adapter. Offline by default; flip to a Foundry/LLM router via ROUTER_PROVIDER.

Mirrors the retrieval adapter seam: the safety pipeline and UI never change when the
router provider changes.
"""

from __future__ import annotations

import os

from .base import RouterProvider, RoutingContext, SpecialistMatch

__all__ = ["get_router", "RoutingContext", "SpecialistMatch", "RouterProvider"]


def get_router() -> RouterProvider:
    choice = os.getenv("ROUTER_PROVIDER", "local").lower()
    if choice in ("foundry", "foundry_iq", "llm"):
        from .foundry_router import FoundryRouter

        return FoundryRouter()
    from .local_router import LocalRouter

    return LocalRouter()
