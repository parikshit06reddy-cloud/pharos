"""SQLModel tables for the enterprise workflow: users/specialists, cases, and the
per-case event timeline. All data is synthetic and no-PHI (the consent gate + PII
scrubber run on every inbound case before it is stored).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Role(str, Enum):
    front_desk = "front_desk"
    doctor = "doctor"
    admin = "admin"


class CaseStatus(str, Enum):
    new = "new"  # created at intake
    triaged = "triaged"  # Decision Brief generated
    routed = "routed"  # routing suggestions computed
    assigned = "assigned"  # assigned to a named doctor
    in_review = "in_review"  # doctor picked it up
    completed = "completed"
    returned = "returned"  # sent back to front desk
    escalated = "escalated"


class Priority(str, Enum):
    routine = "routine"
    urgent = "urgent"
    emergent = "emergent"


def utcnow() -> datetime:
    # Naive UTC: SQLite does not preserve tzinfo, so we keep all timestamps naive-UTC
    # for consistent comparisons across the app.
    return datetime.now(UTC).replace(tzinfo=None)


class User(SQLModel, table=True):
    """A staff member. Doctors also carry their specialist expertise profile inline."""

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    name: str
    role: Role
    password_hash: str
    # Specialist profile (doctors only):
    specialty: str | None = None
    expertise_keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    drug_classes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    capacity: int = 6
    available: bool = True


class Case(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_ref: str = Field(index=True, unique=True)
    title: str
    status: CaseStatus = Field(default=CaseStatus.new, index=True)
    priority: Priority = Priority.routine

    candidate_drug: str
    question: str
    patient_json: dict = Field(default_factory=dict, sa_column=Column(JSON))  # de-identified synthetic context
    brief_json: dict | None = Field(default=None, sa_column=Column(JSON))  # Decision Brief

    triage_tier: str | None = None
    abstained: bool = False
    injection_detected: bool = False

    route_specialty: str | None = None  # top suggested specialty
    route_suggestions: list = Field(default_factory=list, sa_column=Column(JSON))
    assigned_doctor_id: int | None = Field(default=None, foreign_key="user.id", index=True)

    created_by: str | None = None  # username
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    target_window_minutes: int | None = None  # SLA target


class CaseEvent(SQLModel, table=True):
    """Per-case activity timeline. Mirrors entries also written to the hash-chained audit log."""

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(index=True, foreign_key="case.id")
    type: str  # created | triaged | routed | assigned | picked_up | completed | ...
    actor: str | None = None  # username
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
