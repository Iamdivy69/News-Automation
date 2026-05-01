import os
import requests
import psycopg2
import psycopg2.extras
import traceback
import json
from time import sleep
import google.genai as genai
from config.branding_layer import BrandingLayer

class SummarisationAgent:
    """Agent that reads top30_selected articles and generates social media summaries."""
    
    AGENT_NAME = "summarisation"
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    OLLAMA_MODEL = "mistral"

    def __init__(self):
        self.conn_string = os.environ.get("DATABASE_URL")
        if not self.conn_string:
            raise ValueError("DATABASE_URL environment variable is not set.")
        self.branding = BrandingLayer()
        self._gemini_key = os.environ.get("GEMINI_API_KEY")
        self._client = genai.Client(api_key=self._gemini_key) if self._gemini_key else None

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def _determine_tone(self, category: str, is_breaking: bool) -> str:
        if is_breaking:
            return "urgent"
        
        cat = (category or "").lower()
        mapping = {
            "technology": "enthusiastic",
            "business": "professional",
            "sports": "energetic",
            "health": "informative"
        }
        return mapping.get(cat, "neutral")

    def _quality_gate(self, text: str) -> bool:
        if not text or len(text) < 40:
            return False
        
        lower_text = text.lower()
        if 'as an ai' in lower_text or 'i cannot' in lower_text:
            return False
            
        return True

    def _generate(self, prompt: str, system: str) -> tuple[str | None, str]:
        payload = {
            "model": self.OLLAMA_MODEL,
            "prompt": prompt,
            "system": system,
            "stream": False
        }
        
        for attempt in range(3):
            try:
                resp = requests.post(self.OLLAMA_URL, json=payload, timeout=120)
                if resp.status_code == 200:
                    text = resp.json().get("response", "").strip()
                    text = text.strip('"').strip("'")
                    
                    if self._quality_gate(text):
                        return text, "ollama"
            except Exception as e:
                print(f"Ollama generation error: {e}")
            
            backoff = 2 ** (attempt + 1) # 2s, 4s, 8s
            sleep(backoff)
            
        if self._gemini_key and self._client:
            try:
                gemini_prompt = f"System Instruction: {system}\n\nTask: {prompt}"
                response = self._client.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=gemini_prompt,
                )
                text = response.text.strip().strip('"').strip("'")
                if self._quality_gate(text):
                    return text, "gemini"
            except Exception as e:
                print(f"Gemini fallback error: {e}")
                
        return None, "failed"

    def _generate_summaries(self, headline: str, full_text: str, tone: str) -> dict:
        safe_text = (full_text or "")[:4000]
        base_text = f"Headline: {headline}\n\nArticle: {safe_text}"
        
        sys_summary = "You are a news editor. Write a plain summary of the article in under 100 words. Do NOT wrap output in quotes."
        sys_twitter = f"You are a social media manager. Tone: {tone}. Write a Twitter post about the provided article. Max 240 chars. Must have a strong hook in the first 6 words. Do NOT wrap output in quotes."
        sys_linkedin = f"You are a professional networker. Tone: {tone}. Write a LinkedIn post about the provided article. Max 500 chars. Must start with a professional insight opening. Do NOT wrap output in quotes."
        sys_ig = f"You are an Instagram influencer. Tone: {tone}. Write an Instagram caption about the provided article. Max 150 chars. Make it highly visual and emotional. Do NOT wrap output in quotes."
        sys_fb = f"You are a community manager. Tone: {tone}. Write a Facebook post about the provided article. Output EXACTLY 3 bullet points, each starting with an emoji. Conversational style. Do NOT wrap output in quotes."
        sys_tags = "You are an SEO expert. Read the article and return EXACTLY 8 relevant hashtags separated by commas (e.g., #News,#Tech,...). Mix broad and niche tags. Do NOT output anything else."
        
        res = {}
        res["summary"], res["summary_src"] = self._generate(base_text, sys_summary)
        res["twitter"], res["twitter_src"] = self._generate(base_text, sys_twitter)
        res["linkedin"], res["linkedin_src"] = self._generate(base_text, sys_linkedin)
        res["ig"], res["ig_src"] = self._generate(base_text, sys_ig)
        res["fb"], res["fb_src"] = self._generate(base_text, sys_fb)
        res["tags"], res["tags_src"] = self._generate(base_text, sys_tags)
        
        return res

    def run(self) -> dict:
        conn = self._get_conn()
        metrics = {"processed": 0, "ollama_success": 0, "gemini_fallback": 0, "skipped": 0}
        
        articles = []
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    "SELECT id, headline, full_text, category, is_breaking "
                    "FROM articles WHERE top_30_selected = TRUE AND status = 'top30_selected' "
                    "ORDER BY viral_score DESC LIMIT 30"
                )
                articles = cur.fetchall()
        except Exception as e:
            print(f"Error fetching articles: {e}")
            conn.close()
            return metrics
                
        for article in articles:
            article_id = article["id"]
            try:
                headline = article["headline"] or ""
                full_text = article["full_text"]
                
                if not headline or len(headline) < 10:
                    metrics["skipped"] += 1
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO error_logs (agent, message) VALUES (%s, %s)",
                            (self.AGENT_NAME, f"Article {article_id} Skipped: Headline empty or < 10 chars")
                        )
                    conn.commit()
                    continue
                    
                if not full_text or len(full_text) < 50:
                    full_text = headline
                
                category = article["category"] or ""
                is_breaking = article["is_breaking"] or False
                
                tone = self._determine_tone(category, is_breaking)
                gens = self._generate_summaries(headline, full_text, tone)
                
                sources = [gens["summary_src"], gens["twitter_src"], gens["linkedin_src"], gens["ig_src"], gens["fb_src"], gens["tags_src"]]
                if "gemini" in sources:
                    metrics["gemini_fallback"] += 1
                else:
                    metrics["ollama_success"] += 1
                
                branded_summary = self.branding.brand_summary({
                    "twitter_text": gens["twitter"], 
                    "linkedin_text": gens["linkedin"], 
                    "instagram_caption": gens["ig"], 
                    "facebook_text": gens["fb"], 
                    "hashtags": gens["tags"]
                })
                
                captions = {
                    "twitter": branded_summary["twitter_text"],
                    "linkedin": branded_summary["linkedin_text"],
                    "instagram": branded_summary["instagram_caption"],
                    "facebook": branded_summary["facebook_text"],
                    "hashtags": branded_summary["hashtags"]
                }
                
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM articles WHERE id = %s", (article_id,))
                    if not cur.fetchone():
                        print(f"  [skipped] Article {article_id} was purged before summary could be saved.")
                        continue

                    cur.execute(
                        """
                        INSERT INTO summaries (article_id, twitter_text, linkedin_text, instagram_caption, facebook_text, hashtags, tone, is_branded)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                        ON CONFLICT (article_id) DO UPDATE SET
                            twitter_text = EXCLUDED.twitter_text,
                            linkedin_text = EXCLUDED.linkedin_text,
                            instagram_caption = EXCLUDED.instagram_caption,
                            facebook_text = EXCLUDED.facebook_text,
                            hashtags = EXCLUDED.hashtags,
                            tone = EXCLUDED.tone,
                            is_branded = EXCLUDED.is_branded
                        """,
                        (
                            article_id, 
                            branded_summary["twitter_text"], 
                            branded_summary["linkedin_text"], 
                            branded_summary["instagram_caption"], 
                            branded_summary["facebook_text"], 
                            branded_summary["hashtags"], 
                            tone
                        )
                    )
                    
                    cur.execute(
                        """
                        UPDATE articles SET 
                            summary = %s,
                            captions = %s,
                            status = 'summarised',
                            processing_stage = 'summarised',
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (gens["summary"], json.dumps(captions), article_id)
                    )
                
                conn.commit()
                metrics["processed"] += 1
                print(f"Successfully processed and summarised article ID {article_id}.")
                
            except Exception as e:
                conn.rollback()
                print(f"Error processing article ID {article_id}: {e}")
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO error_logs (agent, message, stack_trace) VALUES (%s, %s, %s)",
                            (self.AGENT_NAME, f"Article {article_id} Processing Error: {e}", traceback.format_exc())
                        )
                    conn.commit()
                except Exception as log_err:
                    print(f"Failed to log error to DB for article {article_id}: {log_err}")
        
        conn.close()
        print(f"[SUMM] processed={metrics['processed']} ollama_success={metrics['ollama_success']} gemini_fallback={metrics['gemini_fallback']} skipped={metrics['skipped']}")
        return metrics

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    agent = SummarisationAgent()
    print("SummarisationAgent started...")
    agent.run()
