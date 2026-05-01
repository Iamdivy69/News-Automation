"""
scripts/setup_local.py
Bootstrap the local database for development.
Usage: python scripts/setup_local.py
"""
import os
import sys

# Must load .env before importing anything that reads env vars
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

import psycopg2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("[ERR] DATABASE_URL not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    print(f"  Connecting to: {db_url.split('@')[-1]}")  # hide credentials

    # Step 1: Test connection
    try:
        conn = psycopg2.connect(db_url)
        conn.close()
        print("  [OK] Connection OK")
    except Exception as e:
        print(f"  [ERR] Cannot connect to database: {e}")
        print("  Is Docker running?  ->  docker compose up -d")
        sys.exit(1)

    # Step 2: Apply base schema
    print("\n  Applying base schema (database/db_schema.py)...")
    try:
        from database.db_schema import create_tables
        create_tables(db_url)
        print("  [OK] Base schema applied")
    except Exception as e:
        print(f"  [ERR] Base schema error: {e}")
        sys.exit(1)

    # Step 3: Apply v2 migration
    migration_path = os.path.join(
        os.path.dirname(__file__), '..', 'database', 'migrations', 'v2_upgrade.sql'
    )
    print(f"\n  Applying migration ({os.path.basename(migration_path)})...")
    try:
        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        conn = psycopg2.connect(db_url)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(migration_sql)
        finally:
            conn.close()
        print("  [OK] v2 migration applied")
    except FileNotFoundError:
        print(f"  [WARN] Migration file not found: {migration_path} -- skipping")
    except Exception as e:
        print(f"  [ERR] Migration error: {e}")
        sys.exit(1)

    print("\n[OK] Database ready. You can now run:\n  python -m pytest tests/ -v\n")


if __name__ == "__main__":
    main()
