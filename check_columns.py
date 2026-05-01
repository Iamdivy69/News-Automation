import os, psycopg2
from dotenv import load_dotenv
load_dotenv()

url = os.environ.get("DATABASE_URL", "NOT SET")
print("DATABASE_URL:", url[:80] + "..." if len(url) > 80 else url)

conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='articles' ORDER BY ordinal_position"
)
cols = [r[0] for r in cur.fetchall()]
print("\nAll columns in articles table:")
for c in cols:
    print(" ", c)

check = ["emotion", "priority_level", "is_breaking", "category_detected",
         "score_breakdown_json", "viral_score", "posted_platforms_json",
         "image_path", "duplicate_of_id", "retry_count"]
missing = [c for c in check if c not in cols]
print("\nMISSING columns:", missing if missing else "NONE — all present")
conn.close()
