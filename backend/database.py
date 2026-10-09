"""
Step 10 / Step 10b — Database setup: PostgreSQL (per the literature
review's Sect 6.1/Table 10 recommended architecture), with an automatic
SQLite fallback for anyone who hasn't set up their .env yet.

HOW THE DATABASE IS CHOSEN
----------------------------------------------------------------------------
1. `load_dotenv()` reads a `.env` file at the project root (if one exists)
   into the process's environment. Copy `.env.example` to `.env` and set
   your own PostgreSQL password there -- `.env` is git-ignored, so your
   password never gets committed; `.env.example` IS committed, so anyone
   else cloning the repo knows which variable to set.
2. If `DATABASE_URL` ends up set (from `.env` or any other way the
   environment got it), that's the database used -- expected to be a
   PostgreSQL URL, e.g.
   `postgresql://postgres:<password>@localhost:5432/msme_credit`.
3. If `DATABASE_URL` is NOT set at all (no `.env`, or `.env` exists but
   doesn't define it), this module does NOT crash -- it prints a clear
   warning and falls back to the original Step 10 SQLite file at
   `data/processed/msme_credit.db`, so the app still runs for a teammate
   who hasn't configured Postgres yet.
Either way, EXACTLY which database is in use gets printed at import time,
with the password masked (never printed in full, even to your own
terminal).

WHAT CHANGES vs. WHAT STAYS THE SAME
----------------------------------------------------------------------------
Only this file changes. `Base`, `get_db()`, every ORM model in
backend/db_models.py, every function in backend/crud.py, and every
endpoint in backend/main.py work completely unmodified against either
database -- that's the entire point of using SQLAlchemy as an ORM: it
translates the same Python model definitions and queries into the right
SQL dialect for whichever engine is plugged in underneath. See this
project's Step 10b progress-log entry for the longer explanation.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Reads .env (if it exists) into os.environ. Silently does nothing if the
# file is missing -- that's what makes the SQLite fallback below possible
# for a teammate who hasn't created their .env yet.
load_dotenv(PROJECT_ROOT / ".env")

# The original Step 10 SQLite file -- used ONLY as a fallback when
# DATABASE_URL isn't set at all.
_SQLITE_FALLBACK_PATH = PROJECT_ROOT / "data" / "processed" / "msme_credit.db"
_SQLITE_FALLBACK_URL = f"sqlite:///{_SQLITE_FALLBACK_PATH}"

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # PostgreSQL (via psycopg2) doesn't use/want SQLite's
    # check_same_thread option.
    _connect_args: dict = {}
else:
    print(
        "[database] WARNING: DATABASE_URL is not set (no .env file, or it "
        "doesn't define DATABASE_URL). Falling back to the original "
        f"SQLite database at {_SQLITE_FALLBACK_PATH}. To use PostgreSQL "
        "instead, copy .env.example to .env and set your own password."
    )
    DATABASE_URL = _SQLITE_FALLBACK_URL
    # Make sure data/processed/ exists before SQLite tries to create the
    # file there (it already does, from Step 5's train/test CSVs, but this
    # keeps the fallback safe on a fresh checkout too).
    _SQLITE_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: SQLite normally refuses to let a connection
    # be used from a thread other than the one that created it. FastAPI
    # can serve a request's get_db() dependency on a different thread
    # than the one that created the engine, so this is the standard
    # setting for SQLite + FastAPI. It does NOT mean connections are
    # shared across requests -- get_db() below still hands each request
    # its own, separate Session.
    _connect_args = {"check_same_thread": False}


def _mask_password(url: str) -> str:
    """Hides a URL's password before printing it, e.g.
    postgresql://postgres:secret@localhost/db ->
    postgresql://postgres:***@localhost/db. Leaves URLs with no password
    (like the SQLite fallback) unchanged."""
    return re.sub(r"(://[^:/@]+:)[^@]+(@)", r"\1***\2", url)


print(f"[database] Using: {_mask_password(DATABASE_URL)}")

engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base. backend/db_models.py's ORM models
    (Company, Assessment, FairnessAuditLog) inherit from this, so
    `Base.metadata.create_all(bind=engine)` (used by scripts/init_db.py
    and backend/main.py's startup hook) knows about every table in one
    place -- and creates them correctly on whichever database `engine`
    above points at, Postgres or SQLite."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields one database session per request, and
    always closes it afterward -- even if the request raised an error.

    Step 11's API uses this as:
        @app.get("/api/v1/company/{company_id}")
        def get_company(company_id: str, db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
