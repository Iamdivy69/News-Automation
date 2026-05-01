import os, psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

# 1. Show existing check constraints on articles
cur.execute("""
    SELECT conname, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'articles'::regclass AND contype = 'c'
""")
rows = cur.fetchall()
print("Existing CHECK constraints on articles:")
for name, defn in rows:
    print(f"  {name}: {defn}")

conn.close()
