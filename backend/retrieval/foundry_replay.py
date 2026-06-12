"""FoundryReplayProvider — drives a CAPTURED Foundry IQ retrieve response through the real
FoundryIQProvider adapter mapping, then serves the resulting passages to the pipeline.

This proves, with zero Azure credentials, that (a) the GA-shaped Foundry IQ response maps
correctly via `FoundryIQProvider._to_passage`, and (b) the full safety pipeline produces a
correct grounded brief from Foundry-sourced passages. It is a fixture replay, NOT a live call;
the live path is `FoundryIQProvider` (RETRIEVAL_PROVIDER=foundry_iq).
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

from ..schemas import EvidencePassage
from .base import normalize_name
from .foundry_iq import FoundryIQProvider

_DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "foundry_iq_response.json"


class FoundryReplayProvider:
    def __init__(self, fixture_path: str | os.PathLike[str] | None = None) -> None:
        raw = fixture_path or os.getenv("FOUNDRY_REPLAY_FIXTURE") or _DEFAULT_FIXTURE
        data = json.loads(Path(raw).read_text())
        # Reuse the REAL adapter mapping so this exercises production code, not a parallel copy.
        refs = FoundryIQProvider._references(data)
        self.passages: list[EvidencePassage] = [FoundryIQProvider._to_passage(r) for r in refs]
        self.drug_classes: dict[str, list[str]] = {}

    def retrieve(
        self,
        query: str,
        *,
        drug_rxcuis: Sequence[str] = (),
        drug_names: Sequence[str] = (),
        sections: Sequence[str] = (),
        k: int = 8,
    ) -> list[EvidencePassage]:
        wanted = {normalize_name(n) for n in drug_names if n}
        secs = set(sections)
        out = [
            p for p in self.passages if normalize_name(p.drug_name or "") in wanted and (not secs or p.section in secs)
        ]
        return out[:k]
