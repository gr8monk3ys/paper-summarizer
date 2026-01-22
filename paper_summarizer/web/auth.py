"""Authentication helpers and routes."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import bcrypt
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import select

from .deps import _get_settings, _get_engine
from .db import get_session
from .models import User
from .ratelimit import login_attempt_tracker


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# In-memory token blacklist. Tokens expire naturally after their TTL,
# so this set won't grow unboundedly in practice.
_token_blacklist: set[str] = set()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str, secret: str, expires_minutes: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire, "jti": str(uuid4())}
    return pyjwt.encode(payload, secret, algorithm="HS256")


@router.post("/register")
def register(request: Request, payload: RegisterRequest) -> dict:
    engine = _get_engine(request)
    with get_session(engine) as session:
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(
            email=payload.email, hashed_password=hash_password(payload.password)
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    settings = _get_settings(request)
    token = create_access_token(
        user.id, settings["SECRET_KEY"], settings["ACCESS_TOKEN_EXPIRE_MINUTES"]
    )
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(request: Request, payload: LoginRequest) -> dict:
    email = payload.email.lower()

    # Brute-force protection: block if too many recent failures for this email
    if login_attempt_tracker.is_blocked(email):
        logger.warning(
            "Login blocked (too many failures) for email=%s from ip=%s",
            email,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
        )

    engine = _get_engine(request)
    with get_session(engine) as session:
        user = session.exec(select(User).where(User.email == payload.email)).first()
        if not user or not verify_password(payload.password, user.hashed_password):
            login_attempt_tracker.record_failure(email)
            logger.warning(
                "Failed login attempt for email=%s from ip=%s",
                payload.email,
                request.client.host if request.client else "unknown",
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")

    # Successful login resets the failure counter
    login_attempt_tracker.reset(email)

    settings = _get_settings(request)
    token = create_access_token(
        user.id, settings["SECRET_KEY"], settings["ACCESS_TOKEN_EXPIRE_MINUTES"]
    )
    return {"access_token": token, "token_type": "bearer"}


def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> User:
    settings = _get_settings(request)
    client_ip = request.client.host if request.client else "unknown"

    try:
        payload = pyjwt.decode(
            token,
            settings["SECRET_KEY"],
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        user_id = payload.get("sub")
        jti = payload.get("jti")
        if jti and jti in _token_blacklist:
            raise HTTPException(status_code=401, detail="Token revoked")
    except ExpiredSignatureError as exc:
        logger.warning("Expired token from ip=%s", client_ip)
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except (InvalidTokenError, KeyError) as exc:
        logger.warning("Invalid token from ip=%s", client_ip)
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    engine = _get_engine(request)
    with get_session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    authorization: str = Header(),
) -> dict:
    raw_token = authorization.removeprefix("Bearer ").strip()
    settings = _get_settings(request)
    try:
        payload = pyjwt.decode(
            raw_token,
            settings["SECRET_KEY"],
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
    except (ExpiredSignatureError, InvalidTokenError):
        # Token already invalid — nothing to revoke.
        return {"status": "ok"}

    jti = payload.get("jti")
    if jti:
        _token_blacklist.add(jti)
    return {"status": "ok"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}
