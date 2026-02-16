"""Authentication helpers and routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
import jwt as pyjwt
from jwt.exceptions import InvalidTokenError
import bcrypt
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import select

from .deps import _get_settings, _get_engine
from .db import get_session
from .models import User


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str, secret: str, expires_minutes: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire}
    return pyjwt.encode(payload, secret, algorithm="HS256")


@router.post("/register")
def register(request: Request, payload: RegisterRequest) -> dict:
    engine = _get_engine(request)
    with get_session(engine) as session:
        existing = session.exec(select(User).where(User.email == payload.email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(email=payload.email, hashed_password=hash_password(payload.password))
        session.add(user)
        session.commit()
        session.refresh(user)

    settings = _get_settings(request)
    token = create_access_token(user.id, settings["SECRET_KEY"], settings["ACCESS_TOKEN_EXPIRE_MINUTES"])
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(request: Request, payload: LoginRequest) -> dict:
    engine = _get_engine(request)
    with get_session(engine) as session:
        user = session.exec(select(User).where(User.email == payload.email)).first()
        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    settings = _get_settings(request)
    token = create_access_token(user.id, settings["SECRET_KEY"], settings["ACCESS_TOKEN_EXPIRE_MINUTES"])
    return {"access_token": token, "token_type": "bearer"}


def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> User:
    settings = _get_settings(request)
    try:
        payload = pyjwt.decode(token, settings["SECRET_KEY"], algorithms=["HS256"])
        user_id = payload.get("sub")
    except (InvalidTokenError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    engine = _get_engine(request)
    with get_session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}
