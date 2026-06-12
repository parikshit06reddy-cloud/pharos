"""Idempotent seeding of the synthetic staff roster (front desk, admin, specialists)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from .auth import hash_password
from .db import get_engine
from .models import Role, User

_SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed"


def seed_users() -> int:
    users_file = _SEED_DIR / "users.json"
    specialists_file = _SEED_DIR / "specialists.json"
    if not users_file.exists():
        return 0
    users = json.loads(users_file.read_text())
    specialists = json.loads(specialists_file.read_text()) if specialists_file.exists() else {}

    created = 0
    with Session(get_engine()) as session:
        for u in users:
            exists = session.exec(select(User).where(User.username == u["username"])).first()
            if exists:
                continue
            prof = specialists.get(u["username"], {})
            session.add(
                User(
                    username=u["username"],
                    name=u["name"],
                    role=Role(u["role"]),
                    password_hash=hash_password(u["password"]),
                    specialty=u.get("specialty") or prof.get("specialty"),
                    expertise_keywords=prof.get("expertise_keywords", []),
                    drug_classes=prof.get("drug_classes", []),
                    capacity=prof.get("capacity", 6),
                    available=True,
                )
            )
            created += 1
        session.commit()
    return created
