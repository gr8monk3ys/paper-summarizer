"""Authentication helpers and routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext
from sqlmodel import select

from .config import load_settings
from .db import create_db_engine, get_session, init_db
from .models import User


router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _get_settings(request: Request):
    if not hasattr(request.app.state, "settings"):
        settings = load_settings()
        engine = create_db_engine(settings["DATABASE_URL"])
        init_db(engine, reset=bool(settings.get("TESTING")))
        request.app.state.settings = settings
        request.app.state.engine = engine
    return request.app.state.settings


def _get_engine(request: Request):
    _get_settings(request)
    return request.app.state.engine


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def create_access_token(subject: str, secret: str, expires_minutes: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, secret, algorithm="HS256")


@router.post("/register")
def register(request: Request, payload: dict):
    email = payload.get("email")
    password = payload.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    engine = _get_engine(request)
    with get_session(engine) as session:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(email=email, hashed_password=hash_password(password))
        session.add(user)
        session.commit()
        session.refresh(user)

    settings = _get_settings(request)
    token = create_access_token(user.id, settings["SECRET_KEY"], settings["ACCESS_TOKEN_EXPIRE_MINUTES"])
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(request: Request, payload: dict):
    email = payload.get("email")
    password = payload.get("password")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    engine = _get_engine(request)
    with get_session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    settings = _get_settings(request)
    token = create_access_token(user.id, settings["SECRET_KEY"], settings["ACCESS_TOKEN_EXPIRE_MINUTES"])
    return {"access_token": token, "token_type": "bearer"}


def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> User:
    settings = _get_settings(request)
    try:
        payload = jwt.decode(token, settings["SECRET_KEY"], algorithms=["HS256"])
        user_id = payload.get("sub")
    except Exception as exc:
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
