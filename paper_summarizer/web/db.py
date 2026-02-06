"""Database setup and session helpers."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine


def create_db_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_db(engine, reset: bool = False, auto_create: bool = True) -> None:
    if reset:
        SQLModel.metadata.drop_all(engine)
    if auto_create:
        SQLModel.metadata.create_all(engine)


@contextmanager
def get_session(engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session
