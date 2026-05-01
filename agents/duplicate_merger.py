import os
import time
import json
import datetime
import requests
import psycopg2
import psycopg2.extras
import re

class DuplicateMerger:
    """Semantic Deduplication Engine."""
    
    AGENT_NAME = "duplicate_merger"
    
    def __init__(self):
        self.conn_string = os.environ.get("DATABASE_URL")
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "mistral")

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)
        
    def _similar(self, a, b):
        sa = set(a.lower().split())
        sb = set(b.lower().split())
        return len(sa & sb) / max(1, len(sa | sb))

    def _extract_entities(self, text):
        words = text.split()
        entities = set()
        ignore = {"The", "A", "An", "Breaking", "Monday", "Tuesday", "Today", "Live"}
        for w in words:
            clean_w = re.sub(r'[^a-zA-Z]', '', w)
            if clean_w and clean_w[0].isupper() and clean_w not in ignore:
                entities.add(clean_w.lower())
        return entities

    def _get_locations(self, text):
        geos = {"india", "gujarat", "kerala", "usa", "london", "uk", "america", "europe", "china", "russia", "japan", "france", "germany", "australia", "canada", "delhi", "mumbai", "texas", "california", "new york", "pakistan", "israel", "gaza", "ukraine"}
        words = set(re.sub(r'[^a-zA-Z\s]', '', text.lower()).split())
        return words & geos

    def _has_same_action(self, text1, text2):
        actions = {"launches", "bans", "wins", "dies", "crashes", "acquires", "announces", "sues", "arrests", "resigns"}
        w1 = set(re.sub(r'[^a-zA-Z\s]', '', text1.lower()).split())
        w2 = set(re.sub(r'[^a-zA-Z\s]', '', text2.lower()).split())
        act1 = w1 & actions
        act2 = w2 & actions
        if act1 and act2 and (act1 & act2):
            return True
        return False

    def check_duplicate(self, candidate_article: dict, approved_articles: list, use_llm: bool = True) -> dict:
        """
        Input: 
        candidate_article = { id, title, source, published_date, category, summary, url }
        """
        # FAST LOCAL PREFILTER BEFORE LLM
        candidate_title = candidate_article.get("title", "")
        candidate_url = candidate_article.get("url", "")
        cand_time = candidate_article.get("published_date")
        
        likely_matches = []
        
        for approved in approved_articles:
            match_score = 0
            reason = ""
            
            # A. Exact URL duplicate
            if candidate_url and candidate_url == approved.get("url"):
                match_score = 100
                reason = "Exact URL match"
                
            # B. Token overlap headline similarity > 0.70
            app_title = approved.get("title", "")
            sim = self._similar(candidate_title, app_title)
            if sim > 0.70 and match_score == 0:
                match_score = int(sim * 100)
                reason = "Headline similarity > 0.70"
                
            # C. Same named entities + same action words
            # D. Published within 6 hours
            if match_score == 0:
                cand_entities = self._extract_entities(candidate_title)
                app_entities = self._extract_entities(app_title)
                shared_entities = cand_entities & app_entities
                
                time_close = True
                app_time = approved.get("published_date")
                if cand_time and app_time:
                    if isinstance(cand_time, str):
                        try: cand_time = datetime.datetime.fromisoformat(cand_time.replace("Z", "+00:00"))
                        except: pass
                    if isinstance(app_time, str):
                        try: app_time = datetime.datetime.fromisoformat(app_time.replace("Z", "+00:00"))
                        except: pass
                        
                    if isinstance(cand_time, datetime.datetime) and isinstance(app_time, datetime.datetime):
                        diff = abs((cand_time - app_time).total_seconds()) / 3600
                        if diff > 6:
                            time_close = False
                            
                if shared_entities and time_close:
                    if self._has_same_action(candidate_title, app_title):
                        match_score = 75
                        reason = "Same entity + same action + close time"
                        
            if match_score > 0:
                # Add geography protection
                cand_locs = self._get_locations(candidate_title)
                app_locs = self._get_locations(app_title)
                if cand_locs and app_locs and not (cand_locs & app_locs):
                    match_score -= 40
                    reason += " (Penalty: diff locations)"
                    
                if match_score > 50:
                    likely_matches.append({
                        "approved": approved,
                        "score": match_score,
                        "reason": reason
                    })
        
        # If no likely duplicate -> skip LLM
        if not likely_matches:
            return {
                "is_duplicate": False,
                "duplicate_of_id": None,
                "confidence": 0,
                "reason": "Passed local prefilter",
                "llm_used": False
            }
            
        likely_matches.sort(key=lambda x: x["score"], reverse=True)
        best_match = likely_matches[0]
        likely_duplicate_of = best_match["approved"]
        local_reason = best_match["reason"]
            
        if not use_llm:
            return {
                "is_duplicate": True,
                "duplicate_of_id": likely_duplicate_of["id"],
                "confidence": 80,
                "reason": f"Fallback to local rule: {local_reason}",
                "llm_used": False
            }

        # LLM USAGE
        system_prompt = """You are a duplicate detection system for a news aggregator.

You receive a candidate article and a list of already-approved articles.

Determine if the candidate is a duplicate or near-duplicate.

DUPLICATE CRITERIA:
- Same event, even if different headline wording
- Same entity (person/company/place) + same action within 6 hours
- Reworded Reuters/AP wire story

NOT DUPLICATE:
- Follow-up with materially new information
- Different angle on same topic
- Same topic but different geography

OUTPUT JSON ONLY:

{
 "is_duplicate": true,
 "duplicate_of_id": "123",
 "confidence": 94,
 "reason": "Same Apple product launch event"
}"""
        
        user_prompt = f"CANDIDATE ARTICLE:\nID: {candidate_article.get('id')}\nTitle: {candidate_title}\nSource: {candidate_article.get('source')}\nSummary: {candidate_article.get('summary')}\n\n"
        user_prompt += f"ALREADY APPROVED ARTICLE:\nID: {likely_duplicate_of.get('id')}\nTitle: {likely_duplicate_of.get('title')}\nSource: {likely_duplicate_of.get('source')}\nSummary: {likely_duplicate_of.get('summary')}\n"

        payload = {
            "model": self.ollama_model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "format": "json"
        }
        
        llm_result = None
        for attempt in range(2):
            try:
                resp = requests.post(self.ollama_url, json=payload, timeout=8)
                if resp.status_code == 200:
                    text = resp.json().get("response", "").strip()
                    if text.startswith("```json"): text = text[7:-3].strip()
                    elif text.startswith("```"): text = text[3:-3].strip()
                        
                    data = json.loads(text)
                    if "is_duplicate" in data:
                        llm_result = data
                        break
            except Exception:
                pass
            if attempt == 0:
                time.sleep(1)

        if llm_result:
            dup_id = str(llm_result.get("duplicate_of_id", likely_duplicate_of["id"]))
            # Provide fallback id if LLM hallucinated
            if dup_id == "123":
                dup_id = str(likely_duplicate_of["id"])
                
            return {
                "is_duplicate": llm_result.get("is_duplicate", True),
                "duplicate_of_id": dup_id,
                "confidence": llm_result.get("confidence", 90),
                "reason": llm_result.get("reason", "LLM confirmed"),
                "llm_used": True
            }
        else:
            return {
                "is_duplicate": True,
                "duplicate_of_id": likely_duplicate_of["id"],
                "confidence": 80,
                "reason": f"Fallback to local rule: {local_reason}",
                "llm_used": True
            }

    def run(self):
        """
        Runs the semantic deduplication pipeline.
        Returns the number of duplicates found.
        """
        if not self.conn_string:
            print("No DATABASE_URL configured.")
            return 0
            
        db_conn = self._get_conn()
        metrics = {
            "checked": 0,
            "duplicates": 0,
            "unique": 0,
            "llm_used": 0,
            "saved_processing": 0,
            "total_conf": 0
        }
        
        try:
            with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Fetch candidates (articles that just passed Viral Score Engine with status='ranked')
                cur.execute("SELECT * FROM articles WHERE status = 'ranked' LIMIT 50")
                candidates = cur.fetchall()
                
                if not candidates:
                    return 0
                    
                # Only compare candidate against articles from last 24h
                cur.execute("""
                    SELECT * FROM articles 
                    WHERE status IN ('approved', 'approved_unique', 'queued', 'published')
                    AND created_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY created_at DESC
                    LIMIT 150
                """)
                comparison_set = cur.fetchall()
        except Exception as e:
            print(f"Error fetching articles for dedup: {e}")
            db_conn.rollback()
            db_conn.close()
            return 0
            
        comparison_dicts = []
        for c in comparison_set:
            comparison_dicts.append({
                "id": str(c["id"]),
                "title": c.get("headline", ""),
                "source": c.get("source", ""),
                "published_date": c.get("published_date"),
                "category": c.get("category", ""),
                "summary": c.get("full_text", "")[:500] if c.get("full_text") else "",
                "url": c.get("url", "")
            })

        # Per-article transactions: one failure cannot poison the batch or downstream agents
        cur = db_conn.cursor()
        try:
            for db_art in candidates:
                art_dict = dict(db_art)
                cand_id_str = str(art_dict["id"])

                input_art = {
                    "id": cand_id_str,
                    "title": art_dict.get("headline", ""),
                    "source": art_dict.get("source", ""),
                    "published_date": art_dict.get("published_date"),
                    "category": art_dict.get("category", ""),
                    "summary": art_dict.get("full_text", "")[:500] if art_dict.get("full_text") else "",
                    "url": art_dict.get("url", "")
                }

                valid_comps = [c for c in comparison_dicts if c["id"] != cand_id_str]

                use_llm = metrics["llm_used"] < 20
                result = self.check_duplicate(input_art, valid_comps, use_llm=use_llm)

                if result.get("llm_used"):
                    metrics["llm_used"] += 1

                metrics["checked"] += 1

                if result.get("is_duplicate"):
                    metrics["duplicates"] += 1
                    metrics["saved_processing"] += 1
                    metrics["total_conf"] += result.get("confidence", 0)
                    new_status = 'duplicate'
                    dup_id = result.get("duplicate_of_id")
                    try:
                        dup_id_int = int(dup_id)
                    except Exception:
                        dup_id_int = None
                else:
                    metrics["unique"] += 1
                    new_status = 'approved_unique'
                    dup_id_int = None
                    comparison_dicts.append(input_art)

                # Per-article commit/rollback
                try:
                    cur.execute("""
                        UPDATE articles
                        SET status              = %s,
                            duplicate_of_id     = %s,
                            duplicate_confidence = %s,
                            duplicate_reason    = %s
                        WHERE id = %s
                    """, (
                        new_status,
                        dup_id_int,
                        result.get("confidence", 0),
                        result.get("reason", ""),
                        art_dict["id"]
                    ))
                    db_conn.commit()  # ← commit each article independently
                except Exception as e:
                    print(f"[DEDUP] article {cand_id_str} failed: {e}")
                    db_conn.rollback()  # ← reset state so next article can proceed
        finally:
            cur.close()

        avg_conf = int(metrics["total_conf"] / max(1, metrics["duplicates"]))

        print(f"[DEDUP] avg_confidence={avg_conf}")
        print(f"[DEDUP] false_positive_protection=enabled")
        print(f"[DEDUP] checked={metrics['checked']}")
        print(f"[DEDUP] duplicates={metrics['duplicates']}")
        print(f"[DEDUP] unique={metrics['unique']}")
        print(f"[DEDUP] forwarded_to_visual={metrics['unique']}")
        print(f"[DEDUP] llm_used={metrics['llm_used']}")
        print(f"[DEDUP] saved_processing={metrics['saved_processing']}")

        db_conn.close()
        return metrics["duplicates"]

if __name__ == "__main__":
    conn_string = os.getenv("DATABASE_URL", "host=localhost port=5432 dbname=news_system user=postgres")
    try:
        conn = psycopg2.connect(conn_string)
        merger = DuplicateMerger()
        merger.run(conn)
        conn.close()
    except Exception as e:
        print(f"Error executing DuplicateMerger: {e}")
