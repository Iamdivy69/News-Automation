import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ.get("DATABASE_URL")

def fix_and_migrate():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            # 1. Update articles_status_check constraint
            print("Updating articles_status_check constraint...")
            cur.execute("ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_status_check")
            cur.execute("""
                ALTER TABLE articles 
                ADD CONSTRAINT articles_status_check 
                CHECK (status IN ('new', 'approved', 'summarised', 'merged', 'needs_review', 'publish_approved', 'published'))
            """)

            # 2. Recreate posts table to match user schema
            print("Recreating posts table...")
            cur.execute("DROP TABLE IF EXISTS posts CASCADE")
            cur.execute("""
                CREATE TABLE posts (
                    id               SERIAL PRIMARY KEY,
                    article_id       INT REFERENCES articles(id),
                    platform         TEXT NOT NULL,
                    post_id          TEXT,
                    posted_at        TIMESTAMPTZ DEFAULT NOW(),
                    status           TEXT DEFAULT 'published',
                    engagement_score FLOAT DEFAULT 0
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_posts_platform_date ON posts (platform, posted_at)")
            
            # 3. Alter pipeline_runs
            print("Altering pipeline_runs...")
            cur.execute("ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS published INT DEFAULT 0")

            # 4. Set test articles
            print("Setting test articles...")
            cur.execute("""
                UPDATE articles SET status = 'publish_approved'
                WHERE id IN (
                    SELECT a.id FROM articles a
                    JOIN summaries s ON a.id = s.article_id
                    JOIN images i ON a.id = i.article_id
                    WHERE a.status = 'summarised'
                    ORDER BY a.viral_score DESC
                    LIMIT 5
                )
            """)
            
        conn.close()
        print("Database fixes and migrations successful.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_and_migrate()
