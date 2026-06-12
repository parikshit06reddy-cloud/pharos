"""Agent contract. A provider turns a user message (+ history) into a stream of events:
optional tool calls (read-only, executed inline) and a final assistant message that may
carry a proposed (confirm-required) action."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from sqlmodel import Session

from ..models import User


@runtime_checkable
class AgentProvider(Protocol):
    def respond(self, session: Session, user: User, message: str, history: list[dict]) -> Iterator[dict]: ...


def event(name: str, **data) -> dict:
    return {"event": name, "data": data}
