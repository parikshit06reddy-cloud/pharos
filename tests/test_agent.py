"""Agent: read-only tools execute, state-changing actions are proposed and require confirm."""

from __future__ import annotations

import json

from tests.conftest import case_payload, login


def _sse_events(client, headers, message):
    r = client.post("/api/agent/chat", json={"message": message, "history": []}, headers=headers)
    assert r.status_code == 200
    events = []
    event = None
    for line in r.text.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            events.append((event, json.loads(line.split(":", 1)[1].strip())))
    return events


def _file(client, h, cases, name="case01_warfarin_fluconazole"):
    return client.post("/api/cases", json=case_payload(cases[name]), headers=h).json()


def test_who_is_expert_is_read_only(client, cases):
    h = login(client, "frontdesk")
    detail = _file(client, h, cases)
    events = _sse_events(client, h, f"who is the expert for case {detail['id']}")
    msgs = [d for (e, d) in events if e == "message"]
    assert any("Hematology" in m["text"] for m in msgs)


def test_assign_is_proposed_not_executed(client, cases):
    h = login(client, "frontdesk")
    detail = _file(client, h, cases)
    cid = detail["id"]
    events = _sse_events(client, h, f"assign case {cid} to the best match")
    proposals = [d.get("proposed_action") for (e, d) in events if e == "message" and d.get("proposed_action")]
    assert proposals, "expected a proposed action"
    assert proposals[0]["tool"] == "assign_case"

    # The case must NOT yet be assigned (human still has to confirm).
    after = client.get(f"/api/cases/{cid}", headers=h).json()
    assert after["status"] == "routed"
    assert after["assigned_doctor"] is None

    # Confirming executes it.
    out = client.post("/api/agent/confirm", json={"action": proposals[0]}, headers=h).json()
    assert out["executed"] is True
    final = client.get(f"/api/cases/{cid}", headers=h).json()
    assert final["status"] == "assigned"
    assert final["assigned_doctor"]["specialty"] == "Hematology"


def test_confirm_rejects_non_confirmable_tool(client, cases):
    h = login(client, "frontdesk")
    r = client.post("/api/agent/confirm", json={"action": {"tool": "search_cases", "args": {}}}, headers=h)
    assert r.status_code == 400
