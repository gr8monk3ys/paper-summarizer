"""Database setup and session helpers."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine


def create_db_engine(database_url: str):
    if database_url.startswith("sqlite"):
        # SQLite: keep single-threaded safety; limit pool to 1 since SQLite
        # does not handle concurrent writes well.
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            pool_size=1,
        )

    # PostgreSQL / other databases: configure connection pool for concurrency.
    # pool_size       – number of persistent connections to keep open
    # max_overflow    – extra connections allowed beyond pool_size under load
    # pool_timeout    – seconds to wait for a connection before raising an error
    # pool_recycle    – recycle connections after 30 minutes to avoid stale handles
    # pool_pre_ping   – verify each connection is alive before handing it out
    return create_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )


def init_db(engine, reset: bool = False, auto_create: bool = True) -> None:
    if reset:
        SQLModel.metadata.drop_all(engine)
    if auto_create:
        SQLModel.metadata.create_all(engine)


@contextmanager
def get_session(engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session
