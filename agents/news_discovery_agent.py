import os
import time
import calendar
import traceback
import feedparser
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from newspaper import Article


class NewsDiscoveryAgent:
    """Autonomous agent that discovers and stores new articles from RSS feeds."""

    AGENT_NAME = "discovery"

    def __init__(self):
        self.conn_string = os.environ["DATABASE_URL"]

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    # ------------------------------------------------------------------
    # DB reads
    # ------------------------------------------------------------------

    def _get_active_feeds(self, cur):
        cur.execute(
            "SELECT id, name, url, category, language FROM feed_sources WHERE active = TRUE"
        )
        return cur.fetchall()

    def _url_exists(self, cur, url: str) -> bool:
        cur.execute("SELECT 1 FROM articles WHERE url = %s LIMIT 1", (url,))
        return cur.fetchone() is not None

    # ------------------------------------------------------------------
    # DB writes
    # ------------------------------------------------------------------

    def _save_article(self, cur, url, headline, full_text, source, published_date, category):
        cur.execute(
            """
            INSERT INTO articles (url, headline, full_text, source, published_date, category, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'new')
            ON CONFLICT (url) DO NOTHING
            """,
            (url, headline, full_text, source, published_date, category),
        )
        return cur.rowcount  # 1 if inserted, 0 if skipped due to conflict

    def _update_last_checked(self, cur, feed_id: int):
        cur.execute(
            "UPDATE feed_sources SET last_checked = %s WHERE id = %s",
            (datetime.now(timezone.utc), feed_id),
        )

    def _log_error(self, agent: str, message: str, tb: str):
        try:
            conn = self._get_conn()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO error_logs (agent, message, stack_trace) VALUES (%s, %s, %s)",
                        (agent, message, tb),
                    )
            conn.close()
        except Exception:
            pass  # Don't let error logging crash the agent

    # ------------------------------------------------------------------
    # Article scraping
    # ------------------------------------------------------------------

    def _scrape_article(self, url: str) -> tuple[str | None, str | None]:
        """Returns (headline, full_text) or (None, None) on failure."""
        try:
            article = Article(url, request_timeout=10)
            article.download()
            article.parse()
            return article.title or None, article.text or None
        except Exception as exc:
            self._log_error(
                self.AGENT_NAME,
                f"Scrape failed for {url}: {exc}",
                traceback.format_exc(),
            )
            return None, None

    # ------------------------------------------------------------------
    # Feed processing
    # ------------------------------------------------------------------

    def is_recent(self, published_parsed, hours=12) -> bool:
        """
        Returns True if the date is within the last `hours` hours,
        returns True if published_parsed is None (fails open),
        returns False if older than `hours` hours.
        """
        if published_parsed is None:
            return True
            
        try:
            published_ts = calendar.timegm(published_parsed)
            current_ts = calendar.timegm(time.gmtime())
            return (current_ts - published_ts) <= (hours * 3600)
        except Exception:
            return True  # Fail open on parse error

    def _parse_published(self, entry) -> datetime | None:
        """Convert feedparser's time_struct to an aware datetime, best-effort."""
        t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if t is None:
            return None
        try:
            import calendar
            ts = calendar.timegm(t)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None

    def _process_feed(self, cur, feed_id: int, feed_name: str, feed_url: str, category: str) -> int:
        """Fetch one RSS feed and persist new articles. Returns count of new rows."""
        new_count = 0
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries:
                # Apply recency filter 
                pub_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                if not self.is_recent(pub_parsed, hours=12):
                    continue

                url = entry.get("link") or entry.get("id")
                if not url:
                    continue

                if self._url_exists(cur, url):
                    continue

                # Attempt full scrape; fall back to feed summary if scrape fails
                headline, full_text = self._scrape_article(url)
                if not headline:
                    headline = entry.get("title", "")
                if not full_text:
                    full_text = entry.get("summary", "") or entry.get("description", "")

                published_date = self._parse_published(entry)

                inserted = self._save_article(
                    cur, url, headline, full_text, feed_name, published_date, category
                )
                new_count += inserted

        except Exception as exc:
            self._log_error(
                self.AGENT_NAME,
                f"Feed error [{feed_name}] {feed_url}: {exc}",
                traceback.format_exc(),
            )

        return new_count

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Process all active feeds. Returns total new article count."""
        total_new = 0
        feeds = []
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                feeds = self._get_active_feeds(cur)
        finally:
            conn.close()

        for feed in feeds:
            conn = self._get_conn()
            try:
                with conn:
                    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                        feed_id   = feed["id"]
                        feed_name = feed["name"]
                        feed_url  = feed["url"]
                        category  = feed["category"]

                        new_count = self._process_feed(cur, feed_id, feed_name, feed_url, category)
                        self._update_last_checked(cur, feed_id)
                        total_new += new_count
                        print(f"  [{feed_name}] +{new_count} new articles")
            except Exception as e:
                print(f"  Error processing {feed.get('name')}: {e}")
            finally:
                conn.close()

        return total_new

    # ------------------------------------------------------------------
    # Cleanup helpers
    # ------------------------------------------------------------------

    def discard_old_articles(self, db_conn) -> int:
        """
        DELETE articles older than 24 hours that are still unprocessed
        (status IN ('new', 'merged')) and have a low viral_score (< 60).
        Published articles are never deleted.
        Returns the number of rows deleted.
        """
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM articles
                    WHERE created_at < NOW() - INTERVAL '24 hours'
                      AND status IN ('new', 'merged')
                      AND viral_score < 60
                    """
                )
                deleted = cur.rowcount
            db_conn.commit()
            return deleted
        except Exception as exc:
            db_conn.rollback()
            print(f"discard_old_articles error: {exc}")
            return 0


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    agent = NewsDiscoveryAgent()
    print("NewsDiscoveryAgent starting...")
    count = agent.run()
    print(f"\nDone. Total new articles discovered: {count}")


if __name__ == "__main__":
    main()
