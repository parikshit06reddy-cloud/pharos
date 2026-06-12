"""Auth + role gating."""

from __future__ import annotations

from tests.conftest import login


def test_login_success_and_me(client):
    h = login(client, "frontdesk")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["username"] == "frontdesk"
    assert me["role"] == "front_desk"


def test_login_bad_password(client):
    r = client.post("/api/auth/login", json={"username": "frontdesk", "password": "wrong"})
    assert r.status_code == 401


def test_missing_token_rejected(client):
    assert client.get("/api/auth/me").status_code == 401


def test_doctor_cannot_create_case(client, cases):
    from tests.conftest import case_payload

    h = login(client, "hart")  # doctor
    r = client.post("/api/cases", json=case_payload(cases["case01_warfarin_fluconazole"]), headers=h)
    assert r.status_code == 403


def test_specialists_roster(client):
    h = login(client, "frontdesk")
    docs = client.get("/api/auth/specialists", headers=h).json()
    specialties = {d["specialty"] for d in docs}
    assert {"Hematology", "Cardiology", "Toxicology"} <= specialties
