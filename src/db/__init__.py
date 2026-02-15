"""Database package: engine, session factory, init_db(), get_session()."""

import threading
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from src.config import DATABASE_URL
from src.db.base import Base

# Import all models so Base.metadata has all tables
from src.db.models import (  # noqa: F401
    AllocationRecord,
    AllocationRule,
    Contact,
    Customer,
    DataDictionary,
    Distributor,
    EmailOutcome,
    InventorySnapshot,
    Location,
    Product,
    SpecBuyReport,
)

_init_lock = threading.Lock()
_engine = None
_SessionLocal: sessionmaker | None = None


def _get_engine():
    """Create engine with check_same_thread=False for use from executor threads."""
    url = DATABASE_URL
    if url.startswith("sqlite"):
        if "?" in url:
            url += "&check_same_thread=False"
        else:
            url += "?check_same_thread=False"
    return create_engine(url, echo=False)


def init_db() -> None:
    """Create engine and tables; if tables do not exist, seed from CSV. If tables exist, do nothing."""
    global _engine, _SessionLocal
    with _init_lock:
        if _SessionLocal is not None:
            return
        _engine = _get_engine()
        Base.metadata.create_all(bind=_engine)
        insp = inspect(_engine)
        if not insp.has_table("locations"):
            from src.db.seed_data import seed_mock_data
            with _engine.connect() as conn:
                session = Session(bind=conn)
                try:
                    seed_mock_data(session)
                    conn.commit()
                finally:
                    session.close()
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager yielding a DB session. Calls init_db() on first use."""
    init_db()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
