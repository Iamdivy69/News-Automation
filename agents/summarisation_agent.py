import os
import requests
import psycopg2
import psycopg2.extras
import traceback
from time import sleep
from config.branding_layer import BrandingLayer

class SummarisationAgent:
    """Agent that reads approved articles and uses Ollama local inference to generate social media summaries."""
    
    AGENT_NAME = "summarisation"
    OLLAMA_URL = "http://localhost:11434/api/generate"
    OLLAMA_MODEL = "mistral"

    def __init__(self):
        self.conn_string = os.environ.get("DATABASE_URL")
        if not self.conn_string:
            raise ValueError("DATABASE_URL environment variable is not set.")
        self.branding = BrandingLayer()

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def _determine_tone(self, category: str, is_breaking: bool) -> str:
        """Determines the requested tone based on the category or breaking status."""
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
        """Returns True if the output meets minimum quality criteria, otherwise False."""
        if not text or len(text) < 40:
            return False
        
        lower_text = text.lower()
        if 'as an ai' in lower_text or 'i cannot' in lower_text:
            return False
            
        return True

    def _generate(self, prompt: str, system: str) -> str | None:
        """Pings Ollama with 1 retry logic and a strict quality gate."""
        payload = {
            "model": self.OLLAMA_MODEL,
            "prompt": prompt,
            "system": system,
            "stream": False
        }
        
        for attempt in range(2):  # 1 initial + 1 retry
            try:
                resp = requests.post(self.OLLAMA_URL, json=payload, timeout=120)
                if resp.status_code == 200:
                    text = resp.json().get("response", "").strip()
                    # Strip any generic surrounding quotes sometimes thrown by Mistral
                    text = text.strip('"').strip("'")
                    
                    if self._quality_gate(text):
                        return text
            except Exception as e:
                print(f"Ollama generation error: {e}")
            
            # Wait briefly before retrying
            if attempt == 0:
                sleep(2)
                
        return None

    def _generate_summaries(self, headline: str, full_text: str, tone: str) -> tuple:
        """Generates all 5 required texts serially."""
        # Truncate full text to ensure we don't blow out the context window
        safe_text = (full_text or "")[:4000]
        base_text = f"Headline: {headline}\n\nArticle: {safe_text}"
        
        # Twitter
        sys_twitter = f"You are a social media manager. Tone: {tone}. Write a Twitter post about the provided article. Max 240 chars. Must have a strong hook in the first 6 words. Do NOT wrap output in quotes."
        twitter = self._generate(base_text, sys_twitter)
        
        # LinkedIn
        sys_linkedin = f"You are a professional networker. Tone: {tone}. Write a LinkedIn post about the provided article. Max 500 chars. Must start with a professional insight opening. Do NOT wrap output in quotes."
        linkedin = self._generate(base_text, sys_linkedin)
        
        # Instagram 
        sys_ig = f"You are an Instagram influencer. Tone: {tone}. Write an Instagram caption about the provided article. Max 150 chars. Make it highly visual and emotional. Do NOT wrap output in quotes."
        ig = self._generate(base_text, sys_ig)
        
        # Facebook
        sys_fb = f"You are a community manager. Tone: {tone}. Write a Facebook post about the provided article. Output EXACTLY 3 bullet points, each starting with an emoji. Conversational style. Do NOT wrap output in quotes."
        fb = self._generate(base_text, sys_fb)
        
        # Hashtags
        sys_tags = "You are an SEO expert. Read the article and return EXACTLY 8 relevant hashtags separated by commas (e.g., #News,#Tech,...). Mix broad and niche tags. Do NOT output anything else."
        tags = self._generate(base_text, sys_tags)
        
        return twitter, linkedin, ig, fb, tags

    def run(self) -> int:
        """Main execution flow: Process approved articles in PostgreSQL."""
        conn = self._get_conn()
        processed_count = 0
        
        # 1) Query PostgreSQL for articles with status='approved'
        articles = []
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(
                    "SELECT id, headline, full_text, category, is_breaking "
                    "FROM articles WHERE status = 'approved' "
                    "ORDER BY viral_score DESC LIMIT 50"
                )
                articles = cur.fetchall()
        except Exception as e:
            print(f"Error fetching articles: {e}")
            conn.close()
            return 0
                
        for article in articles:
            article_id = article["id"]
            try:
                headline = article["headline"] or ""
                full_text = article["full_text"] or ""
                category = article["category"] or ""
                is_breaking = article["is_breaking"] or False
                
                # 2) Determine tone
                tone = self._determine_tone(category, is_breaking)
                
                # 3) & 4) Make requests & quality gate
                twitter, linkedin, ig, fb, tags = self._generate_summaries(headline, full_text, tone)
                
                branded_summary = self.branding.brand_summary({
                    "twitter_text": twitter, 
                    "linkedin_text": linkedin, 
                    "instagram_caption": ig, 
                    "facebook_text": fb, 
                    "hashtags": tags
                })
                
                # Use a fresh cursor per transaction
                with conn.cursor() as cur:
                    # 5) Save outputs to summaries table
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
                    
                    # 6) Update article status
                    cur.execute("UPDATE articles SET status = 'summarised' WHERE id = %s", (article_id,))
                
                conn.commit()
                processed_count += 1
                print(f"Successfully processed and summarised article ID {article_id}.")
                
            except Exception as e:
                conn.rollback()
                print(f"Error processing article ID {article_id}: {e}")
                try:
                    # Log error back to the database
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO error_logs (agent, message, stack_trace) VALUES (%s, %s, %s)",
                            (self.AGENT_NAME, f"Article {article_id} Processing Error: {e}", traceback.format_exc())
                        )
                    conn.commit()
                except Exception as log_err:
                    print(f"Failed to log error to DB for article {article_id}: {log_err}")
        
        conn.close()
        return processed_count
            
        # 7) Return count
        return processed_count

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    agent = SummarisationAgent()
    print("SummarisationAgent started...")
    count = agent.run()
    print(f"Finished. Total articles summarised: {count}")
