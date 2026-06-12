"""Data passport — declares what Pharos does and does not collect."""

from __future__ import annotations

PASSPORT = {
    "collects": [
        "Synthetic patient context provided per request (in memory only).",
        "Candidate drug and free-text clinical question.",
    ],
    "does_not_collect": [
        "Real patient identifiers (PHI) — blocked by the consent gate and PII scrubber.",
        "Names, MRNs, SSNs, emails, phone numbers, dates of birth (dropped/redacted at intake).",
    ],
    "retention": "In-memory per session; no server-side patient store.",
    "secondary_use": "None. Data is not used for training or analytics.",
    "telemetry": "Hash-only: the audit log stores a SHA-256 fingerprint of the case, never its contents.",
    "session_deletable": True,
    "knowledge_sources": "Public openFDA drug labels and RxNorm (curated, abbreviated excerpts offline).",
}


def passport(redactions_this_session: list[str] | None = None) -> dict:
    out = dict(PASSPORT)
    out["redactions_this_session"] = redactions_this_session or []
    return out
