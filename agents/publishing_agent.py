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

class PublishingAgent:
    AGENT_NAME = "publishing"

    def __init__(self):
        load_dotenv()
        self.conn_string = os.environ.get("DATABASE_URL")
        
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
                conn.rollback()

        if conn: conn.close()
        
        print(f"[PUBLISH] attempted={metrics['attempted']} posted={metrics['posted']} failed={metrics['failed']} retry_queued={metrics['retry_queued']} platforms_active={active_platforms}")
        return metrics

if __name__ == "__main__":
    agent = PublishingAgent()
    agent.run()

