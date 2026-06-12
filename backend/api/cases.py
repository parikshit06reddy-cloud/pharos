"""Case lifecycle endpoints: intake -> route -> assign -> pick up -> resolve."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlmodel import Session

from ..auth import get_current_user, require_roles
from ..cases import service
from ..db import get_session
from ..models import Case, CaseEvent, Role, User

router = APIRouter(prefix="/cases", tags=["cases"])


class AssignBody(BaseModel):
    doctor_id: int


class ResolveBody(BaseModel):
    outcome: str  # complete | return | escalate
    note: str | None = None


def _summary(case: Case) -> dict:
    return {
        "id": case.id,
        "case_ref": case.case_ref,
        "title": case.title,
        "status": case.status.value,
        "priority": case.priority.value,
        "candidate_drug": case.candidate_drug,
        "triage_tier": case.triage_tier,
        "abstained": case.abstained,
        "injection_detected": case.injection_detected,
        "route_specialty": case.route_specialty,
        "assigned_doctor_id": case.assigned_doctor_id,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "target_window_minutes": case.target_window_minutes,
    }


def _event_dict(e: CaseEvent) -> dict:
    return {"type": e.type, "actor": e.actor, "detail": e.detail, "created_at": e.created_at.isoformat()}


def _detail(session: Session, case: Case) -> dict:
    doctor = session.get(User, case.assigned_doctor_id) if case.assigned_doctor_id else None
    return {
        **_summary(case),
        "question": case.question,
        "patient": case.patient_json,
        "brief": case.brief_json,
        "route_suggestions": case.route_suggestions,
        "assigned_doctor": {"id": doctor.id, "name": doctor.name, "specialty": doctor.specialty} if doctor else None,
        "timeline": [_event_dict(e) for e in service.timeline(session, case.id)] if case.id else [],
    }


@router.post("")
def create_case(
    payload: dict = Body(...),
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.front_desk, Role.admin)),
) -> dict:
    case = service.create_case(session, payload, created_by=user.username)
    return _detail(session, case)


@router.get("")
def list_cases(
    status: str | None = None,
    mine: bool = False,
    unassigned: bool = False,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict]:
    assigned_id = user.id if (mine and user.role == Role.doctor) else None
    cases = service.list_cases(session, status=status, assigned_doctor_id=assigned_id, unassigned=unassigned)
    return [_summary(c) for c in cases]


@router.get("/{case_id}")
def get_case(case_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)) -> dict:
    case = service.get_case_or_404(session, case_id)
    return _detail(session, case)


@router.post("/{case_id}/route")
def route_case(
    case_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.front_desk, Role.admin)),
) -> dict:
    case = service.get_case_or_404(session, case_id)
    case = service.route_case(session, case, actor=user.username)
    return _detail(session, case)


@router.post("/{case_id}/assign")
def assign_case(
    case_id: int,
    body: AssignBody,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.front_desk, Role.admin)),
) -> dict:
    case = service.get_case_or_404(session, case_id)
    case = service.assign_case(session, case, body.doctor_id, actor=user.username)
    return _detail(session, case)


@router.post("/{case_id}/pickup")
def pickup_case(
    case_id: int, session: Session = Depends(get_session), user: User = Depends(require_roles(Role.doctor))
) -> dict:
    case = service.get_case_or_404(session, case_id)
    case = service.pick_up(session, case, user)
    return _detail(session, case)


@router.post("/{case_id}/resolve")
def resolve_case(
    case_id: int,
    body: ResolveBody,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles(Role.doctor)),
) -> dict:
    case = service.get_case_or_404(session, case_id)
    case = service.resolve(session, case, user, body.outcome, body.note)
    return _detail(session, case)


@router.get("/{case_id}/timeline")
def case_timeline(
    case_id: int, session: Session = Depends(get_session), _: User = Depends(get_current_user)
) -> list[dict]:
    service.get_case_or_404(session, case_id)
    return [_event_dict(e) for e in service.timeline(session, case_id)]
