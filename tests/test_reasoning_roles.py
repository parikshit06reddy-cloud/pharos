"""Tests for named reasoning-agent roles and /health provider metadata."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.app import app
from backend.reasoning_roles import REASONING_AGENTS, role_for_event
from tests.conftest import case_payload

client = TestClient(app)


def test_reasoning_agents_roster_complete():
    stages = {a["stage"] for a in REASONING_AGENTS}
    assert stages == {"intake", "retrieval", "injection_scan", "specialist", "synthesis", "verifier", "triage"}
    patterns = {a["pattern"] for a in REASONING_AGENTS}
    assert "critic-verifier" in patterns
    assert "parallel-executor" in patterns


def test_role_for_specialist_includes_name():
    role = role_for_event("specialist", {"specialist": "interactions"})
    assert "interactions" in role
    assert "Safety Analyst" in role


def test_health_exposes_reasoning_agents_and_providers():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert len(body["reasoning_agents"]) == 7
    assert body["providers"]["retrieval"] == "local"
    assert body["offline_capable"] is True
    assert body["foundry_iq_ready"] is False


def test_brief_sse_events_carry_role_field(cases):
    r = client.post("/brief", json=case_payload(cases["case01_warfarin_fluconazole"]))
    assert r.status_code == 200
    lines = r.text.splitlines()
    data_lines = [ln for ln in lines if ln.startswith("data: ")]
    assert data_lines
    first = json.loads(data_lines[0][len("data: ") :])
    assert first.get("role") == "Gatekeeper"
    verifier_idx = next(i for i, ln in enumerate(lines) if ln == "event: verifier")
    verifier_data = json.loads(lines[verifier_idx + 1][len("data: ") :])
    assert "Critic" in verifier_data.get("role", "")


def test_retrieval_event_includes_provider_class(cases):
    r = client.post("/brief", json=case_payload(cases["case01_warfarin_fluconazole"]))
    idx = r.text.splitlines().index("event: retrieval")
    data = json.loads(r.text.splitlines()[idx + 1][len("data: ") :])
    assert data.get("provider_class") == "LocalCorpusProvider"
    assert data.get("role") == "Researcher"
