"""
run_migration.py — Applies final_schema_sync.sql to the configured DATABASE_URL.
Runs each statement individually with its own commit so one failure never blocks the rest.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("ERROR: DATABASE_URL not set in .env")

SQL_FILE = os.path.join(os.path.dirname(__file__), "final_schema_sync.sql")

with open(SQL_FILE, "r") as f:
    raw = f.read()

# Split on semicolons, skip blank / comment-only lines
statements = []
for stmt in raw.split(";"):
    cleaned = "\n".join(
        line for line in stmt.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ).strip()
    if cleaned:
        statements.append(cleaned)

print(f"Connecting to database...")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False

ok = 0
failed = 0
for i, stmt in enumerate(statements, 1):
    preview = stmt.replace("\n", " ")[:80]
    try:
        with conn.cursor() as cur:
            cur.execute(stmt)
        conn.commit()
        print(f"  [{i:02d}] OK  : {preview}")
        ok += 1
    except Exception as e:
        conn.rollback()
        print(f"  [{i:02d}] FAIL: {preview}")
        print(f"        => {e}")
        failed += 1

conn.close()
print(f"\nMigration complete: {ok} OK, {failed} failed.")
