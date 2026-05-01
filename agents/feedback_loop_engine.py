import os
import json
import psycopg2
import psycopg2.extras
import requests
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

class FeedbackLoopEngine:
    AGENT_NAME = "feedback_loop"

    def __init__(self):
        self.conn_string = os.getenv("DATABASE_URL")
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "mistral")
        
    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def _ensure_schema(self, conn):
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS learning_insights (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        insights_json JSONB
                    );
                    
                    CREATE TABLE IF NOT EXISTS historical_stats (
                        id SERIAL PRIMARY KEY,
                        category TEXT UNIQUE,
                        best_hour JSONB,
                        best_platform TEXT,
                        best_day TEXT,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                conn.commit()
        except Exception:
            conn.rollback()

    def generate_insights(self, conn):
        # Local Analytics First
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT 
                    category, 
                    viral_score, 
                    posted_at, 
                    best_platform, 
                    caption_json, 
                    views, likes, shares, comments, clicks
                FROM articles
                WHERE status = 'published'
                AND posted_at > NOW() - INTERVAL '7 days'
            """)
            rows = cur.fetchall()
            
        if not rows:
            return None, 0, None
            
        stats = {
            "categories": {},
            "platforms": {},
            "hours": {},
            "viral_bands": {},
            "caption_styles": {"debate": 0, "emotional": 0, "professional": 0, "conversational": 0}
        }
        
        emotional_keywords = ["shocking", "breaking", "sad", "angry", "happy", "rage", "joy", "fear", "massive"]
        
        for r in rows:
            views = max(r.get("views") or 0, 1)
            likes = r.get("likes") or 0
            shares = r.get("shares") or 0
            comments = r.get("comments") or 0
            clicks = r.get("clicks") or 0
            
            eng_score = likes + (shares * 2) + (comments * 2) + (clicks * 1.5)
            
            # Category
            cat = (r.get("category") or "unknown").lower()
            if cat not in stats["categories"]: stats["categories"][cat] = []
            stats["categories"][cat].append(eng_score)
            
            # Platform & Hour
            plat = r.get("best_platform") or "x"
            posted = r.get("posted_at")
            if posted:
                hr = posted.astimezone(IST).hour
                if plat not in stats["hours"]: stats["hours"][plat] = {}
                if hr not in stats["hours"][plat]: stats["hours"][plat][hr] = []
                stats["hours"][plat][hr].append(eng_score)
            
            # Platform by Category
            if cat not in stats["platforms"]: stats["platforms"][cat] = {}
            if plat not in stats["platforms"][cat]: stats["platforms"][cat][plat] = []
            stats["platforms"][cat][plat].append(eng_score)
            
            # Viral Band
            v_score = r.get("viral_score") or 0
            band = f"{(int(v_score)//10)*10}-{(int(v_score)//10)*10+9}"
            if band not in stats["viral_bands"]: stats["viral_bands"][band] = []
            stats["viral_bands"][band].append(eng_score)
            
            # Caption Style
            caps = r.get("caption_json")
            if isinstance(caps, str): 
                try: caps = json.loads(caps)
                except: caps = {}
            elif caps is None:
                caps = {}
            
            cap_text = caps.get(plat, "")
            cap_lower = cap_text.lower()
            style = "conversational"
            if "?" in cap_text: style = "debate"
            elif any(kw in cap_lower for kw in emotional_keywords): style = "emotional"
            elif plat == "linkedin": style = "professional"
            
            stats["caption_styles"][style] += eng_score
            
        # Aggregate
        def avg(lst): return sum(lst) / max(len(lst), 1)
        
        agg = {
            "top_categories": sorted([{ "category": k, "avg_engagement": round(avg(v), 2) } for k,v in stats["categories"].items()], key=lambda x: x["avg_engagement"], reverse=True),
            "best_posting_times": {},
            "best_caption_style": max(stats["caption_styles"], key=stats["caption_styles"].get) if sum(stats["caption_styles"].values()) > 0 else "conversational",
            "best_platform_by_cat": {}
        }
        
        for p, hours in stats["hours"].items():
            if hours:
                best_hr = max(hours.keys(), key=lambda h: avg(hours[h]))
                agg["best_posting_times"][p] = f"{best_hr:02d}:00"
                
        for c, plats in stats["platforms"].items():
            if plats:
                best_p = max(plats.keys(), key=lambda x: avg(plats[x]))
                agg["best_platform_by_cat"][c] = best_p

        # Call LLM
        prompt = """You are a data-driven content strategist who optimizes social media performance.
Analyze the past 7 days of post performance and generate actionable insights.

OUTPUT JSON:
{
 "top_categories": [{"category":"technology","avg_engagement":9.2}],
 "best_posting_times": {"x":"20:00"},
 "best_caption_style":"debate",
 "top_hashtags":["AI","BreakingNews"],
 "score_calibration":{
   "actual_viral_threshold":78,
   "recommended_threshold":74
 },
 "weekly_insight":"Technology + breaking posts dominated reach. Evening posts outperformed mornings.",
 "next_week_strategy":"Raise tech priority, post X at 8PM, use sharper hooks."
}"""

        user_msg = f"Data:\n{json.dumps(agg)}"
        
        result = None
        try:
            resp = requests.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "prompt": user_msg,
                    "system": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=30
            )
            if resp.status_code == 200:
                txt = resp.json().get("response", "").strip()
                if txt.startswith("```json"): txt = txt[7:-3].strip()
                elif txt.startswith("```"): txt = txt[3:-3].strip()
                result = json.loads(txt)
        except Exception:
            pass
            
        if not result:
            result = {
                "top_categories": agg["top_categories"],
                "best_posting_times": agg["best_posting_times"],
                "best_caption_style": agg["best_caption_style"],
                "top_hashtags": [],
                "score_calibration": {"actual_viral_threshold": 75, "recommended_threshold": 70},
                "weekly_insight": "Deterministic summary generated.",
                "next_week_strategy": "Continue standard optimization."
            }
            
        return result, len(rows), agg

    def apply_optimizations(self, conn, insights, agg):
        configs_updated = 0
        try:
            # 1. Update learning_insights table
            with conn.cursor() as cur:
                cur.execute("INSERT INTO learning_insights (insights_json) VALUES (%s)", (json.dumps(insights),))
                configs_updated += 1
                
            # 2. Update historical_stats table
            with conn.cursor() as cur:
                for cat, best_plat in agg["best_platform_by_cat"].items():
                    best_hr_dict = {}
                    for p, hr_str in insights.get("best_posting_times", {}).items():
                        try:
                            best_hr_dict[p] = int(hr_str.split(":")[0])
                        except:
                            pass
                            
                    cur.execute("""
                        INSERT INTO historical_stats (category, best_hour, best_platform, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (category) DO UPDATE 
                        SET best_hour = EXCLUDED.best_hour,
                            best_platform = EXCLUDED.best_platform,
                            updated_at = NOW()
                    """, (cat, json.dumps(best_hr_dict), best_plat))
                    configs_updated += 1
                    
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"Error applying optimizations: {e}")
            
        return configs_updated

    def run(self):
        metrics = {
            "analyzed_posts": 0,
            "top_category": "none",
            "best_platform": "none",
            "threshold_updated": 0,
            "configs_updated": 0
        }
        
        conn = None
        try:
            conn = self._get_conn()
            if not conn: return metrics
            self._ensure_schema(conn)
            
            insights, rows_count, agg = self.generate_insights(conn)
            if not insights:
                return metrics
                
            metrics["analyzed_posts"] = rows_count
            if insights.get("top_categories"):
                metrics["top_category"] = insights["top_categories"][0].get("category", "none")
                
            times = insights.get("best_posting_times", {})
            metrics["best_platform"] = max(times.keys()) if times else "none"
            
            calib = insights.get("score_calibration", {})
            metrics["threshold_updated"] = calib.get("recommended_threshold", 70)
            
            metrics["configs_updated"] = self.apply_optimizations(conn, insights, agg)
            
        except Exception as e:
            print(f"FeedbackLoopEngine error: {e}")
        finally:
            if conn:
                conn.close()
                
        print(f"[LEARN] analyzed_posts={metrics['analyzed_posts']}")
        print(f"[LEARN] top_category={metrics['top_category']}")
        print(f"[LEARN] best_platform={metrics['best_platform']}")
        print(f"[LEARN] threshold_updated={metrics['threshold_updated']}")
        print(f"[LEARN] configs_updated={metrics['configs_updated']}")
        
        return metrics

if __name__ == "__main__":
    engine = FeedbackLoopEngine()
    engine.run()
