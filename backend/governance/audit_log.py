"""Append-only, hash-chained audit log — tamper-evident and PHI-free.

Each entry stores a SHA-256 *fingerprint* of the case (never raw PHI), plus what the
agent did (candidate, citation keys, triage tier, flags) and the previous entry's hash.
`verify_chain()` detects tampering; `purge_case()` removes a session's rows and re-chains
so the chain stays valid after a one-tap delete. See SAFETY.md §5.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent / "audit_log.jsonl"
_LOCK = threading.Lock()
_GENESIS = "0" * 64


def _path() -> Path:
    return Path(os.getenv("AUDIT_LOG_PATH", _DEFAULT_PATH))


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _hash(prev_hash: str, payload: dict) -> str:
    return hashlib.sha256((prev_hash + _canonical(payload)).encode()).hexdigest()


def case_fingerprint(raw_case: dict) -> str:
    """A stable SHA-256 over the case content — proves integrity without storing PHI."""
    return hashlib.sha256(_canonical(raw_case or {}).encode()).hexdigest()


def _read_raw() -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _write_all(entries: list[dict]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(_canonical(e) + "\n" for e in entries))


def _payload(seq: int, prev_hash: str, **fields) -> dict:
    return {
        "seq": seq,
        "timestamp": fields.pop("timestamp", datetime.now(UTC).isoformat()),
        "case_id": fields.get("case_id"),
        "candidate_drug": fields.get("candidate"),
        "model_version": fields.get("model_version"),
        "citation_keys": sorted(fields.get("citation_keys", [])),
        "triage_tier": fields.get("triage_tier"),
        "abstained": fields.get("abstained"),
        "injection_detected": fields.get("injection_detected"),
        "case_fingerprint": fields.get("case_fp"),
        "prev_hash": prev_hash,
    }


def append(**fields) -> dict:
    with _LOCK:
        entries = _read_raw()
        prev_hash = entries[-1]["hash"] if entries else _GENESIS
        payload = _payload(len(entries), prev_hash, **fields)
        payload["hash"] = _hash(prev_hash, payload)
        entries.append(payload)
        _write_all(entries)
        return payload


def append_event(
    case_ref: str, event_type: str, actor: str | None = None, candidate: str | None = None, detail: dict | None = None
) -> dict:
    """Append a tamper-evident WORKFLOW event (route/assign/pickup/complete/...).

    Stored in the same hash chain as decision-brief rows, with no PHI — only the case
    reference, the action, the actor (a staff username), and a small detail dict.
    """
    with _LOCK:
        entries = _read_raw()
        prev_hash = entries[-1]["hash"] if entries else _GENESIS
        payload = {
            "seq": len(entries),
            "timestamp": datetime.now(UTC).isoformat(),
            "kind": "workflow_event",
            "case_id": case_ref,
            "candidate_drug": candidate,
            "event_type": event_type,
            "actor": actor,
            "detail": detail or {},
            "prev_hash": prev_hash,
        }
        payload["hash"] = _hash(prev_hash, payload)
        entries.append(payload)
        _write_all(entries)
        return payload


def entries() -> list[dict]:
    return _read_raw()


def verify_chain() -> bool:
    prev = _GENESIS
    for i, e in enumerate(_read_raw()):
        body = {k: v for k, v in e.items() if k != "hash"}
        if body.get("prev_hash") != prev or body.get("seq") != i:
            return False
        if _hash(prev, body) != e.get("hash"):
            return False
        prev = e["hash"]
    return True


def purge_case(case_id: str) -> int:
    """Remove all rows for a case/session and re-chain. Returns rows removed."""
    with _LOCK:
        entries = _read_raw()
        kept = [e for e in entries if e.get("case_id") != case_id]
        removed = len(entries) - len(kept)
        if not removed:
            return 0
        prev = _GENESIS
        rechained = []
        for i, e in enumerate(kept):
            body = {k: v for k, v in e.items() if k != "hash"}
            body["seq"] = i
            body["prev_hash"] = prev
            body["hash"] = _hash(prev, body)
            prev = body["hash"]
            rechained.append(body)
        _write_all(rechained)
        return removed


def reset() -> None:
    """Test helper: clear the log file."""
    p = _path()
    if p.exists():
        p.unlink()
