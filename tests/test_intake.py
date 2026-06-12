"""Intake: consent gate + PII scrubbing (privacy by design)."""

from __future__ import annotations

import pytest

from backend.intake import ConsentError, run_intake

_BASE = {
    "candidate_drug": {"name": "fluconazole"},
    "question": "Any interaction?",
    "consent": {"synthetic": True, "no_phi": True},
}


def test_consent_required_synthetic_and_no_phi():
    with pytest.raises(ConsentError):
        run_intake({**_BASE, "consent": {"synthetic": True, "no_phi": False}})
    with pytest.raises(ConsentError):
        run_intake({**_BASE, "consent": {"synthetic": False, "no_phi": True}})
    with pytest.raises(ConsentError):
        run_intake({**_BASE, "consent": {}})


def test_consent_satisfied_passes():
    res = run_intake(_BASE)
    assert res.case.candidate_drug.name == "fluconazole"
    assert res.rxcui_resolved is False


def test_pii_scrubbed_from_question():
    raw = {**_BASE, "question": "Call me at 555-123-4567 or me@example.com about MRN 12345"}
    res = run_intake(raw)
    assert "555-123-4567" not in res.case.question
    assert "me@example.com" not in res.case.question
    assert "[REDACTED]" in res.case.question
    assert "email" in res.redactions and "phone" in res.redactions


def test_identity_fields_dropped():
    raw = {**_BASE, "patient_name": "Jane Doe", "mrn": "A1234567"}
    res = run_intake(raw)
    assert any(r.startswith("field:") for r in res.redactions)
    # The validated case has no place to store the identity field.
    assert "patient_name" not in res.case.model_dump()
