"""Expert routing: the LocalRouter ranks the expected specialty first for every case."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.pipeline import run_to_brief
from backend.retrieval import get_provider
from backend.retrieval.base import normalize_name
from backend.routing import RoutingContext, get_router
from backend.routing.local_router import LocalRouter

CASES_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic_cases"
SEED = Path(__file__).resolve().parents[1] / "data" / "seed" / "specialists.json"
CASE_FILES = sorted(CASES_DIR.glob("case*.json"))


def _specialists() -> list[dict]:
    roster = json.loads(SEED.read_text())
    return [
        {
            "id": i,
            "name": k,
            "specialty": v["specialty"],
            "expertise_keywords": v.get("expertise_keywords", []),
            "drug_classes": v.get("drug_classes", []),
            "capacity": v.get("capacity", 6),
            "current_load": 0,
            "available": True,
        }
        for i, (k, v) in enumerate(roster.items())
    ]


def _ctx(payload: dict, brief) -> RoutingContext:
    classes = getattr(get_provider(), "drug_classes", {})
    cand = payload["candidate_drug"]["name"]
    terms = [cand] + [m["name"] for m in payload.get("current_medications", [])]
    dc: list[str] = []
    for t in terms:
        dc += classes.get(normalize_name(t), [])
    return RoutingContext(
        question=payload.get("question", ""),
        candidate_drug=cand,
        drug_terms=terms,
        drug_classes=dc,
        conditions=[c["name"] for c in payload.get("conditions", [])],
        finding_types=[f.type for f in brief.findings],
        finding_text=" ".join(f.statement for f in brief.findings),
        emergency=bool(brief.emergency_resources),
    )


@pytest.mark.parametrize("path", CASE_FILES, ids=[p.stem for p in CASE_FILES])
def test_route_at_1(path):
    case = json.loads(path.read_text())
    expected = case["_expected"].get("route_specialty")
    if not expected:
        pytest.skip("no expected specialty")
    payload = {k: v for k, v in case.items() if k != "_expected"}
    brief = run_to_brief(payload)
    matches = get_router().route(_ctx(payload, brief), _specialists(), top_n=3)
    assert matches[0].specialty == expected, f"{path.stem}: got {[m.specialty for m in matches]}"


def test_capacity_breaks_ties():
    # Two equal-expertise specialists: the one with spare capacity ranks first.
    ctx = RoutingContext(question="anticoagulation bleeding inr", candidate_drug="warfarin")
    kw = ["anticoagulation", "bleeding", "inr"]
    specs = [
        {
            "id": 1,
            "name": "busy",
            "specialty": "Hematology",
            "expertise_keywords": kw,
            "drug_classes": [],
            "capacity": 4,
            "current_load": 4,
            "available": True,
        },
        {
            "id": 2,
            "name": "free",
            "specialty": "Hematology2",
            "expertise_keywords": kw,
            "drug_classes": [],
            "capacity": 4,
            "current_load": 0,
            "available": True,
        },
    ]
    matches = LocalRouter().route(ctx, specs)
    assert matches[0].specialist_id == 2  # the one with spare capacity


def test_unavailable_ranks_lower():
    ctx = RoutingContext(question="anticoagulation bleeding", candidate_drug="warfarin")
    specs = [
        {
            "id": 1,
            "name": "off",
            "specialty": "A",
            "expertise_keywords": ["anticoagulation", "bleeding"],
            "drug_classes": [],
            "capacity": 4,
            "current_load": 0,
            "available": False,
        },
        {
            "id": 2,
            "name": "on",
            "specialty": "B",
            "expertise_keywords": ["anticoagulation", "bleeding"],
            "drug_classes": [],
            "capacity": 4,
            "current_load": 1,
            "available": True,
        },
    ]
    matches = LocalRouter().route(ctx, specs)
    assert matches[0].specialist_id == 2
