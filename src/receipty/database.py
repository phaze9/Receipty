from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_database(path: Path):
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    from . import models  # noqa: F401

    Base.metadata.create_all(engine)
    _migrate(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    return engine, factory


def _migrate(engine) -> None:
    """Lightweight column migrations for databases created before a column existed."""
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(receipts)")}
        if "deleted_at" not in columns:
            conn.exec_driver_sql("ALTER TABLE receipts ADD COLUMN deleted_at DATETIME")


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

