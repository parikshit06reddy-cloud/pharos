"""LocalCorpusProvider retrieval + the provider selector."""

from __future__ import annotations

import os

from backend.retrieval import get_provider
from backend.retrieval.base import normalize_name, tokenize
from backend.retrieval.local_corpus import LocalCorpusProvider


def test_tokenize_and_normalize():
    assert tokenize("Warfarin (sodium) 5mg!") == ["warfarin", "sodium", "5mg"]
    assert normalize_name("Warfarin Sodium") == "warfarin"
    assert normalize_name("  Fluconazole ") == "fluconazole"


def test_retrieve_known_drug_section():
    p = LocalCorpusProvider()
    res = p.retrieve("warfarin interaction bleeding", drug_names=["fluconazole"], sections=("drug_interactions",), k=5)
    assert res, "expected at least one fluconazole interaction passage"
    assert all(r.section == "drug_interactions" for r in res)
    assert any("warfarin" in r.text.lower() for r in res)


def test_retrieve_unknown_drug_is_empty():
    p = LocalCorpusProvider()
    assert p.retrieve("anything", drug_names=["ceftriaxone"], k=5) == []


def test_drug_classes_loaded():
    p = LocalCorpusProvider()
    assert "benzodiazepine" in p.drug_classes.get("alprazolam", [])
    assert "benzodiazepine" in p.drug_classes.get("diazepam", [])


def test_get_provider_defaults_to_local():
    os.environ.pop("RETRIEVAL_PROVIDER", None)
    assert isinstance(get_provider(), LocalCorpusProvider)
