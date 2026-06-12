"""SQLite persistence via SQLModel. Synthetic, no-PHI data only.

The engine is built from the PHAROS_DB env var (default data/pharos.db) so tests can
point at a throwaway file. `reset_db()` drops + recreates every table for test isolation.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

_DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "pharos.db"


def _db_url() -> str:
    raw = os.getenv("PHAROS_DB", str(_DEFAULT_DB))
    if raw == ":memory:":
        return "sqlite://"
    Path(raw).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{raw}"


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(_db_url(), connect_args={"check_same_thread": False})


def init_db() -> None:
    # Import models so their tables register on SQLModel.metadata before create_all.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def reset_db() -> None:
    from . import models  # noqa: F401

    eng = get_engine()
    SQLModel.metadata.drop_all(eng)
    SQLModel.metadata.create_all(eng)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
