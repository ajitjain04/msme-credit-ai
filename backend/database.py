"""
Step 10 — Database setup (SQLAlchemy + SQLite).

Sets up the local SQLite database the backend API (Step 11) will read from
and write to: company profiles and their credit-assessment history.

The database file lives at data/processed/msme_credit.db. It is NOT
committed to git: `*.db` is already listed in .gitignore (from Step 1), so
running scripts/init_db.py never accidentally adds a database file to the
repo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "processed" / "msme_credit.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Make sure data/processed/ exists before SQLite tries to create the file
# there (it already does, from Step 5's train/test CSVs, but this keeps
# database.py safe to import on a fresh checkout too).
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# check_same_thread=False: SQLite normally refuses to let a connection be
# used from a thread other than the one that created it. FastAPI can serve
# a request's get_db() dependency on a different thread than the one that
# created the engine, so this is the standard setting for SQLite + FastAPI.
# It does NOT mean connections are shared across requests -- get_db() below
# still hands each request its own, separate Session.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base. backend/db_models.py's ORM models
    (Company, Assessment) inherit from this, so
    `Base.metadata.create_all(bind=engine)` (used by scripts/init_db.py)
    knows about every table in one place."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields one database session per request, and
    always closes it afterward -- even if the request raised an error.

    Step 11's API will use this as:
        @app.get("/api/v1/company/{company_id}")
        def get_company(company_id: str, db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
