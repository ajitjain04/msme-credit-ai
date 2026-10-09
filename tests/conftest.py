"""
Step 13 — Shared pytest fixtures.

Currently holds exactly one fixture: `client`, a FastAPI TestClient wired
to a brand-new, empty, IN-MEMORY SQLite database. tests/test_api.py uses
it for every endpoint test -- see the fixture's own docstring for why this
is safe to run repeatedly with zero side effects on the real PostgreSQL
database configured in .env.

pytest automatically discovers conftest.py and makes every fixture in it
available to every test file in this folder (and subfolders), with no
import needed in test_api.py itself -- that's the one bit of "magic"
pytest does with files specifically named conftest.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app


@pytest.fixture()
def client():
    """A FastAPI TestClient wired to a throwaway, in-memory SQLite
    database -- created fresh for every single test function that uses
    this fixture, and discarded the moment that test ends.

    This is what makes the whole suite safe to run over and over: there
    is no file on disk, and no connection to the real PostgreSQL database
    `backend/database.py` would otherwise use -- nothing a test does here
    can ever touch real data.

    poolclass=StaticPool + check_same_thread=False: SQLite's `:memory:`
    database normally lives inside exactly ONE connection and disappears
    the instant that connection closes. FastAPI's get_db() dependency
    opens a fresh connection per request, so without StaticPool the
    in-memory database created by one request (e.g. POST /evaluate)
    would already be gone by the time the next request (e.g. the
    following GET /company/{id}) ran. StaticPool keeps one single
    underlying connection alive for the whole engine instead, so every
    request inside one test sees the same in-memory data.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Swaps out the REAL get_db() dependency for this test only --
    # backend/main.py's endpoints don't need to know or care.
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
