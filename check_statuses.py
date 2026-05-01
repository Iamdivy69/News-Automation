import os, psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

# See all distinct statuses currently in the table
cur.execute("SELECT DISTINCT status, COUNT(*) FROM articles GROUP BY status ORDER BY count DESC")
rows = cur.fetchall()
print("Current statuses in articles table:")
for status, count in rows:
    print(f"  '{status}': {count} rows")

conn.close()
