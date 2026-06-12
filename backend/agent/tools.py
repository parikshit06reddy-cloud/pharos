"""Agent tools — typed app actions the assistant can call.

Read-only tools execute immediately. State-changing tools (e.g. assign_case) are
CONFIRM_REQUIRED: the agent only ever *proposes* them; a human confirms in the UI
before they run (the 2026 human-in-the-loop validation contract; "options, not orders").
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session, select

from ..cases import service
from ..models import Case, User


@dataclass
class ToolSpec:
    name: str
    description: str
    confirm_required: bool
    fn: Callable


def _case_summary(c: Case) -> dict:
    return {
        "id": c.id,
        "case_ref": c.case_ref,
        "candidate_drug": c.candidate_drug,
        "status": c.status.value,
        "priority": c.priority.value,
        "triage_tier": c.triage_tier,
        "route_specialty": c.route_specialty,
        "assigned_doctor_id": c.assigned_doctor_id,
    }


def search_cases(
    session: Session, user: User, *, status: str | None = None, unassigned: bool = False, mine: bool = False
) -> dict:
    assigned_id = user.id if (mine and user.role.value == "doctor") else None
    cases = service.list_cases(session, status=status, assigned_doctor_id=assigned_id, unassigned=unassigned)
    return {"count": len(cases), "cases": [_case_summary(c) for c in cases[:10]]}


def get_case(session: Session, user: User, *, case_id: int) -> dict:
    return _case_summary(service.get_case_or_404(session, case_id))


def explain_brief(session: Session, user: User, *, case_id: int) -> dict:
    case = service.get_case_or_404(session, case_id)
    brief = case.brief_json or {}
    findings = [
        {"type": f.get("type"), "severity": f.get("severity"), "statement": f.get("statement")}
        for f in brief.get("findings", [])
    ]
    return {
        "case_ref": case.case_ref,
        "candidate_drug": case.candidate_drug,
        "triage_tier": case.triage_tier,
        "abstained": case.abstained,
        "answer": brief.get("answer", ""),
        "findings": findings,
    }


def who_is_expert(session: Session, user: User, *, case_id: int) -> dict:
    case = service.get_case_or_404(session, case_id)
    suggestions = case.route_suggestions or []
    return {
        "case_ref": case.case_ref,
        "suggestions": [
            {"specialty": s["specialty"], "name": s["name"], "score": s["score"], "rationale": s.get("rationale", "")}
            for s in suggestions[:3]
        ],
    }


def my_worklist(session: Session, user: User) -> dict:
    if user.role.value != "doctor":
        return {"count": 0, "cases": [], "note": "Only doctors have a personal worklist."}
    cases = service.list_cases(session, assigned_doctor_id=user.id)
    return {"count": len(cases), "cases": [_case_summary(c) for c in cases[:10]]}


def assign_case(session: Session, user: User, *, case_id: int, doctor_id: int) -> dict:
    """STATE-CHANGING — only runs after human confirmation."""
    case = service.get_case_or_404(session, case_id)
    case = service.assign_case(session, case, doctor_id, actor=user.username)
    return {"assigned": True, **_case_summary(case)}


REGISTRY: dict[str, ToolSpec] = {
    "search_cases": ToolSpec("search_cases", "List cases by queue/status.", False, search_cases),
    "get_case": ToolSpec("get_case", "Get one case summary.", False, get_case),
    "explain_brief": ToolSpec("explain_brief", "Explain a case's decision brief.", False, explain_brief),
    "who_is_expert": ToolSpec("who_is_expert", "Suggest the best specialist for a case.", False, who_is_expert),
    "my_worklist": ToolSpec("my_worklist", "List cases assigned to the current doctor.", False, my_worklist),
    "assign_case": ToolSpec("assign_case", "Assign a case to a doctor.", True, assign_case),
}


def resolve_doctor(session: Session, *, name: str | None = None, specialty: str | None = None) -> User | None:
    docs = session.exec(select(User).where(User.role == "doctor")).all()
    if specialty:
        for d in docs:
            if (d.specialty or "").lower() == specialty.lower():
                return d
    if name:
        nl = name.lower()
        for d in docs:
            if nl in d.name.lower() or nl in d.username.lower():
                return d
    return None
