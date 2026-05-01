"""
tests/conftest.py
Global pytest configuration: loads .env automatically and provides shared fixtures.
"""
import os
import sys
import pytest
import psycopg2

# ── Ensure project root is on sys.path ────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Load .env before any test module is collected ────────────────────────────
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(ROOT, ".env"), override=False)


# ── Shared DB fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_conn():
    """
    Session-scoped PostgreSQL connection.
    Skips (does not fail) the entire session if DATABASE_URL is unset or unreachable.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set — run: cp .env.example .env")

    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.OperationalError as e:
        pytest.skip(
            f"Cannot connect to database ({e}). "
            "Make sure Docker is running: docker compose up -d"
        )

    yield conn
    conn.close()


@pytest.fixture(scope="function")
def db_conn_fn(db_conn):
    """
    Function-scoped wrapper: borrows the session connection and rolls back
    after each test so tests don't bleed state into one another.
    """
    yield db_conn
    try:
        db_conn.rollback()
    except Exception:
        pass
