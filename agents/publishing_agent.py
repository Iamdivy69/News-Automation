import os
import sys
import time
import json
import requests
import psycopg2
import traceback
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

<<<<<<< HEAD
=======
CREATE_POSTS_TABLE = """
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    article_id INT,
    platform TEXT NOT NULL,
    post_id TEXT,
    posted_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'published',
    engagement_score FLOAT DEFAULT 0
);
"""

>>>>>>> fd315f50abf38353da795d9f1ab9eb3bd318e436
class PublishingAgent:
    AGENT_NAME = "publishing"

    def __init__(self):
        load_dotenv()
        self.conn_string = os.environ.get("DATABASE_URL")
<<<<<<< HEAD
=======
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "mistral")
>>>>>>> fd315f50abf38353da795d9f1ab9eb3bd318e436
        
        self.telegram_bot = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.telegram_chat = os.environ.get("TELEGRAM_CHANNEL_ID")
        self.x_token = os.environ.get("X_BEARER_TOKEN", "")
        self.ig_token = os.environ.get("IG_ACCESS_TOKEN", "")
        self.li_token = os.environ.get("LINKEDIN_TOKEN", "")
        self.fb_token = os.environ.get("FB_ACCESS_TOKEN", "")
        
        if not self.conn_string:
            print("[WARN] DATABASE_URL not set.")

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

<<<<<<< HEAD
    def auto_discard(self, conn):
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE articles 
                    SET status = 'discarded', processing_stage = 'discarded' 
                    WHERE status = 'image_ready' 
                      AND created_at < NOW() - INTERVAL '6 hours' 
                      AND viral_score < 50
                """)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Auto-discard error: {e}")

    def _post_twitter(self, article, text, img_path):
        if not self.x_token: return False, "missing_token"
        return True, "tw_123"

    def _post_instagram(self, article, text, img_path):
        if not self.ig_token: return False, "missing_token"
        return True, "ig_123"

    def _post_linkedin(self, article, text, img_path):
        if not self.li_token: return False, "missing_token"
        return True, "li_123"

    def _post_facebook(self, article, text, img_path):
        if not self.fb_token: return False, "missing_token"
        return True, "fb_123"

    def _post_telegram(self, article, text, img_path):
        if not self.telegram_bot or not self.telegram_chat:
            return False, "missing_token"
        try:
            base_url = f"https://api.telegram.org/bot{self.telegram_bot}"
            if img_path and os.path.exists(img_path):
                url = f"{base_url}/sendPhoto"
                data = {"chat_id": self.telegram_chat, "caption": text[:1000], "parse_mode": "HTML"}
                with open(img_path, "rb") as f:
                    resp = requests.post(url, data=data, files={"photo": f}, timeout=15)
            else:
                url = f"{base_url}/sendMessage"
                resp = requests.post(url, json={"chat_id": self.telegram_chat, "text": text[:4000], "parse_mode": "HTML"}, timeout=15)
            
            if resp.status_code == 200 and resp.json().get("ok"):
                return True, str(resp.json()["result"]["message_id"])
            return False, str(resp.text)
        except Exception as e:
            return False, str(e)

    def run(self):
        metrics = {
            "processed": 0, "attempted": 0, "posted": 0, "failed": 0, "retry_queued": 0
        }
        active_platforms = []
        if self.x_token: active_platforms.append("twitter")
        if self.ig_token: active_platforms.append("instagram")
        if self.li_token: active_platforms.append("linkedin")
        if self.fb_token: active_platforms.append("facebook")
        if self.telegram_bot and self.telegram_chat: active_platforms.append("telegram")
        
        try:
            conn = self._get_conn()
            self.auto_discard(conn)
            
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("""
                    SELECT * FROM articles 
                    WHERE top_30_selected = TRUE
                      AND (
                          status = 'image_ready'
                          OR (retry_count < 3 AND platform_status::text LIKE '%"failed"%')
                      )
                    ORDER BY viral_score DESC
                    LIMIT 20
                """)
                articles = cur.fetchall()
        except Exception as e:
            print(f"Fetch error: {e}")
            if 'conn' in locals() and conn:
                conn.rollback()
                conn.close()
            return metrics
            
        metrics["attempted"] = len(articles)
        metrics["processed"] = len(articles)
        
        for row in articles:
            art = dict(row)
            art_id = art["id"]
            img_path = art.get("image_path")
            
            platform_status = art.get("platform_status") or {}
            if isinstance(platform_status, str):
                try: platform_status = json.loads(platform_status)
                except: platform_status = {}
                
            retry_count = art.get("retry_count", 0)
            captions = art.get("captions") or {}
            if isinstance(captions, str):
                try: captions = json.loads(captions)
                except: captions = {}
                
            any_success = False
            all_failed = True
            
            # Platforms to process: either never attempted, or "failed" (but not permanently_failed)
            for plat in active_platforms:
                current_stat = platform_status.get(plat)
                if current_stat in ["posted", "permanently_failed"]:
                    if current_stat == "posted":
                        any_success = True
                        all_failed = False
                    continue
                
                # Use specific caption or fallback to headline
                cap_text = captions.get(plat, art.get("headline", ""))
                
                success = False
                err_msg = ""
                if plat == "twitter":
                    success, err_msg = self._post_twitter(art, cap_text, img_path)
                elif plat == "instagram":
                    success, err_msg = self._post_instagram(art, cap_text, img_path)
                elif plat == "linkedin":
                    success, err_msg = self._post_linkedin(art, cap_text, img_path)
                elif plat == "facebook":
                    success, err_msg = self._post_facebook(art, cap_text, img_path)
                elif plat == "telegram":
                    success, err_msg = self._post_telegram(art, cap_text, img_path)
                    
                if success:
                    platform_status[plat] = "posted"
                    any_success = True
                    all_failed = False
                else:
                    if retry_count >= 2: # This was the 3rd attempt (0, 1, 2)
                        platform_status[plat] = "permanently_failed"
                    else:
                        platform_status[plat] = "failed"
            
            # If there was at least one failure that isn't permanent, we consider this a retry queue candidate
            needs_retry = any(stat == "failed" for stat in platform_status.values())
            
            if needs_retry:
                retry_count += 1
                
            # Determine new overall status
            if any_success:
                new_status = 'published'
                metrics["posted"] += 1
            elif all_failed:
                new_status = 'failed'
                metrics["failed"] += 1
            else:
                new_status = art.get("status", "image_ready")
                
            if needs_retry:
                metrics["retry_queued"] += 1
                
            # Update DB
            try:
                with conn.cursor() as cur:
                    if any_success:
                        cur.execute("""
                            UPDATE articles 
                            SET status = %s,
                                platform_status = %s,
                                retry_count = %s,
                                published_at = COALESCE(published_at, NOW()),
                                processing_stage = 'published'
                            WHERE id = %s
                        """, (new_status, json.dumps(platform_status), retry_count, art_id))
                    else:
                        cur.execute("""
                            UPDATE articles 
                            SET status = %s,
                                platform_status = %s,
                                retry_count = %s,
                                processing_stage = %s
                            WHERE id = %s
                        """, (new_status, json.dumps(platform_status), retry_count, new_status, art_id))
                conn.commit()
            except Exception as e:
                print(f"DB update error for article {art_id}: {e}")
=======
    def generate_captions(self, article):
        fallback = {
            "x": article.get("title", "")[:200],
            "instagram": "Breaking: " + article.get("title", ""),
            "linkedin": article.get("title", "") + "\n\n" + str(article.get("summary", ""))[:100],
            "facebook": "Check this out: " + article.get("title", ""),
            "telegram": f"<b>{article.get('title', '')}</b>\n\nSource: {article.get('source', '')}",
            "youtube_shorts": "Follow for more: " + article.get("title", ""),
            "viral_hashtags": ["#news"],
            "best_platform": "x"
        }
        
        system_prompt = """You are a viral social media copywriter who has grown accounts to millions of followers.
Generate platform-optimized captions for a news story.

PLATFORM RULES:
X:
- Max 240 chars
- Sharp, debate-triggering
- Strong hook/question
- No hashtags in body
- 1-2 hashtags only at end

Instagram:
- 3-4 short sentences
- Emotional + personal
- Start with hook word: Massive. Breaking. Finally.
- 5-8 hashtags
- line breaks

LinkedIn:
- 2-3 short paragraphs
- Professional insight
- Industry implications
- End with thoughtful question
- Max 2 hashtags

Facebook:
- Conversational
- Broad audience
- 2-4 sentences
- Emotion hook
- Ask audience question
- 2-3 hashtags

Telegram:
- 3-5 sentence factual summary
- Use <b>bold</b>
- Include source attribution
- No hashtags

YouTube Shorts:
- Hook in first 5 words
- Curiosity gap
- 3 short sentences
- CTA: Follow for more

OUTPUT JSON:
{
 "x": "",
 "instagram": "",
 "linkedin": "",
 "facebook": "",
 "telegram": "",
 "youtube_shorts": "",
 "viral_hashtags": [],
 "best_platform": "x|instagram|linkedin|facebook|telegram"
}"""
        user_prompt = f"Title: {article.get('title')}\nSummary: {article.get('summary')}\nCategory: {article.get('category')}\nEmotion: {article.get('emotion')}"
        
        try:
            resp = requests.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=18
            )
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text.startswith("```json"): text = text[7:-3].strip()
                elif text.startswith("```"): text = text[3:-3].strip()
                import json
                data = json.loads(text)
                if "x" in data:
                    return data
        except Exception as e:
            print(f"Caption generation error: {e}")
            pass
        return fallback

    def _post_x(self, article, text, img_path):
        if not self.x_token: return False, "missing_token"
        return True, "x_123"

    def _post_instagram(self, article, text, img_path):
        if not self.ig_token: return False, "missing_token"
        return True, "ig_123"

    def _post_linkedin(self, article, text, img_path):
        if not self.li_token: return False, "missing_token"
        return True, "li_123"

    def _post_facebook(self, article, text, img_path):
        if not self.fb_token: return False, "missing_token"
        return True, "fb_123"

    def _post_telegram(self, article, text, img_path):
        if not self.telegram_bot or not self.telegram_chat:
            return False, "missing_token"
        try:
            base_url = f"https://api.telegram.org/bot{self.telegram_bot}"
            if img_path and os.path.exists(img_path):
                url = f"{base_url}/sendPhoto"
                data = {"chat_id": self.telegram_chat, "caption": text[:1000], "parse_mode": "HTML"}
                with open(img_path, "rb") as f:
                    resp = requests.post(url, data=data, files={"photo": f}, timeout=15)
            else:
                url = f"{base_url}/sendMessage"
                resp = requests.post(url, json={"chat_id": self.telegram_chat, "text": text[:4000], "parse_mode": "HTML"}, timeout=15)
            
            if resp.status_code == 200 and resp.json().get("ok"):
                return True, str(resp.json()["result"]["message_id"])
            return False, str(resp.text)
        except Exception as e:
            return False, str(e)

    def is_good_time(self, platform, is_urgent):
        if is_urgent: return True
        h = datetime.now().hour
        wd = datetime.now().weekday()
        if platform == "x":
            return h in [8, 9, 13, 14, 20, 21]
        elif platform == "instagram":
            return h in [11, 12, 18, 19, 21, 22]
        elif platform == "linkedin":
            if wd > 4: return False
            return h in [8, 9, 12, 13]
        elif platform == "facebook":
            return h in [9, 10, 19, 20]
        elif platform == "telegram":
            return True
        return True

    def get_best_platform(self, cat):
        cat = cat.lower()
        if "politic" in cat or "break" in cat: return "x"
        if "financ" in cat: return "linkedin"
        if "tech" in cat: return "x"
        if "sport" in cat: return "instagram"
        if "entertain" in cat: return "youtube_shorts"
        if "scienc" in cat: return "linkedin"
        if "weather" in cat or "disaster" in cat: return "facebook"
        return "x"

    def run(self):
        metrics = {
            "queued": 0, "posted": 0, "failed": 0,
            "skipped_duplicate": 0, "scheduled": 0,
            "retries": 0, "multipost": 0, "token_missing": 0,
            "cooldown_skips": 0
        }
        
        try:
            conn = self._get_conn()
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # Add analytics columns if they don't exist dynamically
                try:
                    cur.execute("ALTER TABLE articles ADD COLUMN views INT DEFAULT 0, ADD COLUMN likes INT DEFAULT 0, ADD COLUMN shares INT DEFAULT 0, ADD COLUMN comments INT DEFAULT 0, ADD COLUMN clicks INT DEFAULT 0;")
                    conn.commit()
                except psycopg2.errors.DuplicateColumn:
                    conn.rollback()
                except Exception:
                    conn.rollback()

                cur.execute("""
                    SELECT * FROM articles 
                    WHERE status IN ('image_ready', 'queued', 'scheduled')
                    ORDER BY 
                      COALESCE(priority_level, 0) DESC, 
                      viral_score DESC, 
                      created_at DESC 
                    LIMIT 20
                """)
                articles = cur.fetchall()
        except Exception as e:
            print(f"Fetch error: {e}")
            conn.rollback()
            if conn: conn.close()
            return metrics
            
        metrics["queued"] = len(articles)
        
        import json
        import hashlib
        
        for row in articles:
            art = dict(row)
            art_id = art["id"]
            title = art.get("headline") or art.get("title", "")
            
            # Dupe Check
            try:
                with conn.cursor() as cur:
                    dup_check = art.get("duplicate_of_id")
                    if dup_check is None:
                        dup_check = -1
                    cur.execute("""
                        SELECT COUNT(*) FROM articles 
                        WHERE (headline = %s OR id = %s OR id = %s)
                        AND status = 'published'
                        AND created_at > NOW() - INTERVAL '24 hours'
                    """, (title, art_id, dup_check))
                    if cur.fetchone()[0] > 0:
                        with conn.cursor() as uc:
                            uc.execute("UPDATE articles SET status='discarded_duplicate' WHERE id=%s", (art_id,))
                        conn.commit()
                        metrics["skipped_duplicate"] += 1
                        continue
            except Exception:
                conn.rollback()
                pass
                
            # Captions
            if not art.get("caption_json"):
                caps = self.generate_captions({
                    "title": title,
                    "summary": art.get("full_text", ""),
                    "category": art.get("category", ""),
                    "emotion": art.get("emotion", ""),
                    "viral_score": art.get("viral_score", 0),
                    "source": art.get("source", "")
                })
                art["caption_json"] = caps
            else:
                caps = art.get("caption_json")
                if isinstance(caps, str): caps = json.loads(caps)
                
            # Platform Routing
            best_plat = caps.get("best_platform")
            if not best_plat or best_plat not in ["x", "instagram", "linkedin", "facebook", "telegram", "youtube_shorts"]:
                best_plat = self.get_best_platform(art.get("category", ""))
                
            platforms_to_post = set([best_plat])
            
            cat_lower = art.get("category", "").lower()
            if "break" in cat_lower or "break" in title.lower():
                platforms_to_post.add("telegram")
            if "entertain" in cat_lower:
                platforms_to_post.update(["instagram", "youtube_shorts"])
            
            score = int(art.get("viral_score", 0))
            if score >= 85:
                sec_plat = "instagram" if best_plat == "x" else "x"
                platforms_to_post.add(sec_plat)
                metrics["multipost"] += 1
                
            is_urgent = (art.get("priority_level", 0) > 0) or ("urgent" in title.lower()) or ("breaking" in title.lower())
            
            # Cooldown & Time Checks
            img_path = art.get("image_path")
            posted_json = art.get("posted_platforms_json") or {}
            if isinstance(posted_json, str): posted_json = json.loads(posted_json)
            
            success_any = False
            last_err_msg = ""
            
            for plat in list(platforms_to_post):
                if not self.is_good_time(plat, is_urgent):
                    platforms_to_post.remove(plat)
                    continue
                
                # Check 10-minute cooldown
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1 FROM articles WHERE status='published' AND posted_platforms_json::text LIKE %s AND posted_at > NOW() - INTERVAL '10 minutes' LIMIT 1", (f'%"{plat}"%',))
                        if cur.fetchone():
                            platforms_to_post.remove(plat)
                            metrics["cooldown_skips"] += 1
                            continue
                except Exception:
                    conn.rollback()
                    pass
            
            if not platforms_to_post:
                metrics["scheduled"] += 1
                with conn.cursor() as cur:
                    cur.execute("UPDATE articles SET status='scheduled', caption_json=%s WHERE id=%s", (json.dumps(caps), art_id))
                conn.commit()
                continue
                
            # Post to platforms
            for plat in platforms_to_post:
                success = False
                err_msg = ""
                if plat == "telegram":
                    success, err_msg = self._post_telegram(art, caps.get("telegram", ""), img_path)
                elif plat == "x":
                    success, err_msg = self._post_x(art, caps.get("x", ""), img_path)
                elif plat == "instagram":
                    success, err_msg = self._post_instagram(art, caps.get("instagram", ""), img_path)
                elif plat == "linkedin":
                    success, err_msg = self._post_linkedin(art, caps.get("linkedin", ""), img_path)
                elif plat == "facebook":
                    success, err_msg = self._post_facebook(art, caps.get("facebook", ""), img_path)
                elif plat == "youtube_shorts":
                    success, err_msg = False, "missing_token"
                
                if err_msg == "missing_token":
                    metrics["token_missing"] += 1
                
                if success:
                    success_any = True
                    posted_json[plat] = err_msg
                    metrics["posted"] += 1
                else:
                    last_err_msg = err_msg
            
            retries = art.get("retry_count", 0)
            
            try:
                with conn.cursor() as cur:
                    if success_any:
                        best_plat = list(platforms_to_post)[0] # update best_platform to one that succeeded
                        cur.execute("""
                            UPDATE articles 
                            SET status='published', 
                                caption_json=%s, 
                                posted_platforms_json=%s, 
                                best_platform=%s, 
                                posted_at=NOW(),
                                views=0, likes=0, shares=0, comments=0, clicks=0
                            WHERE id=%s
                        """, (json.dumps(caps), json.dumps(posted_json), best_plat, art_id))
                    else:
                        retries += 1
                        metrics["retries"] += 1
                        if retries >= 3:
                            metrics["failed"] += 1
                            cur.execute("UPDATE articles SET status='publish_failed', retry_count=%s, last_error=%s, caption_json=%s WHERE id=%s", (retries, last_err_msg, json.dumps(caps), art_id))
                        else:
                            cur.execute("UPDATE articles SET retry_count=%s, last_error=%s, caption_json=%s WHERE id=%s", (retries, last_err_msg, json.dumps(caps), art_id))
                conn.commit()
            except Exception as e:
                print(f"Error updating publish status: {e}")
>>>>>>> fd315f50abf38353da795d9f1ab9eb3bd318e436
                conn.rollback()

        if conn: conn.close()
        
<<<<<<< HEAD
        print(f"[PUBLISH] attempted={metrics['attempted']} posted={metrics['posted']} failed={metrics['failed']} retry_queued={metrics['retry_queued']} platforms_active={active_platforms}")
=======
        avg_retry = round(metrics["retries"] / max(1, metrics["queued"]), 1)
        print(f"[PUBLISH] queued={metrics['queued']}")
        print(f"[PUBLISH] posted={metrics['posted']}")
        print(f"[PUBLISH] failed={metrics['failed']}")
        print(f"[PUBLISH] skipped_duplicate={metrics['skipped_duplicate']}")
        print(f"[PUBLISH] scheduled={metrics['scheduled']}")
        print(f"[PUBLISH] avg_retry={avg_retry}")
        print(f"[PUBLISH] multipost={metrics['multipost']}")
        print(f"[PUBLISH] token_missing={metrics['token_missing']}")
        print(f"[PUBLISH] cooldown_skips={metrics['cooldown_skips']}")
        
>>>>>>> fd315f50abf38353da795d9f1ab9eb3bd318e436
        return metrics

if __name__ == "__main__":
    agent = PublishingAgent()
<<<<<<< HEAD
    agent.run()
=======
    results = agent.run()
>>>>>>> fd315f50abf38353da795d9f1ab9eb3bd318e436

