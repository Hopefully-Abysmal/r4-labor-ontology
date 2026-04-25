from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .config import get_settings


def _db_url() -> str:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    # Note: check_same_thread=False is needed for sqlite + FastAPI threaded usage.
    return f"sqlite:///{settings.sqlite_path.as_posix()}?check_same_thread=False"


engine = create_engine(_db_url(), future=True)


@contextmanager
def session_scope():
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

