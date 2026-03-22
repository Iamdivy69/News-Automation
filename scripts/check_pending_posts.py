import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

def check_db():
    with engine.connect() as conn:
        print("--- PUBLISH_APPROVED ARTICLES ---")
        result = conn.execute(text("SELECT id, headline, status FROM articles WHERE status = 'publish_approved'"))
        rows = list(result)
        if not rows:
            print("No articles are currently 'publish_approved'.")
        for row in rows:
            print(f"ID: {row[0]} | Headline: {row[1][:40]}...")
            
        print("\n--- RECENT POSTS (Last 24h) ---")
        result = conn.execute(text("SELECT article_id, platform, status, posted_at FROM posts WHERE posted_at > NOW() - INTERVAL '24 hours'"))
        rows = list(result)
        if not rows:
            print("No new posts in the last 24 hours.")
        for row in rows:
            print(f"Article ID: {row[0]} | Platform: {row[1]} | Status: {row[2]} | Posted: {row[3]}")

if __name__ == "__main__":
    check_db()
