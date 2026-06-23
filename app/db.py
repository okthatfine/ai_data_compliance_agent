from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DEFAULT_SQLITE_URL = f"sqlite:///{ROOT / 'data' / 'app.db'}"


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def database_url() -> str:
    return _normalize_database_url(os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL).strip() or DEFAULT_SQLITE_URL)


def make_engine() -> Engine:
    url = database_url()
    kwargs = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from .models import Base

    Base.metadata.create_all(bind=engine)


def db_status() -> dict:
    url = database_url()
    dialect = engine.url.get_backend_name()
    safe_url = str(engine.url).replace(engine.url.password or "", "***") if engine.url.password else str(engine.url)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        ok = True
        error = ""
    except Exception as exc:
        ok = False
        error = str(exc)
    return {"ok": ok, "dialect": dialect, "url": safe_url, "error": error}
