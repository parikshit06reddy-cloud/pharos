"""End-to-end API test: boots the FastAPI app via TestClient and drives the full flow."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app
from tests.conftest import case_payload

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_brief_sync_flagged_case(cases):
    r = client.post("/brief/sync", json=case_payload(cases["case01_warfarin_fluconazole"]))
    assert r.status_code == 200
    body = r.json()
    assert body["abstained"] is False
    assert body["triage_tier"] == "review_recommended"
    assert any(f["type"] == "interaction" for f in body["findings"])
    assert body["citations"], "expected at least one citation"


def test_brief_sync_abstain_case(cases):
    r = client.post("/brief/sync", json=case_payload(cases["case10_abstain_no_evidence"]))
    body = r.json()
    assert body["abstained"] is True
    assert body["triage_tier"] == "informational"


def test_brief_sync_injection_case(cases):
    r = client.post("/brief/sync", json=case_payload(cases["case12_injection_overdose"]))
    body = r.json()
    assert body["safety_flags"]["injection_detected"] is True
    assert body["triage_tier"] == "urgent"
    assert body["emergency_resources"]
    assert "safe at any dose" not in body["answer"].lower()


def test_consent_gate_returns_422(cases):
    bad = case_payload(cases["case01_warfarin_fluconazole"])
    bad["consent"] = {"synthetic": True, "no_phi": False}
    r = client.post("/brief/sync", json=bad)
    assert r.status_code == 422
    assert r.json()["error"] == "consent"


def test_brief_sse_event_order(cases):
    r = client.post("/brief", json=case_payload(cases["case01_warfarin_fluconazole"]))
    assert r.status_code == 200
    events = [line[len("event: ") :] for line in r.text.splitlines() if line.startswith("event: ")]
    # Stage skeleton in order, with six specialists in the middle.
    assert events[0] == "intake"
    assert events[1] == "retrieval"
    assert events[2] == "injection_scan"
    assert events.count("specialist") == 6
    assert events[-4:] == ["synthesis", "verifier", "triage", "brief"]


def test_data_passport_and_audit_and_delete(cases):
    case = case_payload(cases["case01_warfarin_fluconazole"])
    sid = case["session_id"]
    client.post("/brief/sync", json=case)

    passport = client.get(f"/data-passport?session_id={sid}").json()
    assert passport["session_deletable"] is True

    audit = client.get("/audit-log").json()
    assert audit["chain_valid"] is True
    assert any(e["case_id"] == sid for e in audit["entries"])

    deleted = client.delete(f"/session/{sid}").json()
    assert deleted["deleted"] is True
    assert deleted["audit_rows_removed"] >= 1
    assert deleted["chain_valid"] is True

    audit2 = client.get("/audit-log").json()
    assert all(e["case_id"] != sid for e in audit2["entries"])
    assert audit2["chain_valid"] is True
