"""Auth + roster endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..auth import create_token, get_current_user, verify_password
from ..db import get_session
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


def _public(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "role": user.role.value,
        "specialty": user.specialty,
    }


@router.post("/login")
def login(body: LoginBody, session: Session = Depends(get_session)) -> dict:
    user = session.exec(select(User).where(User.username == body.username)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    return {"token": create_token(user), "user": _public(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return _public(user)


@router.get("/specialists")
def specialists(session: Session = Depends(get_session), _: User = Depends(get_current_user)) -> list[dict]:
    docs = session.exec(select(User).where(User.role == "doctor")).all()
    return [
        {**_public(d), "expertise_keywords": d.expertise_keywords, "capacity": d.capacity, "available": d.available}
        for d in docs
    ]
