import os
import sys
import time
import requests
import psycopg2
import traceback
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

CREATE_POSTS_TABLE = """
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    article_id INT REFERENCES articles(id),
    platform TEXT NOT NULL,
    post_id TEXT,
    posted_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'published',
    engagement_score FLOAT DEFAULT 0
);
"""

class PublishingAgent:
    
    AGENT_NAME = "publishing"

    def __init__(self):
        load_dotenv()
        self.conn_string = os.environ.get("DATABASE_URL")
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.channel_id = os.environ.get("TELEGRAM_CHANNEL_ID")
        
        if not self.conn_string:
            print("[WARN] DATABASE_URL not set.")
        if not self.bot_token or not self.channel_id:
            print("[WARN] Telegram credentials missing.")

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def _log_post(self, article_id, platform, post_id, status, db_conn):
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO posts (article_id, platform, post_id, status)
                    VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
                    """,
                    (article_id, platform, post_id, status)
                )
            db_conn.commit()
        except Exception as e:
            db_conn.rollback()
            print(f"Error logging post: {e}")

    def _log_error(self, agent, message, tb, db_conn):
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO error_logs (agent, message, stack_trace)
                    VALUES (%s, %s, %s)
                    """,
                    (agent, str(message)[:1000], tb)
                )
            db_conn.commit()
        except Exception as e:
            db_conn.rollback()
            print(f"Error logging error: {e}")

    def post_to_telegram(self, article_id, caption_text, image_path, db_conn):
        try:
            if not self.bot_token or not self.channel_id:
                raise ValueError("Telegram credentials missing.")
                
            # a) Build caption
            caption_text = caption_text or ""
            caption = caption_text[:950]
            caption += f"\n\n{self.channel_id}"
            
            # b) base_url
            base_url = f"https://api.telegram.org/bot{self.bot_token}"
            
            # c & d) If image exists, sendPhoto, else sendMessage
            if image_path and os.path.exists(image_path):
                url = f"{base_url}/sendPhoto"
                data = {"chat_id": self.channel_id, "caption": caption, "parse_mode": "HTML"}
                with open(image_path, "rb") as f:
                    files = {"photo": ("card.png", f, "image/png")}
                    # e) Timeout 30
                    resp = requests.post(url, data=data, files=files, timeout=30)
            else:
                url = f"{base_url}/sendMessage"
                json_data = {"chat_id": self.channel_id, "text": caption, "parse_mode": "HTML"}
                resp = requests.post(url, json=json_data, timeout=30)
                
            result = resp.json()
            
            # f) If ok
            if result.get("ok"):
                msg_id = result["result"]["message_id"]
                self._log_post(article_id, "telegram", str(msg_id), "published", db_conn)
                return True
            # g) If not ok
            else:
                error_code = result.get("error_code")
                description = result.get("description", "Unknown error")
                print(f"Telegram API Error {error_code}: {description}")
                self._log_error(self.AGENT_NAME, description, "", db_conn)
                return False
                
        # h) Wrap everything in try/except
        except Exception as e:
            print(f"Error in post_to_telegram: {e}")
            tb = traceback.format_exc()
            self._log_error(self.AGENT_NAME, str(e), tb, db_conn)
            return False

    def rate_limit_check(self, platform, conn):
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM posts WHERE platform=%s AND posted_at >= CURRENT_DATE",
                    (platform,)
                )
                count = cur.fetchone()[0]
                if platform == "telegram" and count >= 20:
                    return False
                return True
        except Exception as e:
            print(f"Rate limit check error: {e}")
            return False

    def auto_discard(self, db_conn) -> int:
        """
        Early-discard articles that will never be worth publishing:
        status='new', viral_score < 65, and older than 6 hours.
        Called as the very first step in MasterPipeline.run() to keep
        the queue clean before IntelligencePipeline processes articles.
        Returns number of rows updated.
        """
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE articles
                    SET status = 'discarded'
                    WHERE status = 'new'
                      AND viral_score < 65
                      AND created_at < NOW() - INTERVAL '6 hours'
                    """
                )
                updated = cur.rowcount
            db_conn.commit()
            print(f"  auto_discard: {updated} article(s) discarded")
            return updated
        except Exception as exc:
            db_conn.rollback()
            print(f"auto_discard error: {exc}")
            return 0

    def publish_article(self, article_id):
        # a) Open one DB connection for the whole method
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # b) Fetch from articles
                cur.execute(
                    "SELECT headline, source, url, category, is_breaking, status FROM articles WHERE id = %s",
                    (article_id,)
                )
                article_row = cur.fetchone()
                
                if not article_row:
                    return {"skipped": True}
                    
                # c) If status != publish_approved
                if article_row["status"] != 'publish_approved':
                    return {"skipped": True}
                
                # d) Fetch from summaries
                cur.execute("SELECT twitter_text, hashtags FROM summaries WHERE article_id = %s", (article_id,))
                summary_row = cur.fetchone()
                twitter_text = summary_row["twitter_text"] if summary_row else None
                hashtags = summary_row["hashtags"] if summary_row else None
                
                # e) Fetch from images (most recent)
                cur.execute(
                    "SELECT image_path FROM images WHERE article_id = %s ORDER BY created_at DESC LIMIT 1", 
                    (article_id,)
                )
                image_row = cur.fetchone()
                image_path = image_row["image_path"] if image_row else None
                
            # f) Build post_text
            post_text = twitter_text or article_row["headline"]
            if article_row.get("url"):
                post_text += f"\n\n🔗 {article_row['url']}"
            if hashtags:
                post_text += f"\n\n{hashtags}"
                
            # g) Check rate limit
            if not self.rate_limit_check("telegram", conn):
                print("Telegram rate limit reached (>= 20 posts today).")
                return {"telegram": False}
                
            # h) Call post_to_telegram
            telegram_ok = self.post_to_telegram(article_id, post_text, image_path, conn)
            
            # i) If succeeded, update status
            if telegram_ok:
                with conn.cursor() as cur:
                    cur.execute("UPDATE articles SET status='published' WHERE id=%s", (article_id,))
                conn.commit()
                
            # j) Return dict
            return {"telegram": telegram_ok, "article_id": article_id}
                
        except Exception as e:
            print(f"Error in publish_article for ID {article_id}: {e}")
            if conn:
                self._log_error(self.AGENT_NAME, str(e), traceback.format_exc(), conn)
            return {"telegram": False, "article_id": article_id}
        finally:
            if conn:
                conn.close()

    def run(self, limit=10):
        conn = None
        attempted = 0
        telegram_ok = 0
        failed = 0
        try:
            # a) Fetch up to limit
            conn = self._get_conn()
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    "SELECT id FROM articles WHERE status='publish_approved' ORDER BY viral_score DESC LIMIT %s",
                    (limit,)
                )
                rows = cur.fetchall()
                article_ids = [r["id"] for r in rows]
        except Exception as e:
            print(f"Error fetching articles queue: {e}")
            return {"attempted": 0, "telegram_ok": 0, "failed": 0}
        finally:
            if conn:
                conn.close()
                
        # b) Call publish_article for each
        for aid in article_ids:
            attempted += 1
            result = self.publish_article(aid)
            
            if result.get("telegram"):
                telegram_ok += 1
            else:
                if not result.get("skipped"):
                    failed += 1
                    
            # 3 second sleep (Telegram best practice)
            time.sleep(3)
            
        # c) Return metrics
        return {"attempted": attempted, "telegram_ok": telegram_ok, "failed": failed}

if __name__ == "__main__":
    agent = PublishingAgent()
    print("PublishingAgent startup...")
    results = agent.run()
    print(f"Publishing result: {results}")
