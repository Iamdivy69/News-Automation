import os
import json
import shutil
import textwrap
import requests
import time
from io import BytesIO
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import urllib.parse
import psycopg2
import psycopg2.extras

class VisualGenerationAgent:
    AGENT_NAME = "visual_generator"
    
    CATEGORY_COLORS = {
        "technology": "#0D47A1",
        "business":   "#1B5E20",
        "sports":     "#4A148C",
        "health":     "#880E4F",
        "science":    "#E65100",
        "india":      "#B71C1C",
        "world":      "#004D40",
    }

    def __init__(self, config_path=None):
        self.conn_string = os.environ.get("DATABASE_URL")
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', 'config', 'brand_config.json'
            )
        config_path = os.path.normpath(config_path)
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {"brand_name": "Synthetix News", "tagline": "Real-time updates", "accent_color": "#E53935"}
            
        self.project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..')
        )
        today = datetime.now().strftime('%Y-%m-%d')
        self.images_dir = os.path.join(self.project_root, 'images', today)
        os.makedirs(self.images_dir, exist_ok=True)
        
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "mistral")

    def _hex_to_rgb(self, hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        
    def _load_font(self, path_list: list, size: int):
        for font_path in path_list:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size=size)
                except Exception:
                    continue
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def _get_font(self, size):
        font_candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
        return self._load_font(font_candidates, size)

    def _get_visual_concept(self, article):
        # FAST LOCAL CATEGORY FALLBACK base
        fallback = {
            "entities": {"people": [], "companies": [], "places": [], "event_type": "news"},
            "visual_scene": "breaking news event",
            "mood": "urgent",
            "camera": "wide shot",
            "style": "photorealistic",
            "lighting": "dramatic",
            "color_palette": "muted",
            "dalle_prompt": "",
            "pexels_fallback": "breaking news event"
        }
        category = (article.get("category") or "").lower()
        if "tech" in category: fallback["pexels_fallback"] = "futuristic product launch"
        elif "politic" in category: fallback["pexels_fallback"] = "podium parliament"
        elif "financ" in category or "stock" in category: fallback["pexels_fallback"] = "stock market office"
        elif "sport" in category: fallback["pexels_fallback"] = "stadium crowd"
        elif "war" in category: fallback["pexels_fallback"] = "command room world map"
        elif "scienc" in category: fallback["pexels_fallback"] = "lab discovery"
        elif "weather" in category: fallback["pexels_fallback"] = "storm satellite"

        system_prompt = """You are a world-class creative director for viral news media.

Your job is to analyze a news headline and extract a precise visual concept for image generation.

RULES:
1. Identify named entities: people, companies, places, events
2. Determine PRIMARY visual scene
3. Choose mood: urgent | celebratory | somber | shocking | professional | dramatic
4. Choose camera: aerial | close-up | wide shot | portrait | documentary | cinematic
5. NEVER use real faces. Use silhouettes, hands, buildings, objects, environments.
6. NEVER include text or logos.
7. Match emotional tone.

CATEGORY TEMPLATES:
Technology: product on minimalist stage, LED lighting, futuristic
Politics: empty podium, parliament hall
Finance: trading floor, charts screens
Sports: stadium action, crowd energy
War: command room, map room, red urgent lighting, no violence
Entertainment: red carpet, spotlight glamour
Science: laboratory, glowing specimen
Weather: storm system, satellite clouds

OUTPUT JSON:
{
 "entities": {
   "people": [],
   "companies": [],
   "places": [],
   "event_type": ""
 },
 "visual_scene": "",
 "mood": "",
 "camera": "",
 "style": "",
 "lighting": "",
 "color_palette": "",
 "dalle_prompt": "",
 "pexels_fallback": "category + object + place keywords max 5 words"
}"""

        user_prompt = f"Headline: {article.get('title')}\nSummary: {article.get('summary')}\nCategory: {article.get('category')}\nEmotion: {article.get('emotion')}"
        
        payload = {
            "model": self.ollama_model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "format": "json"
        }
        
        try:
            resp = requests.post(self.ollama_url, json=payload, timeout=12)
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text.startswith("```json"): text = text[7:-3].strip()
                elif text.startswith("```"): text = text[3:-3].strip()
                data = json.loads(text)
                if "dalle_prompt" in data:
                    return data
        except Exception as e:
            pass
            
        return fallback

    def _generate_ai_image(self, prompt):
        dalle_key = os.environ.get("OPENAI_API_KEY")
        if not dalle_key:
            raise ValueError("No API key for AI generation")
            
        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {dalle_key}"},
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "size": "1024x1024",
                "quality": "standard",
                "n": 1,
            },
            timeout=35
        )
        resp.raise_for_status()
        url = resp.json()["data"][0]["url"]
        img_resp = requests.get(url, timeout=15)
        img = Image.open(BytesIO(img_resp.content))
        img = img.resize((1200, 1200))
        return img.crop((0, 285, 1200, 915))
        
    def _validate_image(self, img, concept, article, is_ai=False):
        result = {
            "pass": False,
            "relevance_score": 0,
            "quality_score": 0,
            "issues": [],
            "regenerate_reason": None,
            "use_fallback": False
        }
        
        try:
            if img.width < 800:
                result["issues"].append("width < 800")
                return result
            
            gray = img.convert("L")
            extrema = gray.getextrema()
            if extrema[0] == extrema[1]:
                result["issues"].append("blank image")
                return result
                
            from PIL import ImageStat
            stat = ImageStat.Stat(gray)
            avg_luminance = stat.mean[0]
            if avg_luminance < 15 or avg_luminance > 240:
                result["issues"].append("too dark/light")
                return result
                
            import hashlib
            img_small = gray.resize((16, 16))
            h = hashlib.md5(img_small.tobytes()).hexdigest()
            if not hasattr(self, '_recent_hashes'):
                self._recent_hashes = []
            if h in self._recent_hashes:
                result["issues"].append("duplicate hash")
                return result
            self._recent_hashes.append(h)
            if len(self._recent_hashes) > 200:
                self._recent_hashes.pop(0)
                
            result["pass"] = True
        except Exception as e:
            result["issues"].append(f"corrupted file: {e}")
            result["pass"] = False
            return result

        if not is_ai or not result["pass"]:
            return result
            
        try:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return result
                
            import base64
            buffered = BytesIO()
            img.copy().resize((512, 512)).save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            cat = article.get("category", "").lower()
            special_rules = ""
            if "war" in cat or "conflict" in cat:
                special_rules = "If category = war/conflict: No explosions, blood, corpses."
            elif "politic" in cat:
                special_rules = "If category = politics: No fake politician faces."
            elif "financ" in cat:
                special_rules = "If category = finance: Prefer markets/buildings/charts."
            elif "tech" in cat:
                special_rules = "If category = technology: Prefer devices/stage/products."
                
            sys_prompt = f"""You are a quality control inspector for news images.
You receive a news headline and a generated image.
Validate whether the image is appropriate and relevant.

CHECK FOR:
1. RELEVANCE: Does image visually represent headline topic?
2. QUALITY: Sharp, clear, not blurry or pixelated?
3. SAFETY: No gore, violence, nudity, disturbing content.
4. ACCURACY: No wrong people, wrong flags, wrong logos.
5. GENERIC: Not a useless generic stock image.
6. TEXT: No unwanted text or watermarks.

PASS RULE:
Image relevance score must be >= 7/10
{special_rules}

OUTPUT JSON:
{{
 "pass": true,
 "relevance_score": 0,
 "quality_score": 0,
 "issues": [],
 "regenerate_reason": null,
 "use_fallback": false
}}"""
            
            user_content = [
                {"type": "text", "text": f"Headline: {article.get('title')}\nSummary: {article.get('summary')}"},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}}
            ]
            
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o",
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    "max_tokens": 300
                },
                timeout=8
            )
            
            if resp.status_code == 200:
                ai_data = json.loads(resp.json()["choices"][0]["message"]["content"])
                
                is_pass = ai_data.get("pass", False)
                rel = ai_data.get("relevance_score", 0)
                qual = ai_data.get("quality_score", 0)
                
                if is_pass and rel >= 7 and qual >= 7:
                    ai_data["pass"] = True
                else:
                    ai_data["pass"] = False
                    if not ai_data.get("regenerate_reason"):
                        ai_data["regenerate_reason"] = "Failed relevance or quality score thresholds."
                return ai_data
        except Exception as e:
            print(f"Vision validation error: {e}")
            
        return result

    def _fetch_pexels_photo(self, query):
        if not query:
            query = "news"
        encoded_query = urllib.parse.quote(query)
        url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=5&orientation=landscape"
        headers = {"Authorization": os.environ.get("PEXELS_API_KEY", "")}
        
        response = requests.get(url, headers=headers, timeout=8)
        response.raise_for_status()
        data = response.json()
        
        photos = data.get("photos", [])
        if not photos:
            raise ValueError("No photos found")
            
        photo_url = photos[0]["src"]["landscape"]
        
        img_response = requests.get(photo_url, timeout=10)
        img_response.raise_for_status()
        
        base_image = Image.open(BytesIO(img_response.content))
        return base_image.resize((1200, 630), getattr(Image, 'Resampling', Image).LANCZOS)

    def _overlay_text(self, image, headline, source, brand_name, tagline, accent_hex, is_breaking, category=None, viral_score=0):
        try:
            BOLD_FONTS = [
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/calibrib.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
            ]
            BODY_FONTS = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/calibri.ttf",
            ]

            font_headline = self._load_font(BOLD_FONTS, 36)
            font_pill     = self._load_font(BOLD_FONTS, 14)
            font_source   = self._load_font(BODY_FONTS, 17)
            font_brand    = self._load_font(BOLD_FONTS, 19)
            font_tagline  = self._load_font(BODY_FONTS, 13)
            font_score    = self._load_font(BODY_FONTS, 13)

            accent_rgb = self._hex_to_rgb(accent_hex)
            image = image.convert("RGBA")
            W, H = image.size

            overlay1 = Image.new('RGBA', image.size, (0, 0, 0, 0))
            d1 = ImageDraw.Draw(overlay1)
            d1.rectangle([0, 400, W, H], fill=(0, 0, 0, 120))
            image = Image.alpha_composite(image, overlay1)

            overlay2 = Image.new('RGBA', image.size, (0, 0, 0, 0))
            d2 = ImageDraw.Draw(overlay2)
            d2.rectangle([0, 400, W, 418], fill=(*accent_rgb, 200))
            image = Image.alpha_composite(image, overlay2)

            draw = ImageDraw.Draw(image)

            cat_lower   = (category or "world").lower()
            pill_hex    = self.CATEGORY_COLORS.get(cat_lower, accent_hex)
            pill_rgb    = self._hex_to_rgb(pill_hex)
            pill_alpha  = 220
            pill_x, pill_y, pill_w, pill_h, pill_r = 20, 20, 120, 32, 12

            pill_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
            dp = ImageDraw.Draw(pill_layer)
            dp.rounded_rectangle(
                [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
                radius=pill_r,
                fill=(*pill_rgb, pill_alpha)
            )
            image = Image.alpha_composite(image, pill_layer)

            draw = ImageDraw.Draw(image)
            draw.text(
                (pill_x + pill_w // 2, pill_y + pill_h // 2),
                cat_lower.upper(),
                font=font_pill,
                fill=(255, 255, 255),
                anchor="mm"
            )

            score_val  = max(0, min(100, int(viral_score or 0)))
            bar_x, bar_y = W - 140, 20
            bar_w, bar_h = 120, 8
            label_text  = f"Score: {score_val}"

            draw.text((bar_x, bar_y - 16), label_text, font=font_score, fill=(255, 255, 255), anchor="la")
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(60, 60, 60))
            fg_w = int(score_val / 100 * bar_w)
            if fg_w > 0:
                draw.rectangle([bar_x, bar_y, bar_x + fg_w, bar_y + bar_h], fill=accent_rgb)

            wrapped = textwrap.wrap(headline or "", width=48)
            line_h  = 46
            text_y  = 420

            for i, line in enumerate(wrapped[:3]):
                draw.text((26, text_y + 2), line, font=font_headline, fill=(0, 0, 0, 80), anchor="la")
                draw.text((24, text_y), line, font=font_headline, fill=(255, 255, 255), anchor="la")
                text_y += line_h

            draw.text((24, 596), source or "", font=font_source, fill=(170, 170, 170), anchor="la")
            draw.text((W - 24, 582), brand_name or "", font=font_brand, fill=accent_rgb, anchor="ra")
            draw.text((W - 24, 606), tagline or "", font=font_tagline, fill=(136, 136, 136), anchor="ra")

            return image.convert("RGB")

        except Exception as exc:
            image = image.convert("RGB")
            draw = ImageDraw.Draw(image)
            font = self._get_font(28)
            for i, line in enumerate(textwrap.wrap(headline or "", 52)[:3]):
                draw.text((24, 420 + i * 42), line, font=font, fill=(255, 255, 255))
            return image

    def generate_visual(self, article):
        """
        Input: { id, title, summary, category, emotion, viral_score }
        Returns: { 'image_path': path, 'visual_concept_json': dict, 'image_status': 'image_ready', 'image_source': 'ai|pexels|template' }
        """
        concept = self._get_visual_concept(article)
        art_id = article.get("id", "0")
        fname = f"{art_id}_card_{int(time.time())}.png"
        output_path = os.path.join(self.images_dir, fname)
        
        image_source = None
        image_source_reason = None
        base_image = None
        validation_failed = False
        
        validation_json = {}
        
        # COST TIERS
        score = int(article.get("viral_score", 0))
        if score >= 85:
            sequence = [("ai", "ai_high_score"), ("pexels", "pexels_fallback"), ("template", "template_fallback")]
        elif score >= 70:
            sequence = [("pexels", "pexels_mid_score"), ("template", "template_fallback")]
        else:
            sequence = [("template", "template_low_score")]
            
        for tier, reason in sequence:
            if tier == "ai":
                ai_prompt = concept.get("dalle_prompt")
                if ai_prompt:
                    ai_prompt += ", no visible faces, silhouettes only, no portrait faces"
                    try:
                        base_image = self._generate_ai_image(ai_prompt)
                        val_res = self._validate_image(base_image, concept, article, is_ai=True)
                        if not val_res.get("pass"):
                            validation_failed = True
                            if val_res.get("use_fallback"):
                                raise ValueError("AI validation said use fallback")
                                
                            regen_reason = val_res.get("regenerate_reason", "")
                            regen_prompt = ai_prompt + (" - Fix this: " + regen_reason if regen_reason else "")
                            
                            base_image = self._generate_ai_image(regen_prompt)
                            val_res = self._validate_image(base_image, concept, article, is_ai=True)
                            if not val_res.get("pass"):
                                raise ValueError("AI validation failed twice")
                        
                        validation_json = val_res
                        image_source = "ai"
                        image_source_reason = reason
                        break
                    except Exception:
                        base_image = None
            elif tier == "pexels":
                pexels_query = concept.get("pexels_fallback")
                try:
                    base_image = self._fetch_pexels_photo(pexels_query)
                    val_res = self._validate_image(base_image, concept, article, is_ai=False)
                    if not val_res.get("pass"):
                        raise ValueError("Pexels image failed local validation")
                    validation_json = val_res
                    image_source = "pexels"
                    image_source_reason = reason
                    break
                except Exception:
                    base_image = None
            elif tier == "template":
                width, height = 1200, 630
                primary_hex = self.CATEGORY_COLORS.get((article.get("category") or "").lower(), "#1E3A8A")
                base_image = Image.new("RGB", (width, height), color=self._hex_to_rgb(primary_hex))
                val_res = self._validate_image(base_image, concept, article, is_ai=False)
                validation_json = val_res
                image_source = "template"
                image_source_reason = reason
                break
            
        # Composite Overlay
        is_breaking = any(w in article.get("title", "").lower() for w in ["breaking", "urgent"])
        final_image = self._overlay_text(
            base_image,
            article.get("title", ""),
            article.get("source", ""),
            self.config.get("brand_name", "Synthetix News"),
            self.config.get("tagline", "Real-time updates"),
            self.config.get("accent_color", "#E53935"),
            is_breaking,
            category=article.get("category"),
            viral_score=article.get("viral_score", 0)
        )
        
        final_image.save(output_path, format="PNG")
        
        return {
            "image_path": output_path,
            "visual_concept_json": concept,
            "image_status": "image_ready",
            "image_source": image_source,
            "image_source_reason": image_source_reason,
            "validation_failed": validation_failed,
            "validation_json": validation_json,
            "width": final_image.width,
            "height": final_image.height
        }

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def run(self):
        if not self.conn_string:
            print("No DATABASE_URL configured.")
            return {}
            
        db_conn = self._get_conn()
        metrics = {
            "processed": 0,
            "ai_generated": 0,
            "pexels_used": 0,
            "template_used": 0,
            "validation_failed": 0,
            "skipped_cached": 0,
            "validation_checked": 0,
            "validation_passed": 0,
            "validation_regenerated": 0,
            "validation_fallback": 0,
            "validation_relevance_sum": 0,
            "validation_relevance_count": 0
        }
        gen_time_total = 0
        
        try:
            with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Only process viral_score >= 55
                cur.execute("""
                    SELECT * FROM articles 
                    WHERE status = 'approved_unique' AND viral_score >= 55
                    LIMIT 20
                """)
                articles = cur.fetchall()
        except Exception as e:
            print(f"Error fetching for visual generation: {e}")
            db_conn.rollback()
            db_conn.close()
            return metrics
            
        for db_art in articles:
            art_dict = dict(db_art)
            input_art = {
                "id": art_dict["id"],
                "title": art_dict.get("headline", ""),
                "summary": art_dict.get("full_text", "")[:500] if art_dict.get("full_text") else "",
                "category": art_dict.get("category", ""),
                "emotion": art_dict.get("emotion", ""),
                "viral_score": art_dict.get("viral_score", 0),
                "source": art_dict.get("source", "")
            }
            
            if art_dict.get("image_path") and os.path.exists(art_dict["image_path"]):
                metrics["skipped_cached"] += 1
                continue
                
            start_t = time.time()
            try:
                res = self.generate_visual(input_art)
                end_t = time.time()
                gen_time_total += (end_t - start_t)
                
                if res.get("validation_failed"):
                    metrics["validation_failed"] += 1
                    metrics["validation_regenerated"] += 1
                
                v_json = res.get("validation_json", {})
                if v_json:
                    metrics["validation_checked"] += 1
                    if v_json.get("pass"):
                        metrics["validation_passed"] += 1
                    else:
                        metrics["validation_fallback"] += 1
                        
                    rel_score = v_json.get("relevance_score")
                    if rel_score is not None:
                        metrics["validation_relevance_sum"] += rel_score
                        metrics["validation_relevance_count"] += 1
                
                source = res["image_source"]
                if source == "ai": metrics["ai_generated"] += 1
                elif source == "pexels": metrics["pexels_used"] += 1
                elif source == "template": metrics["template_used"] += 1
                
                metrics["processed"] += 1
                
                with db_conn:
                    with db_conn.cursor() as cur:
                        cur.execute("""
                            UPDATE articles
                            SET image_path = %s,
                                visual_concept_json = %s,
                                image_source = %s,
                                image_source_reason = %s,
                                image_width = %s,
                                image_height = %s,
                                image_validation_json = %s,
                                image_relevance_score = %s,
                                image_quality_score = %s,
                                image_issues = %s,
                                status = %s
                            WHERE id = %s
                        """, (
                            res["image_path"],
                            json.dumps(res["visual_concept_json"]),
                            source,
                            res["image_source_reason"],
                            res["width"],
                            res["height"],
                            json.dumps(v_json),
                            v_json.get("relevance_score"),
                            v_json.get("quality_score"),
                            json.dumps(v_json.get("issues", [])),
                            res["image_status"],
                            art_dict["id"]
                        ))
            except Exception as e:
                print(f"Error processing visual for {art_dict['id']}: {e}")
                db_conn.rollback()
                try:
                    with db_conn:
                        with db_conn.cursor() as cur:
                            cur.execute("UPDATE articles SET status = 'image_failed' WHERE id = %s", (art_dict["id"],))
                except Exception:
                    db_conn.rollback()
                
        db_conn.close()
        avg_gen_time = round(gen_time_total / max(1, metrics['processed']), 1)
        print(f"[VISUAL] processed={metrics['processed']}")
        print(f"[VISUAL] ai_generated={metrics['ai_generated']}")
        print(f"[VISUAL] pexels_used={metrics['pexels_used']}")
        print(f"[VISUAL] template_used={metrics['template_used']}")
        print(f"[VISUAL] skipped_cached={metrics['skipped_cached']}")
        print(f"[VISUAL] avg_gen_time={avg_gen_time}s")
        
        print(f"[VALIDATION] checked={metrics['validation_checked']}")
        print(f"[VALIDATION] passed={metrics['validation_passed']}")
        print(f"[VALIDATION] regenerated={metrics['validation_regenerated']}")
        print(f"[VALIDATION] fallback={metrics['validation_fallback']}")
        avg_rel = round(metrics["validation_relevance_sum"] / max(1, metrics["validation_relevance_count"]), 1)
        print(f"[VALIDATION] avg_relevance={avg_rel}")
        
        return metrics

if __name__ == "__main__":
    conn_string = os.getenv("DATABASE_URL", "host=localhost port=5432 dbname=news_system user=postgres")
    try:
        conn = psycopg2.connect(conn_string)
        agent = VisualGenerationAgent()
        agent.run(conn)
        conn.close()
    except Exception as e:
        print(f"Error executing VisualGenerationAgent: {e}")
