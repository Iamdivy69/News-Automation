import os
import sys
import json
import requests
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

CREATE_ANALYTICS_TABLE = """
CREATE TABLE IF NOT EXISTS post_analytics (
    id           SERIAL PRIMARY KEY,
    post_id      TEXT NOT NULL,
    platform     TEXT NOT NULL,
    article_id   INT REFERENCES articles(id),
    views        INT DEFAULT 0,
    forwards     INT DEFAULT 0,
    collected_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_analytics_article
ON post_analytics (article_id);
"""

class FeedbackLoopEngine:
    AGENT_NAME = "feedback_loop"

    def __init__(self):
        load_dotenv()
        self.conn_string = os.environ.get("DATABASE_URL")
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.bot_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        if not self.conn_string:
            print("[WARN] DATABASE_URL not set.")

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def collect_telegram_analytics(self, days_back=7):
        """
        Telegram Bot API does not expose view counts for channel messages to bots.
        Instead, we track delivery by inserting a placeholder analytics row.
        """
        count = 0
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(CREATE_ANALYTICS_TABLE)
                
                cur.execute(f"""
                    SELECT post_id, platform, article_id FROM posts 
                    WHERE platform='telegram' AND status='published' 
                    AND posted_at >= NOW() - INTERVAL '{days_back} days'
                    AND NOT EXISTS (
                        SELECT 1 FROM post_analytics pa WHERE pa.post_id = posts.post_id
                    )
                """)
                rows = cur.fetchall()
                
                for row in rows:
                    post_id, platform, article_id = row
                    cur.execute(
                        """
                        INSERT INTO post_analytics (post_id, platform, article_id, views, forwards, collected_at) 
                        VALUES (%s, %s, %s, 0, 0, NOW())
                        """,
                        (post_id, platform, article_id)
                    )
                    count += 1
            conn.commit()
        except Exception as e:
            print(f"Error collecting analytics: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        return count

    def calculate_performance_scores(self):
        count = 0
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT 
                        a.id, 
                        a.viral_score, 
                        MIN(EXTRACT(EPOCH FROM (NOW() - p.posted_at))/3600.0) as hours_since_posted
                    FROM articles a
                    JOIN posts p ON a.id = p.article_id
                    WHERE p.status = 'published'
                    GROUP BY a.id, a.viral_score
                """)
                rows = cur.fetchall()
                
                for row in rows:
                    article_id = row['id']
                    base_score = float(row['viral_score'] or 0)
                    hours_since_posted = float(row['hours_since_posted'] or 0)
                    
                    recency_bonus = max(0.0, 10.0 - hours_since_posted)
                    final_score = base_score + recency_bonus
                    
                    if final_score > base_score:
                        cur.execute("UPDATE articles SET viral_score = %s WHERE id = %s", (final_score, article_id))
                        count += 1
            conn.commit()
        except Exception as e:
            print(f"Error calculating scores: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
        return count

    def analyse_top_performers(self):
        results = []
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT a.category, a.source, AVG(a.viral_score) as avg_score, COUNT(*) as post_count
                    FROM articles a 
                    JOIN posts p ON a.id = p.article_id
                    WHERE p.status = 'published'
                    GROUP BY a.category, a.source
                    ORDER BY avg_score DESC LIMIT 10
                """)
                rows = cur.fetchall()
                for r in rows:
                    results.append({
                        "category": r['category'],
                        "source": r['source'],
                        "avg_score": round(float(r['avg_score'] or 0), 2),
                        "post_count": r['post_count']
                    })
        except Exception as e:
            print(f"Error analysing top performers: {e}")
        finally:
            if conn:
                conn.close()
        return results

    def generate_insight_report(self, top_performers):
        try:
            prompt = f"Top performing categories and sources this week:\n{json.dumps(top_performers, indent=2)}\nWhat should we prioritise publishing more of?"
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "mistral",
                    "stream": False,
                    "system": "You are a news analytics expert. Write a concise 3-sentence performance report.",
                    "prompt": prompt
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except Exception as e:
            print(f"Error generating insight report: {e}")
            return f"Unable to generate insight report at this time. Error: {e}"

    def run(self):
        collected = self.collect_telegram_analytics()
        updated = self.calculate_performance_scores()
        top_performers = self.analyse_top_performers()
        
        insight_report = "Skip insight report generation because no top performers found."
        if top_performers:
            insight_report = self.generate_insight_report(top_performers)
        
        conn = None
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO system_config (key, value, updated_at) 
                    VALUES ('latest_insight_report', %s, NOW())
                    ON CONFLICT (key) DO UPDATE SET 
                        value = EXCLUDED.value,
                        updated_at = NOW()
                """, (insight_report,))
            conn.commit()
        except Exception as e:
            print(f"Error saving insight report: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
                
        return {
            "collected": collected,
            "updated": updated,
            "insight_report": insight_report
        }

if __name__ == "__main__":
    engine = FeedbackLoopEngine()
    print("FeedbackLoopEngine started...")
    results = engine.run()
    if isinstance(results, dict):
        print(f"Collected: {results.get('collected')}")
        print(f"Updated: {results.get('updated')}")
        print(f"Insight Report:\n{results.get('insight_report')}")
