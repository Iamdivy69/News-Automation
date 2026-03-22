import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ.get("DATABASE_URL")

def migrate():
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            print("Checking summaries table...")
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='summaries' AND column_name='is_branded'")
            if not cur.fetchone():
                print("Adding is_branded column to summaries table...")
                cur.execute("ALTER TABLE summaries ADD COLUMN is_branded BOOLEAN DEFAULT TRUE")
            else:
                print("Column is_branded already exists in summaries.")
            
            print("Checking posts table...")
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name='posts'")
            if not cur.fetchone():
                print("Creating posts table...")
                cur.execute("""
                    CREATE TABLE posts (
                        id SERIAL PRIMARY KEY,
                        article_id INT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                        platform TEXT NOT NULL,
                        post_id TEXT,
                        status TEXT DEFAULT 'pending',
                        published_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
            else:
                print("Table posts already exists.")
            
            # Additional cleanup: ensure articles are marked as summarized if they have a summary
            cur.execute("UPDATE articles SET status = 'summarised' WHERE id IN (SELECT article_id FROM summaries)")
            
        print("Migration complete.")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    migrate()
