"""Audit chain integrity, PHI-free fingerprints, purge-and-rechain, passport, model card."""

from __future__ import annotations

from backend.governance import audit_log, data_passport, model_card


def _append(case_id: str, candidate: str):
    return audit_log.append(
        case_id=case_id,
        candidate=candidate,
        model_version="pharos-0.1.0",
        citation_keys=["a:b"],
        triage_tier="review_recommended",
        abstained=False,
        injection_detected=False,
        case_fp=audit_log.case_fingerprint({"case_id": case_id}),
    )


def test_chain_valid_after_appends():
    _append("c1", "fluconazole")
    _append("c2", "metformin")
    assert audit_log.verify_chain() is True
    rows = audit_log.entries()
    assert len(rows) == 2
    assert rows[0]["prev_hash"] == "0" * 64
    assert rows[1]["prev_hash"] == rows[0]["hash"]


def test_fingerprint_is_stable_and_phi_free():
    raw = {"candidate_drug": {"name": "x"}, "question": "secret"}
    fp1 = audit_log.case_fingerprint(raw)
    fp2 = audit_log.case_fingerprint(dict(raw))
    assert fp1 == fp2 and len(fp1) == 64
    assert "secret" not in fp1


def test_tampering_detected():
    _append("c1", "fluconazole")
    rows = audit_log.entries()
    rows[0]["candidate_drug"] = "tampered"
    audit_log._write_all(rows)  # corrupt the file
    assert audit_log.verify_chain() is False


def test_purge_rechains_and_stays_valid():
    _append("keep", "fluconazole")
    _append("drop", "metformin")
    _append("keep2", "lisinopril")
    removed = audit_log.purge_case("drop")
    assert removed == 1
    rows = audit_log.entries()
    assert all(r["case_id"] != "drop" for r in rows)
    assert audit_log.verify_chain() is True


def test_data_passport_shape():
    p = data_passport.passport(["email"])
    assert p["session_deletable"] is True
    assert p["redactions_this_session"] == ["email"]
    assert "hash" in p["telemetry"].lower()


def test_model_card_shape():
    c = model_card.model_card()
    assert c["version"] == "pharos-0.1.0"
    assert any("abstention" in s.lower() for s in c["safety_mechanisms"])
    assert c["out_of_scope"]
