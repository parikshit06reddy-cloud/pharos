"""Agent endpoints: streamed chat (SSE) + confirm for human-in-the-loop actions."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

from ..agent import get_agent
from ..agent import tools as agent_tools
from ..auth import get_current_user
from ..db import get_session
from ..models import User

router = APIRouter(prefix="/agent", tags=["agent"])


class ConfirmBody(BaseModel):
    action: dict


def _sse(payload: dict) -> str:
    return f"event: {payload['event']}\ndata: {json.dumps(jsonable_encoder(payload['data']))}\n\n"


@router.post("/chat")
async def chat(request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    body = await request.json()
    message = body.get("message", "")
    history = body.get("history", [])
    agent = get_agent()

    def gen():
        try:
            for ev in agent.respond(session, user, message, history):
                yield _sse(ev)
        except Exception as e:  # never crash the stream
            yield _sse({"event": "message", "data": {"text": f"Sorry, I hit an error: {e}"}})
        yield _sse({"event": "done", "data": {}})

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.post("/confirm")
def confirm(body: ConfirmBody, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    """Execute a previously proposed, confirm-required tool action."""
    tool_name = str(body.action.get("tool", ""))
    args = body.action.get("args", {})
    spec = agent_tools.REGISTRY.get(tool_name)
    if not spec or not spec.confirm_required:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown or non-confirmable action")
    result = spec.fn(session, user, **args)
    return {"executed": True, "tool": tool_name, "result": jsonable_encoder(result)}
