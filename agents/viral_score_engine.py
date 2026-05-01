import os
import time
import json
import datetime
import requests
import psycopg2
import psycopg2.extras

class ViralScoreEngine:
    """Engine to estimate virality and breaking news probability for articles."""
    
    AGENT_NAME = "viral_scorer"

    def __init__(self):
        self.conn_string = os.environ.get("DATABASE_URL")
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "mistral")

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)
        
    def _get_age_hours(self, pub_date):
        if not pub_date:
            return 24
        if isinstance(pub_date, str):
            try:
                pub_date = datetime.datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        if isinstance(pub_date, datetime.datetime):
            now = datetime.datetime.now(pub_date.tzinfo or datetime.timezone.utc)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=datetime.timezone.utc)
            hours_diff = max(0, int((now - pub_date).total_seconds() / 3600))
            return hours_diff
        return 24

    def score_article(self, article: dict, use_llm: bool = True) -> dict:
        """
        Input: { id, title, source, age_hours, summary, category, mention_count }
        """
        title = article.get("title", "")
        title_lower = title.lower()
        age_hours = article.get("age_hours", 24)
        mention_count = article.get("mention_count", 0)
        source = (article.get("source") or "").lower()

        # 1. Cheap local pre-score BEFORE LLM
        prescore = 0
        
        # recency
        if age_hours <= 2: prescore += 20
        elif age_hours <= 6: prescore += 15
        elif age_hours <= 12: prescore += 10
        else: prescore += 5
            
        # keywords
        cat2_kws = ["war", "election", "ban", "crash", "lawsuit", "death"]
        cat1_kws = ["record", "shocking", "massive"]
        vip_kws = ["apple", "tesla", "google", "elon musk", "trump", "modi", "fifa"]
        
        if any(kw in title_lower for kw in cat2_kws): prescore += 8
        if any(kw in title_lower for kw in cat1_kws): prescore += 5
        if any(kw in title_lower for kw in vip_kws): prescore += 10
            
        # mention_count
        if mention_count >= 5: prescore += 10
        elif mention_count >= 3: prescore += 5
            
        # trusted source
        if "reuters" in source or "bbc" in source or "ap" in source:
            prescore += 5
            
        prescore = min(60, prescore)
        
        llm_result = None
        if use_llm:
            # 2. Call LLM for final enrichment
            system_prompt = """You are a viral content strategist who has studied 10 million social media posts.

Score this news article for viral potential on a scale of 0-100.

SCORING FACTORS:

- Recency: 0-20
  0-2 hr = 20
  2-6 hr = 15
  6-12 hr = 10
  >12 hr = 5

- Emotional intensity: 0-20
  rage / shock / joy / fear score highest

- Controversy level: 0-15
  debate-triggering / divisive topics

- Celebrity / brand involvement: 0-15

- Breaking / exclusive: 0-10

- Share trigger: 0-10
  likely to be forwarded

- Visual potential: 0-10
  easy to make striking thumbnail

OUTPUT FORMAT JSON ONLY:

{
 "viral_score": 0,
 "is_breaking": false,
 "emotion": "rage|shock|joy|fear|awe|sadness|excitement",
 "category_detected": "technology|politics|sports|finance|war|entertainment|science",
 "controversy": 0,
 "visual_difficulty": "easy|medium|hard",
 "score_breakdown": {
   "recency": 0,
   "emotion": 0,
   "controversy": 0,
   "celebrity": 0,
   "breaking": 0,
   "share_trigger": 0,
   "visual": 0
 }
}"""

            user_prompt = f"Title: {title}\nSource: {article.get('source')}\nAge: {age_hours} hours\nCategory: {article.get('category')}\nSummary: {article.get('summary')}"
            
            payload = {
                "model": self.ollama_model,
                "prompt": user_prompt,
                "system": system_prompt,
                "stream": False,
                "format": "json"
            }
            
            for attempt in range(2):
                try:
                    # Timeout requests after 8 sec
                    resp = requests.post(self.ollama_url, json=payload, timeout=8)
                    if resp.status_code == 200:
                        text = resp.json().get("response", "").strip()
                        if text.startswith("```json"): text = text[7:-3].strip()
                        elif text.startswith("```"): text = text[3:-3].strip()
                            
                        data = json.loads(text)
                        if "viral_score" in data:
                            llm_result = data
                            break
                except Exception:
                    pass
                if attempt == 0:
                    time.sleep(1)

        # 3. If LLM fails: Use fallback deterministic score
        if llm_result:
            result = llm_result
            llm_score = result.get("viral_score", prescore)
            score = int((prescore * 0.45) + (llm_score * 0.55))
        else:
            score = prescore
            result = {
                "viral_score": score,
                "is_breaking": any(kw in title_lower for kw in ["breaking", "urgent", "alert", "exclusive", "live", "war", "crash"]),
                "emotion": "neutral",
                "category_detected": article.get("category", "general"),
                "controversy": 0,
                "visual_difficulty": "medium",
                "score_breakdown": {
                    "recency": prescore,
                    "emotion": 0,
                    "controversy": 0,
                    "celebrity": 0,
                    "breaking": 0,
                    "share_trigger": 0,
                    "visual": 0
                }
            }

        score = max(0, min(100, score))
        if mention_count >= 5:
            score = min(100, score + 5)

        # 4. Category fallback logic
        cat_lower = result.get("category_detected", "").lower()
        if not cat_lower or cat_lower == "general":
            if any(w in title_lower for w in ["war", "conflict"]): result["category_detected"] = "war"
            elif any(w in title_lower for w in ["stock", "market", "inflation"]): result["category_detected"] = "finance"
            elif any(w in title_lower for w in ["apple", "google", "ai", "software"]): result["category_detected"] = "technology"
            elif any(w in title_lower for w in ["election", "parliament", "president"]): result["category_detected"] = "politics"
            elif any(w in title_lower for w in ["match", "fifa", "nba", "cricket"]): result["category_detected"] = "sports"

        # 5. Score decision rules
        if score >= 85: priority = 100
        elif score >= 70: priority = 50
        elif score >= 55: priority = 10
        elif score >= 40: priority = 1
        else: priority = 0
            
        result["priority_level"] = priority
        result["viral_score"] = int(score)
        
        return result

    def run(self):
        """Batch scores approved raw articles and updates the DB."""
        if not self.conn_string:
            print("No DATABASE_URL configured.")
            return

        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Fetch articles awaiting score
                cur.execute("SELECT * FROM articles WHERE status = 'approved' AND viral_score = 0 LIMIT 100")
                articles = cur.fetchall()
        except Exception as e:
            print(f"Error fetching articles: {e}")
            conn.rollback()
            conn.close()
            return
            
        metrics = {
            "scored": 0,
            "urgent": 0,
            "high": 0,
            "ignored": 0,
            "total_score": 0,
            "ai_scored": 0,
            "deterministic_only": 0,
            "total_mentions": 0
        }
        
        try:
            # Per-article transactions: one bad row cannot poison the entire batch
            with conn.cursor() as cur:
                for db_art in articles:
                    art_dict = dict(db_art)
                    art_id   = art_dict["id"]
                    age_hours = self._get_age_hours(art_dict.get("published_date"))
                    
                    headline = art_dict.get("headline", "")
                    category = art_dict.get("category", "")
                    
                    # --- Mention count (best-effort, isolated) ---
                    mention_count = 0
                    words = [w for w in headline.lower().split() if len(w) > 4]
                    if words:
                        like_clause = " OR ".join(["LOWER(headline) LIKE %s" for _ in words])
                        params = [f"%{w}%" for w in words]
                        cat_clause = "category_detected = %s" if category else "FALSE"
                        if category:
                            params.append(category)
                        try:
                            cur.execute(f"""
                                SELECT COUNT(*) FROM articles
                                WHERE ({like_clause} OR {cat_clause})
                                AND published_date >= NOW() - INTERVAL '12 hours'
                            """, tuple(params))
                            mention_count = cur.fetchone()[0]
                        except Exception:
                            conn.rollback()  # reset aborted state before next query
                            mention_count = 0

                    metrics["total_mentions"] += mention_count

                    input_art = {
                        "id": art_id,
                        "title": headline,
                        "source": art_dict.get("source", ""),
                        "age_hours": age_hours,
                        "summary": art_dict.get("full_text", "")[:1000] if art_dict.get("full_text") else "",
                        "category": category,
                        "mention_count": mention_count
                    }

                    use_llm = metrics["ai_scored"] < 30
                    result = self.score_article(input_art, use_llm=use_llm)

                    if use_llm: metrics["ai_scored"] += 1
                    else: metrics["deterministic_only"] += 1

                    priority = result.get("priority_level", 0)
                    score    = result.get("viral_score", 0)

                    metrics["scored"]      += 1
                    metrics["total_score"] += score

                    if priority == 100: metrics["urgent"] += 1
                    elif priority == 50: metrics["high"] += 1
                    elif priority == 0:  metrics["ignored"] += 1

                    new_status = 'ignored'
                    if score >= 55:   new_status = 'ranked'
                    elif score >= 40: new_status = 'low_priority'

                    # --- Per-article commit/rollback ---
                    try:
                        cur.execute("""
                            UPDATE articles
                            SET viral_score          = %s,
                                is_breaking          = %s,
                                emotion              = %s,
                                category_detected    = %s,
                                priority_level       = %s,
                                score_breakdown_json = %s,
                                status               = %s
                            WHERE id = %s
                        """, (
                            score,
                            result.get("is_breaking", False),
                            result.get("emotion", "neutral"),
                            result.get("category_detected", ""),
                            priority,
                            json.dumps(result.get("score_breakdown", {})),
                            new_status,
                            art_id
                        ))
                        conn.commit()   # ← commit every article independently
                    except Exception as inner_e:
                        print(f"[VIRAL] article {art_id} failed: {inner_e}")
                        conn.rollback() # ← reset so the NEXT article can proceed

        finally:
            conn.close()
            
        avg_score = int(metrics["total_score"] / max(1, metrics["scored"]))
        avg_mentions = round(metrics["total_mentions"] / max(1, metrics["scored"]), 1)
        
        print(f"[VIRAL] avg_mentions={avg_mentions}")
        print(f"[VIRAL] scored={metrics['scored']}")
        print(f"[VIRAL] ai_scored={metrics['ai_scored']}")
        print(f"[VIRAL] deterministic_only={metrics['deterministic_only']}")
        print(f"[VIRAL] urgent={metrics['urgent']}")
        print(f"[VIRAL] high={metrics['high']}")
        print(f"[VIRAL] ignored={metrics['ignored']}")
        print(f"[VIRAL] avg_score={avg_score}")

    # --- Legacy wrappers to maintain pipeline compatibility ---
    def score(self, article_dict: dict) -> int:
        """Legacy compatibility wrapper."""
        return self.score_article({
            "title": article_dict.get("headline", ""),
            "source": article_dict.get("source", ""),
            "age_hours": self._get_age_hours(article_dict.get("published_date")),
            "summary": article_dict.get("full_text", "")[:1000] if article_dict.get("full_text") else "",
            "category": article_dict.get("category", ""),
            "mention_count": 0
        }).get("viral_score", 0)
        
    def is_breaking(self, headline: str) -> bool:
        """Legacy compatibility wrapper."""
        if not headline: return False
        urgent_words = ['breaking', 'urgent', 'alert', 'exclusive', 'live']
        return any(w in headline.lower() for w in urgent_words)

if __name__ == "__main__":
    engine = ViralScoreEngine()
    engine.run()
