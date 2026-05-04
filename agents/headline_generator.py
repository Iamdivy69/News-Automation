import os
import json
import time
import psycopg2
import traceback
import google.genai as genai
from google.genai import types as genai_types

class HeadlineGenerator:
    AGENT_NAME = "headline_generator"

    def __init__(self):
        self.conn_string = os.environ.get("DATABASE_URL")
        self._gemini_key = os.environ.get("GEMINI_API_KEY")
        self._client = genai.Client(api_key=self._gemini_key) if self._gemini_key else None

    def _get_conn(self):
        if not self.conn_string:
            return None
        try:
            return psycopg2.connect(self.conn_string)
        except Exception:
            return None

    def _log_error(self, message: str, stack: str = ""):
        conn = self._get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO error_logs (agent, message, stack_trace) VALUES (%s, %s, %s)",
                    (self.AGENT_NAME, message, stack)
                )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    def generate(self, article: dict) -> dict:
        title = article.get("title", "")
        summary = article.get("summary", "")
        category = article.get("category", "")
        is_breaking = article.get("is_breaking", False)

        prompt = f"""
Article Title: {title}
Article Summary: {summary}
Category: {category}
Is Breaking: {is_breaking}
"""

        system_prompt = """
You are a tabloid headline writer for BOLD visual social media news cards.
Your headlines will be rendered in GIANT TYPE on a 1080x1080 image.
STRICT OUTPUT RULES:
1. headline: EXACTLY 4-6 WORDS. ALL CAPS. NO MORE.
Good: "9 KILLED IN DELHI BLAZE"
Good: "TRUMP BYPASSES CONGRESS ON WAR"
Bad: "GRETCHEN WALSH SETS 100M BUTTERFLY WORLD RECORD FOR THIRD TIME" (too long)
2. highlight_words: EXACTLY 2 words from the headline that carry maximum emotional impact.
These will be printed in RED. Choose action/impact words, not names.
Good: ["KILLED", "BLAZE"]
Good: ["BYPASSES", "WAR"]
Bad: ["GRETCHEN", "WALSH"] (names are weak highlights)
3. subtext: One sentence. Max 12 words. Plain case. Must add context not in headline.
Good: "Tragedy strikes Delhi building; child among nine victims."
Bad: "Gretchen Walsh breaks her own 100m butterfly world record for the third time." (too long)
4. tag: ONE of: breaking | sports | finance | politics | technology | world | india
OUTPUT: Valid JSON only. No markdown. No explanation. No extra text.
{
"headline": "EXACTLY 4-6 WORDS ALL CAPS",
"highlight_words": ["WORD1", "WORD2"],
"subtext": "One sentence max 12 words.",
"tag": "breaking"
}
"""
        
        fallback_headline = " ".join(str(title).split()[:8]).upper()
        highlight_fallback = [fallback_headline.split()[0]] if fallback_headline else []
        subtext_fallback = " ".join(str(summary or title).split()[:15])
        
        fallback = {
            "headline": fallback_headline,
            "highlight_words": highlight_fallback,
            "subtext": subtext_fallback,
            "tag": "breaking" if is_breaking else "world"
        }

        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not self._gemini_key or not self._client:
            self._log_error("GEMINI_API_KEY not found in environment. Using fallback.")
            return fallback

        full_prompt = f"{system_prompt.strip()}\n\n{prompt.strip()}"

        last_error = None
        last_stack = None

        for attempt in range(3):
            try:
                response = self._client.models.generate_content(
                    model='gemini-1.5-flash',
                    contents=full_prompt,
                )
                text = response.text.strip()
                
                # Cleanup possible markdown JSON formatting
                if text.startswith("```json"):
                    text = text[7:]
                elif text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                    
                text = text.strip()
                data = json.loads(text)
                
                # Validate keys
                required_keys = {"headline", "highlight_words", "subtext", "tag"}
                if not required_keys.issubset(data.keys()):
                    raise ValueError(f"Missing required JSON keys: {required_keys - data.keys()}")
                
                # Validate highlight_words
                if not isinstance(data["highlight_words"], list):
                    raise ValueError("highlight_words must be a list")
                
                # Enforce 6-word max on headline
                words = data['headline'].split()
                if len(words) > 6:
                    # Keep most impactful 6 words (drop filler words)
                    FILLERS = {'THE', 'A', 'AN', 'FOR', 'OF', 'IN', 'ON', 'AT', 'TO', 'AND', 'AS', 'IS', 'ARE', 'BY'}
                    core_words = [w for w in words if w.upper() not in FILLERS]
                    if len(core_words) >= 4:
                        data['headline'] = ' '.join(core_words[:6])
                    else:
                        data['headline'] = ' '.join(words[:6])
                
                # Enforce highlight_words exist in headline
                headline_words = set(data['headline'].upper().split())
                data['highlight_words'] = [
                    w for w in data['highlight_words']
                    if w.upper() in headline_words
                ]
                if not data['highlight_words'] and data['headline'].split():
                    # Auto-pick: first non-filler word
                    FILLERS = {'THE', 'A', 'AN', 'FOR', 'OF', 'IN', 'ON', 'AT', 'TO', 'AND'}
                    for w in data['headline'].split():
                        if w.upper() not in FILLERS:
                            data['highlight_words'] = [w]
                            break
                            
                data['headline'] = data['headline'].upper()
                return data

            except Exception as e:
                last_error = str(e)
                last_stack = traceback.format_exc()
                
            time.sleep(2)

        # If all fail
        self._log_error(f"Failed to generate headline after 3 attempts. Last error: {last_error}", last_stack)
        return fallback

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    agent = HeadlineGenerator()
    article_test = {
        "title": "Local Startup Raises 50M to Clean the Ocean",
        "summary": "A new oceanic technology company has secured massive funding to deploy their drone fleet in the Pacific.",
        "category": "technology",
        "is_breaking": False
    }
    print(json.dumps(agent.generate(article_test), indent=2))
