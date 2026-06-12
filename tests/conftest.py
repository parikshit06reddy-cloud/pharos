"""Shared test fixtures. Routes the audit log + SQLite DB to throwaway temp files so tests
never touch real state, and resets them between tests."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

# Point storage at temp files BEFORE backend modules read the env vars.
_TMP = Path(tempfile.gettempdir())
os.environ["AUDIT_LOG_PATH"] = str(_TMP / "pharos_test_audit.jsonl")
os.environ["PHAROS_DB"] = str(_TMP / "pharos_test.db")

from backend.db import reset_db  # noqa: E402
from backend.governance import audit_log  # noqa: E402
from backend.seed import seed_users  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "data" / "synthetic_cases"


@pytest.fixture(autouse=True)
def _clean_audit():
    audit_log.reset()
    yield
    audit_log.reset()


@pytest.fixture
def cases() -> dict:
    return {p.stem: json.loads(p.read_text()) for p in sorted(CASES_DIR.glob("case*.json"))}


@pytest.fixture
def client():
    """A TestClient with a freshly reset + seeded database (lifespan active)."""
    from fastapi.testclient import TestClient

    from backend.app import app

    reset_db()
    seed_users()
    with TestClient(app) as c:
        yield c


def login(client, username: str, password: str = "pharos123") -> dict:
    out = client.post("/api/auth/login", json={"username": username, "password": password}).json()
    return {"Authorization": f"Bearer {out['token']}"}


def case_payload(case: dict) -> dict:
    return {k: v for k, v in case.items() if k != "_expected"}
