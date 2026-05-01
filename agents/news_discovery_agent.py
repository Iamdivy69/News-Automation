import os
import time
import calendar
import traceback
import json
import requests
import re
import feedparser
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from difflib import SequenceMatcher
from newspaper import Article
from dotenv import load_dotenv

load_dotenv()


class NewsDiscoveryAgent:
    """Autonomous agent that discovers and stores new articles from RSS feeds."""

    AGENT_NAME = "discovery"

    def __init__(self):
        self.conn_string = os.environ["DATABASE_URL"]
        self.use_llm_filter = os.getenv("USE_LLM_FILTER", "true").lower() == "true"

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
            VALUES (%s, %s, %s, %s, %s, %s, 'approved')
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
            article = Article(url, request_timeout=8)
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

    def _filter_batch(self, articles: list, approved_headlines: list) -> list:
        # 1. Cheap pre-filter before LLM
        def similar(a, b):
            sa = set(a.lower().split())
            sb = set(b.lower().split())
            return len(sa & sb) / max(1, len(sa | sb)) > 0.65

        prefiltered = []
        seen_urls = set()
        
        for art in articles:
            title = art.get("title", "")
            url = art.get("url", "")
            age = art.get("age_hours", 0)
            
            # - title too short (<25 chars)
            if len(title) < 25:
                continue
                
            # - obvious ads/promotions
            lower_title = title.lower()
            if any(ad in lower_title for ad in ["sponsored", "promoted", "buy now", "discount"]):
                continue
                
            # - duplicate URL
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # - age > 24h
            if age > 24:
                continue
                
            # - duplicate headline similarity > 90%
            is_dup = False
            for approved in approved_headlines:
                if similar(title, approved):
                    is_dup = True
                    break
            if is_dup:
                continue
                
            prefiltered.append(art)
            
        if not hasattr(self, '_current_prefiltered_count'):
            self._current_prefiltered_count = 0
        self._current_prefiltered_count += len(prefiltered)

        if not prefiltered:
            return []

        approved_indices = set()
        llm_success = False

        # 2. LLM filter
        if self.use_llm_filter:
            system_prompt = """You are a senior news editor for a viral social media news channel.

Your job is to filter a batch of raw news headlines and return ONLY those worth publishing.

ACCEPT articles that are:
- Breaking news (government, economy, war, disasters, major corporate events)
- High emotional impact (shocking, outrageous, inspiring, controversial)
- Celebrity or public figure involvement
- Record-breaking statistics or milestones
- Viral potential: debate-triggering, shareable, emotionally charged

REJECT articles that are:
- Press releases or promotional content
- Minor local news with no national/global impact
- Listicles or opinion pieces with no news hook
- Duplicate of a story already in the approved list
- Age > 12 hours unless the story is still actively trending

OUTPUT FORMAT:
JSON array only:
[
 {"id":"1","keep":true,"reason":"Major breaking geopolitical story"},
 {"id":"2","keep":false,"reason":"Low impact local article"}
]

Be aggressive in filtering.
Keep only TOP 20% stories."""

            user_prompt = "Batch:\n"
            for i, art in enumerate(prefiltered):
                user_prompt += f"id: {i}, title: {art['title']}, source: {art['source']}, age_hours: {art['age_hours']:.1f}\n"

            OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
            OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

            payload = {
                "model": OLLAMA_MODEL,
                "prompt": user_prompt,
                "system": system_prompt,
                "stream": False,
                "format": "json"
            }

            for attempt in range(2):
                timeout_val = 20 if attempt == 0 else 35
                try:
                    resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout_val)
                    if resp.status_code == 200:
                        text = resp.json().get("response", "").strip()
                        if text.startswith("```json"):
                            text = text[7:-3].strip()
                        elif text.startswith("```"):
                            text = text[3:-3].strip()
                            
                        data = json.loads(text)
                        if isinstance(data, list):
                            llm_success = True
                            for item in data:
                                if item.get("keep"):
                                    try:
                                        idx = int(item.get("id"))
                                        approved_indices.add(idx)
                                    except (ValueError, TypeError):
                                        pass
                            break
                except Exception as e:
                    print(f"LLM filter attempt {attempt+1} error: {e}")
                
                if attempt == 0:
                    time.sleep(2)
                    
            if not llm_success:
                print("[DISCOVERY] llm_slow_switching_fallback")
                print("[DISCOVERY] llm_disabled_for_cycle")
                self.use_llm_filter = False

        # 3. Rule-based fallback
        if not hasattr(self, '_current_rejected_low_score'):
            self._current_rejected_low_score = 0
            
        if not llm_success:
            cat2_kws = ["war", "election", "crash", "breaking"]
            cat1_kws = ["record", "shocking", "massive"]
            source_weights = {"reuters": 3, "bbc": 3, "ap": 3, "cnn": 2, "cnbc": 2, "bloomberg": 2}
            
            scored_articles = []
            for i, art in enumerate(prefiltered):
                score = 0
                title_lower = art["title"].lower()
                source_lower = art.get("source", "").lower()
                
                score += sum(2 for kw in cat2_kws if kw in title_lower)
                score += sum(1 for kw in cat1_kws if kw in title_lower)
                
                for src, w in source_weights.items():
                    if src in source_lower:
                        score += w
                        break
                
                capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', art["title"])
                if len(capitalized_words) >= 2:
                    score += 1
                    
                scored_articles.append((score, i))
                
            scored_articles.sort(key=lambda x: x[0], reverse=True)
            top_count = max(1, int(len(prefiltered) * 0.2))
            
            for score, i in scored_articles[:top_count]:
                if score < 2:
                    self._current_rejected_low_score += 1
                else:
                    approved_indices.add(i)

        return [art for i, art in enumerate(prefiltered) if i in approved_indices]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Process all active feeds. Returns total new article count."""
        start_time = time.time()
        print("[DISCOVERY] started")
        total_new = 0
        conn = self._get_conn()
        print("[DISCOVERY] db connected")
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                feeds = self._get_active_feeds(cur)
                # Get already approved headlines for duplication check
                cur.execute("SELECT headline FROM articles WHERE created_at >= NOW() - INTERVAL '24 hours'")
                approved_headlines = [row["headline"] for row in cur.fetchall() if row["headline"]]
        finally:
            conn.close()

        print("[DISCOVERY] fetching rss")
        all_raw_articles = []
        for feed in feeds:
            if time.time() - start_time > 45:
                print("[DISCOVERY] 45s timeout reached, aborting fetch loop safely.")
                break
                
            feed_id   = feed["id"]
            feed_name = feed["name"]
            feed_url  = feed["url"]
            category  = feed["category"]

            print(f"[DISCOVERY] fetching {feed_name} RSS")
            conn = None
            try:
                conn = self._get_conn()
                with conn.cursor() as cur:
                    resp = requests.get(feed_url, timeout=8, headers={"User-Agent":"Mozilla/5.0"})
                    parsed = feedparser.parse(resp.content)
                    
                    print(f"[DISCOVERY] success {feed_name} {len(parsed.entries)} items")
                    for entry in parsed.entries:
                        pub_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
                        if not self.is_recent(pub_parsed, hours=12):
                            continue

                        url = entry.get("link") or entry.get("id")
                        if not url:
                            continue

                        if self._url_exists(cur, url):
                            continue

                        headline = entry.get("title", "")
                        age_hours = 0
                        if pub_parsed:
                            try:
                                published_ts = calendar.timegm(pub_parsed)
                                current_ts = calendar.timegm(time.gmtime())
                                age_hours = max(0, (current_ts - published_ts) / 3600.0)
                            except Exception:
                                pass

                        all_raw_articles.append({
                            "id": url,
                            "title": headline,
                            "source": feed_name,
                            "age_hours": age_hours,
                            "url": url,
                            "category": category,
                            "published_date": self._parse_published(entry),
                            "entry": entry,
                            "feed_id": feed_id
                        })
            except requests.exceptions.Timeout:
                print(f"[DISCOVERY] skipped {feed_name} timeout")
            except Exception as e:
                print(f"[DISCOVERY] skipped {feed_name} error")
                self._log_error(
                    self.AGENT_NAME,
                    f"Feed error [{feed_name}] {feed_url}: {e}",
                    traceback.format_exc(),
                )
            finally:
                if conn:
                    conn.close()

        print(f"[DISCOVERY] fetched {len(feeds)} feeds")

        total_fetched_raw = len(all_raw_articles)

        def get_source_score(src):
            src_lower = src.lower()
            if "reuters" in src_lower or "bbc" in src_lower or "ap" in src_lower: return 5
            if "bloomberg" in src_lower: return 4
            if "cnn" in src_lower or "cnbc" in src_lower: return 3
            return 1
            
        all_raw_articles.sort(key=lambda x: get_source_score(x.get("source", "")), reverse=True)

        MAX_RAW_PER_RUN = 300
        if len(all_raw_articles) > MAX_RAW_PER_RUN:
            all_raw_articles = all_raw_articles[:MAX_RAW_PER_RUN]

        total_fetched_capped = len(all_raw_articles)
        self._current_prefiltered_count = 0
        self._current_rejected_low_score = 0
        
        print("[DISCOVERY] llm_batch=10")
        approved_articles = []
        for i in range(0, total_fetched_capped, 10):
            batch = all_raw_articles[i:i+10]
            batch_approved = self._filter_batch(batch, approved_headlines)
            approved_articles.extend(batch_approved)

        print(f"[DISCOVERY] fetched={total_fetched_raw}")
        print(f"[DISCOVERY] capped_after_priority={total_fetched_capped}")
        print(f"[DISCOVERY] prefiltered={self._current_prefiltered_count}")
        print(f"[DISCOVERY] approved={len(approved_articles)}")
        print(f"[DISCOVERY] rejected_low_score={self._current_rejected_low_score}")

        conn = self._get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    for article in approved_articles:
                        url = article["url"]
                        headline, full_text = self._scrape_article(url)
                        if not headline:
                            headline = article["title"]
                        if not full_text:
                            entry = article["entry"]
                            full_text = entry.get("summary", "") or entry.get("description", "")
                        
                        inserted = self._save_article(
                            cur, url, headline, full_text, article["source"], article["published_date"], article["category"]
                        )
                        if inserted:
                            total_new += 1
                    
                    for feed in feeds:
                        self._update_last_checked(cur, feed["id"])
        finally:
            conn.close()

        print("[DISCOVERY] completed")
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

    def purge_stale_articles(self, db_conn) -> int:
        """
        DELETE unprocessed articles older than 12 hours.
        Keeps articles that have already been summarised, approved, or published.
        Returns count of deleted rows.
        """
        try:
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM articles
                    WHERE created_at < NOW() - INTERVAL '12 hours'
                      AND status IN ('new', 'discarded', 'merged')
                    """
                )
                deleted = cur.rowcount
            db_conn.commit()
            print(f"  purged {deleted} stale articles")
            return deleted
        except Exception as exc:
            db_conn.rollback()
            print(f"purge_stale_articles error: {exc}")
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
