import os
import json
import requests
import urllib.parse
from io import BytesIO
from PIL import Image

class SmartImageFetcher:
    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.pexels_key = os.environ.get("PEXELS_API_KEY", "")

    def _crop_center(self, img, target_w, target_h):
        scale = max(target_w / img.width, target_h / img.height)
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        
        # Use Image.Resampling.LANCZOS for PIL 10+, fallback to Image.LANCZOS for older versions
        resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
        img = img.resize((new_w, new_h), resample_filter)
        
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return img.crop((left, top, left + target_w, top + target_h))

    def _analyse_headline(self, headline, category):
        try:
            prompt = f"Headline: {headline}\nCategory: {category}"
            system_prompt = """You are a news image analyst. Analyse the headline
and return ONLY valid JSON with these exact keys:
- type: one of 'movie', 'person', 'multi_person', 'sports', 'event', 'place', 'general'
- entities: list of specific named entities (people, teams, movies, places)
- search_query: a 4-6 word Google Images search that finds REAL NEWS PHOTOS
  not stock photos. Include year (2025 or 2026), real names, and action words.
  Examples:
  'NBA playoffs 2026 basketball game action'
  'Donald Trump Narendra Modi meeting 2026'
  'MacBook laptop Apple product 2026'
  'Providence Friars basketball coach 2026'
- wikipedia_subjects: list of real famous people names for Wikipedia lookup
  (only if the headline is specifically ABOUT that named person)

Rules for search_query:
- Always include the year 2026 to get recent photos
- Use real names of teams, people, places from the headline
- Add 'news photo' at the end for non-person queries
- For sports: include team name + sport + 'game'
- For business/tech: include company/product name + 'official'
- NEVER use abstract words like 'concept', 'idea', 'future', 'coming soon'

Return ONLY the JSON object, no other text."""
            
            resp = requests.post(
                self.ollama_url,
                json={
                    "model": "mistral",
                    "stream": False,
                    "system": system_prompt,
                    "prompt": prompt
                },
                timeout=15
            )
            resp.raise_for_status()
            text_resp = resp.json().get("response", "").strip()
            
            # Clean up potential markdown formatting around JSON
            if text_resp.startswith("```json"):
                text_resp = text_resp[7:]
            if text_resp.startswith("```"):
                text_resp = text_resp[3:]
            if text_resp.endswith("```"):
                text_resp = text_resp[:-3]
                
            return json.loads(text_resp.strip())
        except Exception as e:
            print(f"SmartImageFetcher analysis error: {e}")
            return {
                "type": "general", 
                "entities": [], 
                "search_query": category or "news",
                "wikipedia_subjects": []
            }

    def _fetch_wikipedia_image(self, subject_name):
        try:
            encoded_name = urllib.parse.quote(subject_name.replace(' ', '_'))
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_name}"
            
            headers = {
                "User-Agent": "NewsWeaverBot/1.0 (Contact: dev@example.com; project: news-automation)"
            }
            resp = requests.get(url, headers=headers, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            
            # Try original image first, then thumbnail
            img_url = None
            if "originalimage" in data and "source" in data["originalimage"]:
                img_url = data["originalimage"]["source"]
            elif "thumbnail" in data and "source" in data["thumbnail"]:
                img_url = data["thumbnail"]["source"]
                
            if img_url:
                # CRITICAL: upload.wikimedia.org ALSO requires the same User-Agent
                img_resp = requests.get(img_url, headers=headers, timeout=8)
                img_resp.raise_for_status()
                return Image.open(BytesIO(img_resp.content)).convert("RGB")
        except Exception as e:
            print(f"Wikipedia fetch error for {subject_name}: {e}")
        return None

    def _fetch_google_image(self, search_query, img_type="general"):
        # We replaced Google with DuckDuckGo to bypass GCP 403 API permission bugs
        # DuckDuckGo is 100% free, has no quota, and requires no API keys.
        
        # Only use web search for specific entity types
        if img_type not in ("movie", "person", "event", "place", "sports"):
            print(f"Skipping DuckDuckGo Image fetch for type '{img_type}'.")
            return None
            
        try:
            from duckduckgo_search import DDGS
            ddgs = DDGS()
            items = ddgs.images(search_query, max_results=5)
            
            SKIP_KEYWORDS = [
                'shutterstock', 'istockphoto', 'gettyimages', 'alamy',
                'dreamstime', 'depositphotos', 'stock', 'clipart',
                'illustration', 'vector', 'icon', 'logo', 'thumbnail'
            ]
            
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            
            for item in items:
                img_url = item.get("image")
                if img_url:
                    if any(kw in img_url.lower() for kw in SKIP_KEYWORDS):
                        continue
                        
                    try:
                        img_resp = requests.get(img_url, headers=headers, timeout=8)
                        img_resp.raise_for_status()
                        return Image.open(BytesIO(img_resp.content)).convert("RGB")
                    except Exception:
                        continue
                        
        except Exception as e:
            print(f"DuckDuckGo Image fetch error: {e}")
        return None

    def _fetch_pexels_image(self, query):
        if not self.pexels_key:
            return None
            
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=1"
            headers = {"Authorization": self.pexels_key}
            
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("photos"):
                photo = data["photos"][0]
                img_url = photo["src"]["landscape"]
                
                img_resp = requests.get(img_url, timeout=10)
                img_resp.raise_for_status()
                return Image.open(BytesIO(img_resp.content)).convert("RGB")
        except Exception as e:
            print(f"Pexels fetch error: {e}")
        return None

    def _compose_multi_entity(self, images_list, target_size):
        from PIL import ImageDraw
        target_w, target_h = target_size
        count = len(images_list)
        
        canvas = Image.new("RGB", target_size, (255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        
        if count == 2:
            w_each = target_w // 2
            img1 = self._crop_center(images_list[0], w_each, target_h)
            img2 = self._crop_center(images_list[1], w_each, target_h)
            canvas.paste(img1, (0, 0))
            canvas.paste(img2, (w_each, 0))
            draw.line([(w_each, 0), (w_each, target_h)], fill=(255, 255, 255), width=3)
            
        elif count == 3:
            w_each = target_w // 3
            img1 = self._crop_center(images_list[0], w_each, target_h)
            img2 = self._crop_center(images_list[1], w_each, target_h)
            img3 = self._crop_center(images_list[2], w_each, target_h)
            canvas.paste(img1, (0, 0))
            canvas.paste(img2, (w_each, 0))
            canvas.paste(img3, (w_each * 2, 0))
            draw.line([(w_each, 0), (w_each, target_h)], fill=(255, 255, 255), width=3)
            draw.line([(w_each * 2, 0), (w_each * 2, target_h)], fill=(255, 255, 255), width=3)
            
        elif count >= 4:
            w_each = target_w // 2
            h_each = target_h // 2
            img1 = self._crop_center(images_list[0], w_each, h_each)
            img2 = self._crop_center(images_list[1], w_each, h_each)
            img3 = self._crop_center(images_list[2], w_each, h_each)
            img4 = self._crop_center(images_list[3], w_each, h_each)
            canvas.paste(img1, (0, 0))
            canvas.paste(img2, (w_each, 0))
            canvas.paste(img3, (0, h_each))
            canvas.paste(img4, (w_each, h_each))
            draw.line([(w_each, 0), (w_each, target_h)], fill=(255, 255, 255), width=3)
            draw.line([(0, h_each), (target_w, h_each)], fill=(255, 255, 255), width=3)
            
        return canvas

    def get_best_image(self, headline, category, target_size):
        try:
            analysis = self._analyse_headline(headline, category)
            img_type = analysis.get("type", "general")
            subjects = analysis.get("wikipedia_subjects", [])
            query = analysis.get("search_query", category or "news")
            
            img = None
            
            if img_type == "multi_person" and len(subjects) >= 2:
                images = []
                for subject in subjects:
                    subj_img = self._fetch_wikipedia_image(subject)
                    if subj_img:
                        images.append(subj_img)
                        if len(images) == 4: # Max 4 supported
                            break
                            
                if len(images) >= 2:
                    return self._compose_multi_entity(images, target_size)
                elif len(images) == 1:
                    img = images[0]
                    
            elif img_type == "person" and subjects:
                img = self._fetch_wikipedia_image(subjects[0])
                
            if not img and (img_type in ("movie", "event", "place", "person", "sports") or not subjects):
                img = self._fetch_google_image(query, img_type)
                
            if not img:
                img = self._fetch_pexels_image(query)
                
            if img:
                return self._crop_center(img, target_size[0], target_size[1])
                
            return None
            
        except Exception as e:
            print(f"SmartImageFetcher global error: {e}")
            return None
