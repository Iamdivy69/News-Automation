import os, psycopg2
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

# Drop the old restrictive CHECK constraint
cur.execute("ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_status_check")
print("Dropped old articles_status_check constraint")

# Add a new one covering all statuses used by every agent in the pipeline
cur.execute("""
    ALTER TABLE articles ADD CONSTRAINT articles_status_check CHECK (status = ANY (ARRAY[
        'new',
        'approved',
        'ranked',
        'low_priority',
        'ignored',
        'approved_unique',
        'duplicate',
        'image_ready',
        'image_failed',
        'queued',
        'scheduled',
        'published',
        'publish_failed',
        'merged',
        'summarised',
        'pending',
        'rejected',
        'discarded',
        'archived'
    ]::text[]))
""")
print("Created new articles_status_check constraint with all pipeline statuses")

# Verify
cur.execute("""
    SELECT pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'articles'::regclass AND conname = 'articles_status_check'
""")
print("New constraint:", cur.fetchone()[0])
conn.close()
