"""
Schema tests — three layers:
  1. SQLAlchemy models are importable and declare the right tables/columns.
  2. Alembic migration SQL contains every required table.
  3. Supabase has the tables after migration (verified via REST API).
"""

import os
from pathlib import Path

import pytest

from app.models.enums import ENUM_NAMES

# ---------------------------------------------------------------------------
# Layer 1: SQLAlchemy model structure (no DB required)
# ---------------------------------------------------------------------------

REQUIRED_TABLES = {
    "representatives",
    "bills",
    "votes",
    "vote_outcomes",
    "users",
    "user_representatives",
    "pledges",
    "disbursements",
}

REQUIRED_ENUMS = {
    "chamber",
    "vote_outcome",
    "pledge_direction",
    "pledge_status",
    "disbursement_status",
}


def test_all_models_importable():
    from app.models import Base  # noqa: F401


def test_all_tables_declared():
    from app.models import Base

    declared = set(Base.metadata.tables.keys())
    missing = REQUIRED_TABLES - declared
    assert not missing, f"Models missing tables: {missing}"


def test_enum_types_declared():
    import app.models  # noqa: F401

    missing = REQUIRED_ENUMS - ENUM_NAMES
    assert not missing, f"Missing enum definitions: {missing}"


# ---------------------------------------------------------------------------
# Layer 2: Migration SQL contains all required tables
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).parents[1] / "alembic" / "versions"


def test_migration_file_exists():
    sql_files = list(MIGRATIONS_DIR.glob("*.py"))
    assert sql_files, "No Alembic migration files found in alembic/versions/"


def test_migration_references_all_tables():
    migration_files = list(MIGRATIONS_DIR.glob("*.py"))
    combined = "\n".join(f.read_text() for f in migration_files)
    missing = [t for t in REQUIRED_TABLES if t not in combined]
    assert not missing, f"Tables not referenced in any migration: {missing}"


# ---------------------------------------------------------------------------
# Layer 3: Supabase schema live (via REST API — requires SUPABASE_* env vars)
# ---------------------------------------------------------------------------

pytestmark_live = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    reason="SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set",
)


@pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    reason="Supabase env vars not set",
)
def test_supabase_tables_exist():
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parents[2] / ".env")

    from supabase import create_client

    client = create_client(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )

    missing = []
    for table in REQUIRED_TABLES:
        try:
            client.table(table).select("*").limit(1).execute()
        except Exception as e:
            if "does not exist" in str(e) or "PGRST" in str(e):
                missing.append(table)

    assert not missing, f"Tables missing from Supabase: {missing}"
