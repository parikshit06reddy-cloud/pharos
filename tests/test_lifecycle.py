"""Case lifecycle state machine + role enforcement, via the API."""

from __future__ import annotations

from tests.conftest import case_payload, login


def _file_case(client, cases, name="case01_warfarin_fluconazole"):
    h = login(client, "frontdesk")
    return client.post("/api/cases", json=case_payload(cases[name]), headers=h).json(), h


def test_create_triages_and_routes(client, cases):
    detail, _ = _file_case(client, cases)
    assert detail["status"] == "routed"
    assert detail["triage_tier"] == "review_recommended"
    assert detail["route_specialty"] == "Hematology"
    assert detail["brief"] is not None
    assert [e["type"] for e in detail["timeline"]] == ["created", "triaged", "routed"]


def test_full_assign_pickup_complete(client, cases):
    detail, h = _file_case(client, cases)
    cid = detail["id"]
    docs = client.get("/api/auth/specialists", headers=h).json()
    hart = next(d for d in docs if d["specialty"] == "Hematology")

    a = client.post(f"/api/cases/{cid}/assign", json={"doctor_id": hart["id"]}, headers=h).json()
    assert a["status"] == "assigned" and a["assigned_doctor"]["specialty"] == "Hematology"

    dh = login(client, "hart")
    p = client.post(f"/api/cases/{cid}/pickup", headers=dh).json()
    assert p["status"] == "in_review"
    r = client.post(f"/api/cases/{cid}/resolve", json={"outcome": "complete", "note": "done"}, headers=dh)
    assert r.json()["status"] == "completed"


def test_doctor_cannot_pickup_unassigned_case(client, cases):
    detail, _ = _file_case(client, cases)
    cid = detail["id"]
    # cardoso is not assigned this case
    dh = login(client, "cardoso")
    r = client.post(f"/api/cases/{cid}/pickup", headers=dh)
    assert r.status_code == 403


def test_invalid_transition_rejected(client, cases):
    detail, h = _file_case(client, cases)
    cid = detail["id"]
    dh = login(client, "hart")
    # Cannot resolve a case that is only 'routed' (not picked up / not theirs)
    r = client.post(f"/api/cases/{cid}/resolve", json={"outcome": "complete"}, headers=dh)
    assert r.status_code in (403, 409)


def test_consent_gate_blocks_non_synthetic(client, cases):
    h = login(client, "frontdesk")
    bad = case_payload(cases["case01_warfarin_fluconazole"])
    bad["consent"] = {"synthetic": True, "no_phi": False}
    r = client.post("/api/cases", json=bad, headers=h)
    assert r.status_code == 422
