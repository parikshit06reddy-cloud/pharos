"""LocalAgent — deterministic, offline intent router over the app tools.

Maps a natural-language request to one tool, runs read-only tools inline, and proposes
(but never executes) state-changing tools. Zero credentials. The FoundryAgent swaps in an
LLM ReAct loop with the same event contract.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from sqlmodel import Session

from ..models import User
from . import tools
from .base import event


def _extract_case_id(text: str) -> int | None:
    m = (
        re.search(r"case[-\s#]*0*(\d+)", text, re.IGNORECASE)
        or re.search(r"#(\d+)", text)
        or re.search(r"\b(\d{1,5})\b", text)
    )
    return int(m.group(1)) if m else None


class LocalAgent:
    def respond(self, session: Session, user: User, message: str, history: list[dict]) -> Iterator[dict]:
        msg = message.lower().strip()
        case_id = _extract_case_id(msg)

        # 1) Assign (state-changing -> propose, do not execute)
        if "assign" in msg:
            yield from self._propose_assign(session, user, msg, case_id)
            return

        # 2) Who is the expert / how should this route
        if any(k in msg for k in ("who", "expert", "specialist", "route", "refer")) and "assign" not in msg:
            yield from self._who(session, user, case_id)
            return

        # 3) My worklist
        if any(k in msg for k in ("my worklist", "my cases", "assigned to me", "my queue")):
            res = tools.my_worklist(session, user)
            yield event("tool", tool="my_worklist", result=res)
            yield event("message", text=_fmt_cases("Your worklist", res), navigate="/worklist")
            return

        # 4) Unassigned / queue
        if any(k in msg for k in ("unassigned", "queue", "pending", "waiting", "to assign")):
            res = tools.search_cases(session, user, unassigned=True)
            yield event("tool", tool="search_cases", result=res)
            yield event("message", text=_fmt_cases("Unassigned cases", res), navigate="/cases")
            return

        # 5) Explain a brief / why
        if any(k in msg for k in ("explain", "why", "summar", "brief")) and case_id:
            res = tools.explain_brief(session, user, case_id=case_id)
            yield event("tool", tool="explain_brief", result=res)
            yield event("message", text=_fmt_brief(res), navigate=f"/cases/{case_id}")
            return

        # 6) Show / open a specific case
        if case_id and any(k in msg for k in ("show", "open", "case", "view", "go")):
            try:
                res = tools.get_case(session, user, case_id=case_id)
            except Exception:
                yield event("message", text=f"I couldn't find case {case_id}.")
                return
            yield event("tool", tool="get_case", result=res)
            yield event(
                "message",
                text=f"{res['case_ref']} — {res['candidate_drug']} ({res['status']}, "
                f"{res['priority']}). Opening it for you.",
                navigate=f"/cases/{case_id}",
            )
            return

        # 7) Navigate
        nav = _nav_target(msg)
        if nav:
            yield event("message", text=f"Opening {nav['label']}.", navigate=nav["to"])
            return

        # 8) Help
        yield event("message", text=_HELP)

    # --- handlers -------------------------------------------------------------
    def _who(self, session: Session, user: User, case_id: int | None) -> Iterator[dict]:
        if not case_id:
            res = tools.search_cases(session, user, unassigned=True)
            if not res["cases"]:
                yield event("message", text='Which case? Tell me a case number, e.g. "who is the expert for case 2".')
                return
            case_id = res["cases"][0]["id"]
        try:
            res = tools.who_is_expert(session, user, case_id=case_id)
        except Exception:
            yield event("message", text=f"I couldn't find case {case_id}.")
            return
        yield event("tool", tool="who_is_expert", result=res)
        lines = [f"For {res['case_ref']}, the best-matched specialists are:"]
        for i, s in enumerate(res["suggestions"]):
            tag = " (best match)" if i == 0 else ""
            lines.append(f"• {s['specialty']} — {s['name']} · {round(s['score'] * 100)}%{tag}. {s['rationale']}")
        lines.append(
            'Say e.g. "assign case '
            f"{case_id} to {res['suggestions'][0]['specialty']}\" and I'll prepare it for your confirmation."
            if res["suggestions"]
            else ""
        )
        yield event("message", text="\n".join(l for l in lines if l), navigate=f"/cases/{case_id}")

    def _propose_assign(self, session: Session, user: User, msg: str, case_id: int | None) -> Iterator[dict]:
        if user.role.value not in ("front_desk", "admin"):
            yield event("message", text="Only front-desk or admin can assign cases.")
            return
        if not case_id:
            yield event("message", text="Which case should I assign? Include a case number.")
            return
        try:
            case = tools.get_case(session, user, case_id=case_id)
        except Exception:
            yield event("message", text=f"I couldn't find case {case_id}.")
            return

        # Resolve target doctor: by specialty name, doctor name, or 'best match'.
        doctor = None
        specialty = _match_specialty(msg)
        if specialty:
            doctor = tools.resolve_doctor(session, specialty=specialty)
        if not doctor and ("best" in msg or "recommend" in msg or "suggested" in msg):
            sugg = tools.who_is_expert(session, user, case_id=case_id)["suggestions"]
            if sugg:
                doctor = tools.resolve_doctor(session, specialty=sugg[0]["specialty"])
        if not doctor:
            doctor = tools.resolve_doctor(session, name=_match_name(msg))
        if not doctor:
            # Fall back to the case's top routing suggestion.
            sugg = tools.who_is_expert(session, user, case_id=case_id)["suggestions"]
            if sugg:
                doctor = tools.resolve_doctor(session, specialty=sugg[0]["specialty"])
        if not doctor:
            yield event(
                "message", text='I couldn\'t tell which doctor to assign. Try "assign case 2 to the best match".'
            )
            return

        summary = f"Assign {case['case_ref']} ({case['candidate_drug']}) to {doctor.name} ({doctor.specialty})."
        evidence = f"Case triage: {case['triage_tier']}; suggested specialty: {case['route_specialty']}."
        action = {
            "tool": "assign_case",
            "args": {"case_id": case_id, "doctor_id": doctor.id},
            "summary": summary,
            "evidence": evidence,
        }
        yield event(
            "message",
            text=f"I can assign {case['case_ref']} to {doctor.name} ({doctor.specialty}). Confirm to proceed.",
            proposed_action=action,
        )


# --- formatting helpers -------------------------------------------------------
_HELP = (
    "I can help you navigate Pharos. Try:\n"
    '• "show unassigned cases"\n'
    '• "who is the expert for case 2"\n'
    '• "assign case 2 to the best match" (you\'ll confirm)\n'
    '• "explain the brief for case 2"\n'
    '• "my worklist" · "go to dashboard"'
)


def _fmt_cases(title: str, res: dict) -> str:
    if not res["cases"]:
        return f"{title}: none right now."
    lines = [f"{title} ({res['count']}):"]
    for c in res["cases"]:
        lines.append(
            f"• {c['case_ref']} — {c['candidate_drug']} ({c['status']}, {c['priority']})"
            + (f" -> {c['route_specialty']}" if c["route_specialty"] else "")
        )
    return "\n".join(lines)


def _fmt_brief(res: dict) -> str:
    head = f"{res['case_ref']} — {res['candidate_drug']}: triage {res['triage_tier']}" + (
        " (abstained)" if res["abstained"] else ""
    )
    flags = "; ".join(f"{f['severity']} {f['type']}" for f in res["findings"]) or "no safety flags"
    return f"{head}.\nFlags: {flags}.\n{res['answer'][:300]}"


_SPECIALTIES = [
    "hematology",
    "cardiology",
    "nephrology",
    "infectious disease",
    "psychiatry",
    "dermatology",
    "toxicology",
    "general medicine",
]


def _match_specialty(msg: str) -> str | None:
    for s in _SPECIALTIES:
        if s in msg:
            return s
    return None


def _match_name(msg: str) -> str | None:
    m = re.search(r"\bto\s+(?:dr\.?\s+)?([a-z]+)", msg, re.IGNORECASE)
    return m.group(1) if m else None


def _nav_target(msg: str) -> dict | None:
    if "dashboard" in msg:
        return {"to": "/dashboard", "label": "the dashboard"}
    if "intake" in msg or "new case" in msg:
        return {"to": "/intake", "label": "new case intake"}
    if "all cases" in msg or "cases" in msg:
        return {"to": "/cases", "label": "all cases"}
    if "quick brief" in msg:
        return {"to": "/quick-brief", "label": "quick brief"}
    return None
