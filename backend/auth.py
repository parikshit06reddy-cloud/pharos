"""Demo-grade authentication: seeded users, salted password hashes (stdlib pbkdf2),
and signed bearer tokens (itsdangerous). Role dependencies gate the API.

This is intentionally lightweight for a synthetic demo. A production deployment would
swap this for hospital SSO / OIDC — the role dependencies below are the seam.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import Depends, Header, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlmodel import Session, select

from .db import get_session
from .models import Role, User

_SECRET = os.getenv("PHAROS_SECRET", "pharos-dev-secret-not-for-production")
_TOKEN_MAX_AGE = int(os.getenv("PHAROS_TOKEN_TTL", "43200"))  # 12h
_serializer = URLSafeTimedSerializer(_SECRET, salt="pharos-auth")


# --- passwords ----------------------------------------------------------------
def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return f"{salt}${dk}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, dk = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return hmac.compare_digest(calc, dk)


# --- tokens -------------------------------------------------------------------
def create_token(user: User) -> str:
    return _serializer.dumps({"uid": user.id, "username": user.username, "role": user.role.value})


def decode_token(token: str) -> dict | None:
    try:
        return _serializer.loads(token, max_age=_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


# --- FastAPI dependencies -----------------------------------------------------
def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    payload = decode_token(authorization.split(" ", 1)[1].strip())
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = session.exec(select(User).where(User.id == payload["uid"])).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def require_roles(*roles: Role):
    allowed = {r.value if isinstance(r, Role) else r for r in roles}

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"Requires role in {sorted(allowed)}; you are {user.role.value}"
            )
        return user

    return _dep
