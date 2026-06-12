"""Dashboard KPIs: queue counts, unassigned, overdue, and per-specialty load."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, func, select

from ..auth import get_current_user
from ..db import get_session
from ..models import Case, CaseStatus, User, utcnow

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_OPEN = [
    CaseStatus.new,
    CaseStatus.triaged,
    CaseStatus.routed,
    CaseStatus.assigned,
    CaseStatus.in_review,
    CaseStatus.escalated,
]


@router.get("/metrics")
def metrics(session: Session = Depends(get_session), _: User = Depends(get_current_user)) -> dict:
    by_status: dict[str, int] = {}
    for s in CaseStatus:
        n = session.exec(select(func.count(col(Case.id))).where(Case.status == s)).one() or 0
        by_status[s.value] = int(n)

    unassigned = (
        session.exec(
            select(func.count(col(Case.id))).where(col(Case.assigned_doctor_id).is_(None), col(Case.status).in_(_OPEN))
        ).one()
        or 0
    )

    # Overdue: open cases past their SLA target window.
    now = utcnow()
    overdue = 0
    for c in session.exec(select(Case).where(col(Case.status).in_(_OPEN))).all():
        if c.target_window_minutes and (c.created_at + timedelta(minutes=c.target_window_minutes)) < now:
            overdue += 1

    by_specialty: list[dict] = []
    for d in session.exec(select(User).where(User.role == "doctor")).all():
        load = (
            session.exec(
                select(func.count(col(Case.id))).where(
                    Case.assigned_doctor_id == d.id,
                    col(Case.status).in_([CaseStatus.assigned, CaseStatus.in_review]),
                )
            ).one()
            or 0
        )
        by_specialty.append(
            {
                "specialty": d.specialty,
                "name": d.name,
                "load": int(load),
                "capacity": d.capacity,
                "available": d.available,
            }
        )

    return {
        "by_status": by_status,
        "open": sum(by_status[s.value] for s in _OPEN),
        "unassigned": int(unassigned),
        "overdue": overdue,
        "by_specialty": by_specialty,
    }
