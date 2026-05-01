import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    import pytz as ZoneInfo # fallback

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

class PostingTimeEngine:
    AGENT_NAME = "posting_time"

    PEAK_WINDOWS = {
        "x": [(7,9), (12,13), (20,22)],
        "instagram": [(8,10), (19,21)],
        "linkedin": [(7,9), (12,13)],
        "facebook": [(7,9), (18,20)],
        "telegram": [(0,23)],
        "youtube_shorts": [(12,23)]
    }

    CATEGORY_BIAS = {
        "politics": ["x", "telegram"],
        "breaking": ["telegram", "x"],
        "finance": ["linkedin", "x"],
        "technology": ["x", "instagram"],
        "sports": ["instagram", "facebook"],
        "entertainment": ["instagram", "youtube_shorts"],
        "science": ["linkedin", "x"],
        "weather": ["telegram", "facebook", "x"],
        "disaster": ["telegram", "facebook", "x"]
    }

    def __init__(self):
        self.conn_string = os.getenv("DATABASE_URL")
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def get_next_peak(self, platform, current_local_dt, score):
        if score < 50:
            current_local_dt += timedelta(days=1)
            current_local_dt = current_local_dt.replace(hour=7, minute=0, second=0)

        test_dt = current_local_dt
        for _ in range(7 * 24):
            h = test_dt.hour
            wd = test_dt.weekday()
            
            if platform == "linkedin" and wd >= 5:
                test_dt += timedelta(hours=1)
                continue
                
            windows = self.PEAK_WINDOWS.get(platform, [(0, 23)])
            for start_h, end_h in windows:
                if start_h <= h <= end_h:
                    return test_dt.astimezone(UTC)
            test_dt += timedelta(hours=1)
            
        return current_local_dt.astimezone(UTC)

    def optimize(self, article, stats=None):
        res_metrics = {"crosspost_all": False, "used_historical": False, "custom_tz": False}
        
        is_breaking = article.get("is_breaking", False)
        title = article.get("headline") or article.get("title") or ""
        title_lower = title.lower()
        if "breaking" in title_lower or "urgent" in title_lower:
            is_breaking = True
            
        score = int(article.get("viral_score", 0))
        cat = (article.get("category") or "").lower()
        
        bias_list = ["x"]
        for k, v in self.CATEGORY_BIAS.items():
            if k in cat or k in title_lower:
                bias_list = list(v)
                break
                
        if score >= 90:
            # Cross-post all relevant
            all_rel = set(bias_list + ["x", "telegram", "facebook"])
            bias_list = list(all_rel)
            res_metrics["crosspost_all"] = True
            
        priority_platform = bias_list[0]
        
        tz_str = article.get("audience_timezone")
        local_tz = IST
        if tz_str:
            try:
                local_tz = ZoneInfo(tz_str) if 'ZoneInfo' in globals() else IST
                if local_tz != IST:
                    res_metrics["custom_tz"] = True
            except Exception:
                pass
                
        now_utc = datetime.now(UTC)
        now_local = now_utc.astimezone(local_tz)
        
        post_immediately = False
        next_post_at = now_utc
        schedule = {}
        
        if is_breaking:
            post_immediately = True
            for i, p in enumerate(bias_list):
                # Stagger even immediate posts slightly to avoid API rate limits
                schedule[p] = (now_utc + timedelta(minutes=i*2)).isoformat()
            
        elif score >= 80:
            next_post_at = now_utc + timedelta(minutes=30)
            for i, p in enumerate(bias_list):
                schedule[p] = (next_post_at + timedelta(minutes=i*15)).isoformat()
            
        else:
            custom_hour = None
            if stats and "best_hour_by_category" in stats:
                cat_stats = stats["best_hour_by_category"].get(cat)
                if cat_stats:
                    custom_hour = cat_stats.get(priority_platform)
            
            if custom_hour is not None:
                res_metrics["used_historical"] = True
                test_dt = now_local
                if score < 50: test_dt += timedelta(days=1)
                for _ in range(48):
                    if test_dt.hour == custom_hour:
                        next_post_at = test_dt.astimezone(UTC)
                        break
                    test_dt += timedelta(hours=1)
                schedule[priority_platform] = next_post_at.isoformat()
            else:
                next_post_at = self.get_next_peak(priority_platform, now_local, score)
                schedule[priority_platform] = next_post_at.isoformat()
                
            for i, p in enumerate(bias_list[1:]):
                # Staggered multi-platform: secondary +30m, tertiary +2h
                offset = timedelta(minutes=30) if i == 0 else timedelta(hours=2)
                schedule[p] = (self.get_next_peak(p, now_local, score) + offset).isoformat()
                
        # Weekend adjustment: deprioritize linkedin
        if "linkedin" in schedule:
            li_dt = datetime.fromisoformat(schedule["linkedin"])
            if li_dt.weekday() >= 5:
                # push to monday
                days_ahead = 7 - li_dt.weekday()
                schedule["linkedin"] = (li_dt + timedelta(days=days_ahead)).isoformat()
                
        return {
            "post_immediately": post_immediately,
            "schedule": schedule,
            "priority_platform": priority_platform,
            "reason": "breaking" if is_breaking else ("viral" if score>=80 else "standard"),
            "next_post_at": next_post_at,
            "metrics": res_metrics
        }

    def _ensure_schema(self, conn):
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE articles 
                    ADD COLUMN IF NOT EXISTS scheduled_post_json JSONB,
                    ADD COLUMN IF NOT EXISTS priority_platform TEXT,
                    ADD COLUMN IF NOT EXISTS post_immediately BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS next_post_at TIMESTAMPTZ
                """)
                conn.commit()
        except Exception as e:
            conn.rollback()

    def run(self):
        metrics = {
            "optimized": 0,
            "immediate": 0,
            "scheduled": 0,
            "moved_to_queue": 0,
            "top_platform_counts": {},
            "total_delay_minutes": 0,
            "crosspost_all": 0,
            "used_historical": 0,
            "timezone_mix": 0
        }
        
        conn = None
        try:
            conn = self._get_conn()
            if not conn: return metrics
            self._ensure_schema(conn)
            
            # Fetch historical stats
            historical_stats = {
                "best_hour_by_category": {},
                "best_platform_ctr": {},
                "best_day_per_category": {}
            }
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute("SELECT category, best_hour, best_platform, best_day FROM historical_stats LIMIT 100")
                    for row in cur.fetchall():
                        c = row.get("category", "").lower()
                        historical_stats["best_hour_by_category"][c] = row.get("best_hour", {})
            except Exception:
                pass
            
            # 1. OPTIMIZE NEW ARTICLES
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT * FROM articles 
                    WHERE status IN ('image_ready', 'approved_unique')
                      AND scheduled_post_json IS NULL
                    LIMIT 100
                """)
                articles = cur.fetchall()
            
            for row in articles:
                art = dict(row)
                res = self.optimize(art, historical_stats)
                
                metrics["optimized"] += 1
                
                rm = res.get("metrics", {})
                if rm.get("crosspost_all"): metrics["crosspost_all"] += 1
                if rm.get("used_historical"): metrics["used_historical"] += 1
                if rm.get("custom_tz"): metrics["timezone_mix"] += 1
                
                if res["post_immediately"]:
                    metrics["immediate"] += 1
                    # If it's image_ready, we can queue it immediately
                    status = 'queued' if art["status"] == 'image_ready' else 'approved_unique'
                else:
                    metrics["scheduled"] += 1
                    status = 'scheduled' if art["status"] == 'image_ready' else 'approved_unique'
                    
                plat = res["priority_platform"]
                metrics["top_platform_counts"][plat] = metrics["top_platform_counts"].get(plat, 0) + 1
                
                delay = (res["next_post_at"] - datetime.now(UTC)).total_seconds() / 60.0
                if delay > 0: metrics["total_delay_minutes"] += delay
                
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE articles 
                        SET scheduled_post_json = %s,
                            priority_platform = %s,
                            post_immediately = %s,
                            next_post_at = %s,
                            status = %s
                        WHERE id = %s
                    """, (
                        json.dumps(res["schedule"]),
                        res["priority_platform"],
                        res["post_immediately"],
                        res["next_post_at"],
                        status,
                        art["id"]
                    ))
                conn.commit()
                
            # 2. REQUEUE LOGIC
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE articles
                    SET status = 'queued'
                    WHERE status = 'scheduled' 
                      AND next_post_at <= NOW()
                """)
                requeued = cur.rowcount
                conn.commit()
                metrics["moved_to_queue"] += requeued
                
        except Exception as e:
            print(f"PostingTimeEngine error: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
        finally:
            if conn:
                conn.close()
                
        top_plat = max(metrics["top_platform_counts"], key=metrics["top_platform_counts"].get) if metrics["top_platform_counts"] else "none"
        avg_delay = round(metrics["total_delay_minutes"] / max(1, metrics["scheduled"]), 1)
        
        print(f"[TIME] optimized={metrics['optimized']}")
        print(f"[TIME] immediate={metrics['immediate']}")
        print(f"[TIME] scheduled={metrics['scheduled']}")
        print(f"[TIME] moved_to_queue={metrics['moved_to_queue']}")
        print(f"[TIME] top_platform={top_plat}")
        print(f"[TIME] avg_delay_minutes={avg_delay}")
        print(f"[TIME] crosspost_all={metrics['crosspost_all']}")
        print(f"[TIME] used_historical={metrics['used_historical']}")
        print(f"[TIME] timezone_mix={metrics['timezone_mix']}")
        
        return metrics

if __name__ == "__main__":
    engine = PostingTimeEngine()
    engine.run()
