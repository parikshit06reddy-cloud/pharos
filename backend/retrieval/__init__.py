"""Retrieval provider selection. Flip the offline/live seam with RETRIEVAL_PROVIDER."""

from __future__ import annotations

import os
from functools import lru_cache

from .base import RetrievalProvider, normalize_name, tokenize

__all__ = ["get_provider", "RetrievalProvider", "normalize_name", "tokenize"]


@lru_cache(maxsize=1)
def _local():
    from .local_corpus import LocalCorpusProvider

    return LocalCorpusProvider()


def get_provider() -> RetrievalProvider:
    choice = os.getenv("RETRIEVAL_PROVIDER", "local").lower()
    if choice in ("foundry_iq", "foundry"):
        from .foundry_iq import FoundryIQProvider

        return FoundryIQProvider()
    if choice in ("foundry_replay", "replay"):
        # Offline replay of a captured Foundry IQ response — proves the adapter + pipeline
        # work on Foundry-shaped data without a live tenant.
        from .foundry_replay import FoundryReplayProvider

        return FoundryReplayProvider()
    return _local()
