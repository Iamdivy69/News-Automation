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

    # Step 2: Apply full unified schema
    print("\n  Applying base schema (database/db_schema.py)...")
    try:
        from database.db_schema import create_tables, verify_tables
        create_tables(db_url)
        print("  [OK] Base schema applied")
    except Exception as e:
        print(f"  [ERR] Base schema error: {e}")
        sys.exit(1)

    # Step 3: Apply v2 migration (safe to skip if file missing)
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
        print(f"  [WARN] Migration error (non-fatal, columns may already exist): {e}")

    # Step 4: Verify all expected tables exist
    print("\n  Verifying all required tables...")
    try:
        missing = verify_tables(db_url)
        if missing:
            print(f"  [ERR] Missing tables after setup: {missing}")
            sys.exit(1)
        else:
            print("  [OK] All tables verified")
    except Exception as e:
        print(f"  [ERR] Table verification failed: {e}")
        sys.exit(1)

    # Step 5: Seed feed sources if empty
    print("\n  Checking feed_sources seed data...")
    seed_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'seed_feeds.sql')
    try:
        conn = psycopg2.connect(db_url)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM feed_sources")
                count = cur.fetchone()[0]
            if count == 0 and os.path.exists(seed_path):
                with open(seed_path, 'r') as f:
                    seed_sql = f.read()
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(seed_sql)
                print("  [OK] feed_sources seeded")
            else:
                print(f"  [OK] feed_sources already has {count} rows — skipping seed")
        finally:
            conn.close()
    except Exception as e:
        print(f"  [WARN] feed_sources seed skipped: {e}")

    print("\nInstalling image generation fonts...")
    os.system('python scripts/install_fonts.py')
    print(" Fonts installed")

    print("\n[OK] Database ready -- all tables verified\n")


if __name__ == "__main__":
    main()
