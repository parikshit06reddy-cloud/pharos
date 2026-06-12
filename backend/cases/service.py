"""Case lifecycle: create (intake + triage Decision Brief + route), assign, pick up,
complete / return / escalate. Enforces the status state machine and records a
CaseEvent timeline. All inbound cases pass the consent gate + PII scrubber first.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi import status as http
from sqlmodel import Session, col, func, select

from ..governance import audit_log
from ..intake import ConsentError, run_intake
from ..models import Case, CaseEvent, CaseStatus, Priority, User
from ..pipeline import run_to_brief
from ..retrieval import get_provider
from ..retrieval.base import normalize_name
from ..routing import RoutingContext, get_router

# Allowed status transitions (state machine).
_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.new: {CaseStatus.triaged},
    CaseStatus.triaged: {CaseStatus.routed},
    CaseStatus.routed: {CaseStatus.assigned, CaseStatus.escalated},
    CaseStatus.assigned: {CaseStatus.in_review, CaseStatus.routed, CaseStatus.escalated},
    CaseStatus.in_review: {CaseStatus.completed, CaseStatus.returned, CaseStatus.escalated},
    CaseStatus.returned: {CaseStatus.routed, CaseStatus.assigned},
    CaseStatus.escalated: {CaseStatus.assigned, CaseStatus.in_review, CaseStatus.completed},
    CaseStatus.completed: set(),
}

_TARGET_WINDOW = {Priority.emergent: 15, Priority.urgent: 60, Priority.routine: 1440}


def _event(session: Session, case: Case, type_: str, actor: str | None, detail: dict | None = None) -> None:
    session.add(CaseEvent(case_id=case.id, type=type_, actor=actor, detail=detail or {}))
    # Mirror into the tamper-evident, PHI-free hash chain.
    audit_log.append_event(
        case_ref=case.case_ref, event_type=type_, actor=actor, candidate=case.candidate_drug, detail=detail or {}
    )


def _next_ref(session: Session) -> str:
    n = session.exec(select(func.count(col(Case.id)))).one()
    return f"CASE-{(n or 0) + 1:04d}"


def _priority(brief) -> Priority:
    if brief.emergency_resources:
        return Priority.emergent
    if brief.triage_tier.value == "urgent":
        return Priority.urgent
    return Priority.routine


def build_routing_context(case: Case) -> RoutingContext:
    """Assemble a rich query from the case + its brief for the router."""
    provider = get_provider()
    classes_idx = getattr(provider, "drug_classes", {})
    patient = case.patient_json or {}
    drug_terms = [case.candidate_drug] + [m.get("name", "") for m in patient.get("current_medications", [])]
    drug_classes: list[str] = []
    for name in drug_terms:
        drug_classes += classes_idx.get(normalize_name(name), [])
    conditions = [c.get("name", "") for c in patient.get("conditions", [])]
    brief = case.brief_json or {}
    findings = brief.get("findings", [])
    finding_types = [f.get("type", "") for f in findings]
    finding_text = " ".join(f.get("statement", "") for f in findings)
    return RoutingContext(
        question=case.question,
        candidate_drug=case.candidate_drug,
        drug_terms=[t for t in drug_terms if t],
        drug_classes=drug_classes,
        conditions=conditions,
        finding_types=finding_types,
        finding_text=finding_text,
        emergency=bool(brief.get("emergency_resources")),
    )


def _specialist_dtos(session: Session) -> list[dict]:
    """Doctors with their live load (count of active cases) for the router."""
    doctors = session.exec(select(User).where(User.role == "doctor")).all()
    out = []
    for d in doctors:
        load = (
            session.exec(
                select(func.count(col(Case.id))).where(
                    Case.assigned_doctor_id == d.id,
                    col(Case.status).in_([CaseStatus.assigned, CaseStatus.in_review]),
                )
            ).one()
            or 0
        )
        out.append(
            {
                "id": d.id,
                "name": d.name,
                "specialty": d.specialty or "General Medicine",
                "expertise_keywords": d.expertise_keywords,
                "drug_classes": d.drug_classes,
                "capacity": d.capacity,
                "current_load": int(load),
                "available": d.available,
            }
        )
    return out


def route_case(session: Session, case: Case, actor: str | None = None) -> Case:
    ctx = build_routing_context(case)
    specialists = _specialist_dtos(session)
    matches = get_router().route(ctx, specialists)
    case.route_suggestions = [m.as_dict() for m in matches]
    case.route_specialty = matches[0].specialty if matches else None
    if case.status in (CaseStatus.triaged,):
        case.status = CaseStatus.routed
    _event(
        session, case, "routed", actor, {"top": case.route_specialty, "suggestions": [m.specialty for m in matches[:3]]}
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def create_case(session: Session, raw_case: dict, created_by: str | None = None) -> Case:
    # 1) Consent gate + PII scrub + Decision Brief pipeline.
    try:
        intake = run_intake(raw_case)
        brief = run_to_brief(raw_case)
    except ConsentError as e:
        raise HTTPException(http.HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": "consent", "detail": str(e)}) from e

    case = Case(
        case_ref=_next_ref(session),
        title=raw_case.get("title") or f"{intake.case.candidate_drug.name} — {intake.case.question[:60]}",
        status=CaseStatus.triaged,
        priority=_priority(brief),
        candidate_drug=intake.case.candidate_drug.name,
        question=intake.case.question,
        patient_json=intake.case.model_dump(),
        brief_json=brief.model_dump(mode="json"),
        triage_tier=brief.triage_tier.value,
        abstained=brief.abstained,
        injection_detected=bool(brief.safety_flags.get("injection_detected")),
        created_by=created_by,
        target_window_minutes=_TARGET_WINDOW[_priority(brief)],
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    _event(session, case, "created", created_by, {"candidate": case.candidate_drug})
    _event(session, case, "triaged", created_by, {"tier": case.triage_tier, "abstained": case.abstained})
    session.commit()
    session.refresh(case)

    # 2) Auto-compute routing suggestions so the front desk can act immediately.
    return route_case(session, case, actor=created_by)


# --- lifecycle transitions ----------------------------------------------------
def _require_transition(case: Case, target: CaseStatus) -> None:
    if target not in _TRANSITIONS.get(case.status, set()):
        raise HTTPException(http.HTTP_409_CONFLICT, f"Cannot move case from {case.status.value} to {target.value}")


def assign_case(session: Session, case: Case, doctor_id: int, actor: str | None) -> Case:
    doctor = session.get(User, doctor_id)
    if not doctor or doctor.role.value != "doctor":
        raise HTTPException(http.HTTP_400_BAD_REQUEST, "Target is not a doctor")
    if case.status not in (CaseStatus.routed, CaseStatus.returned, CaseStatus.escalated, CaseStatus.assigned):
        _require_transition(case, CaseStatus.assigned)
    case.assigned_doctor_id = doctor_id
    case.status = CaseStatus.assigned
    _touch(session, case)
    _event(
        session, case, "assigned", actor, {"doctor_id": doctor_id, "doctor": doctor.name, "specialty": doctor.specialty}
    )
    return _save(session, case)


def pick_up(session: Session, case: Case, doctor: User) -> Case:
    if case.assigned_doctor_id != doctor.id:
        raise HTTPException(http.HTTP_403_FORBIDDEN, "Case is not assigned to you")
    _require_transition(case, CaseStatus.in_review)
    case.status = CaseStatus.in_review
    _touch(session, case)
    _event(session, case, "picked_up", doctor.username, {})
    return _save(session, case)


def resolve(session: Session, case: Case, doctor: User, outcome: str, note: str | None) -> Case:
    target = {"complete": CaseStatus.completed, "return": CaseStatus.returned, "escalate": CaseStatus.escalated}.get(
        outcome
    )
    if target is None:
        raise HTTPException(http.HTTP_400_BAD_REQUEST, "outcome must be complete|return|escalate")
    _require_transition(case, target)
    case.status = target
    _touch(session, case)
    _event(session, case, outcome, doctor.username, {"note": note} if note else {})
    return _save(session, case)


def list_cases(
    session: Session, *, status: str | None = None, assigned_doctor_id: int | None = None, unassigned: bool = False
) -> list[Case]:
    q = select(Case)
    if status:
        q = q.where(Case.status == status)
    if assigned_doctor_id is not None:
        q = q.where(Case.assigned_doctor_id == assigned_doctor_id)
    if unassigned:
        q = q.where(col(Case.assigned_doctor_id).is_(None))
    return list(session.exec(q.order_by(col(Case.created_at).desc())).all())


def get_case_or_404(session: Session, case_id: int) -> Case:
    case = session.get(Case, case_id)
    if not case:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "Case not found")
    return case


def timeline(session: Session, case_id: int) -> list[CaseEvent]:
    return list(
        session.exec(select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(col(CaseEvent.created_at))).all()
    )


def _touch(session: Session, case: Case) -> None:
    from ..models import utcnow

    case.updated_at = utcnow()


def _save(session: Session, case: Case) -> Case:
    session.add(case)
    session.commit()
    session.refresh(case)
    return case
