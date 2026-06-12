"""End-to-end enterprise flow: intake -> route -> assign -> pick up -> complete,
plus dashboard metrics and a valid audit chain throughout."""

from __future__ import annotations

from backend.governance import audit_log
from tests.conftest import case_payload, login


def test_intake_to_completion_with_audit_chain(client, cases):
    fd = login(client, "frontdesk")

    # File a flagged case + an abstain case + the injection case.
    flagged = client.post("/api/cases", json=case_payload(cases["case01_warfarin_fluconazole"]), headers=fd).json()
    client.post("/api/cases", json=case_payload(cases["case10_abstain_no_evidence"]), headers=fd).json()
    inj = client.post("/api/cases", json=case_payload(cases["case12_injection_overdose"]), headers=fd).json()

    assert inj["injection_detected"] is True
    assert inj["triage_tier"] == "urgent"
    assert "safe at any dose" not in (inj["brief"]["answer"].lower())

    # Assign flagged case to Hematology, doctor picks it up and completes it.
    docs = client.get("/api/auth/specialists", headers=fd).json()
    hart = next(d for d in docs if d["specialty"] == "Hematology")
    cid = flagged["id"]
    client.post(f"/api/cases/{cid}/assign", json={"doctor_id": hart["id"]}, headers=fd)
    dh = login(client, "hart")
    client.post(f"/api/cases/{cid}/pickup", headers=dh)
    done = client.post(f"/api/cases/{cid}/resolve", json={"outcome": "complete"}, headers=dh).json()
    assert done["status"] == "completed"

    # Doctor worklist shows their case.
    mine = client.get("/api/cases?mine=true", headers=dh).json()
    assert any(c["id"] == cid for c in mine)

    # Dashboard reflects the work.
    metrics = client.get("/api/dashboard/metrics", headers=fd).json()
    assert metrics["by_status"]["completed"] >= 1
    assert metrics["open"] >= 1  # the abstain + injection cases are still open

    # The tamper-evident audit chain is valid and recorded workflow events.
    assert audit_log.verify_chain() is True
    types = {e.get("event_type") for e in audit_log.entries() if e.get("kind") == "workflow_event"}
    assert {"created", "triaged", "routed", "assigned", "picked_up", "complete"} <= types


def test_audit_chain_detects_tampering(client, cases):
    fd = login(client, "frontdesk")
    client.post("/api/cases", json=case_payload(cases["case01_warfarin_fluconazole"]), headers=fd)
    rows = audit_log.entries()
    assert rows and audit_log.verify_chain() is True
    rows[0]["candidate_drug"] = "tampered"
    audit_log._write_all(rows)
    assert audit_log.verify_chain() is False
