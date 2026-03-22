import os
import json
import shutil
import textwrap
import requests
from io import BytesIO
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import urllib.parse

CREATE_IMAGES_TABLE = """
CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    article_id INT NOT NULL,
    image_path TEXT NOT NULL,
    image_type TEXT,
    is_branded BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

class VisualGenerationAgent:
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
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', 'config', 'brand_config.json'
            )
        config_path = os.path.normpath(config_path)
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..')
        )
        # Store images in date-based subfolders: images/YYYY-MM-DD/
        today = datetime.now().strftime('%Y-%m-%d')
        self.images_dir = os.path.join(self.project_root, 'images', today)
        os.makedirs(self.images_dir, exist_ok=True)

    def cleanup_old_image_folders(self, days_to_keep: int = 7) -> int:
        """
        Delete image date-subfolders (format YYYY-MM-DD) that are older
        than `days_to_keep` days.
        Returns the count of folders deleted.
        """
        images_root = os.path.join(self.project_root, 'images')
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        deleted = 0
        try:
            for entry in os.scandir(images_root):
                if not entry.is_dir():
                    continue
                try:
                    folder_date = datetime.strptime(entry.name, '%Y-%m-%d')
                except ValueError:
                    continue  # Skip non-date folders (e.g. .gitkeep parent dirs)
                if folder_date < cutoff:
                    shutil.rmtree(entry.path)
                    deleted += 1
                    print(f"  Deleted old image folder: {entry.name}")
        except Exception as e:
            print(f"cleanup_old_image_folders error: {e}")
        return deleted

    def _hex_to_rgb(self, hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        
    def _load_font(self, path_list: list, size: int):
        """Try each font path in order; fall back to PIL default if none found."""
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
            "C:/Windows/Fonts/arialbd.ttf",   # Arial Bold
            "C:/Windows/Fonts/arial.ttf",      # Arial
            "C:/Windows/Fonts/calibrib.ttf",   # Calibri Bold
            "C:/Windows/Fonts/segoeui.ttf",    # Segoe UI
        ]
        return self._load_font(font_candidates, size)

    SAFE_FALLBACK_QUERIES = {
        "world":       "global news newspaper",
        "india":       "india city landscape",
        "technology":  "technology digital screen",
        "business":    "business office meeting",
        "sports":      "sports stadium crowd",
        "health":      "healthcare hospital doctor",
        "science":     "science laboratory research",
    }

    def _build_image_query(self, headline, category):
        query = category or "news"
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "mistral",
                    "stream": False,
                    "system": "You are a stock photo search expert. Output ONLY a 2-3 word search query for a photorealistic landscape stock photo that visually represents the news headline. No explanations. No quotes. Just the search words.",
                    "prompt": f"Headline: {headline}\nCategory: {category}"
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            q = data.get("response", "").strip()
            if q:
                query = q.splitlines()[0].strip()
        except Exception:
            pass

        sensitive_words = ["missile", "bomb", "war", "attack", "kill", "dead", "shoot", "crash", "explosion", "protest", "riot"]
        query_lower = query.lower()
        has_sensitive = any(word in query_lower for word in sensitive_words)
        
        needs_fallback = has_sensitive
        if not needs_fallback:
            try:
                encoded_query = urllib.parse.quote(query)
                url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=1"
                headers = {"Authorization": os.environ.get("PEXELS_API_KEY", "")}
                test_resp = requests.get(url, headers=headers, timeout=5)
                test_resp.raise_for_status()
                if test_resp.json().get("total_results", 0) == 0:
                    needs_fallback = True
            except Exception:
                needs_fallback = True
                
        if needs_fallback:
            cat_safe = (category or "").lower()
            return self.SAFE_FALLBACK_QUERIES.get(cat_safe, "breaking news world")
            
        return query

    def _fetch_pexels_photo(self, query):
        if not query:
            query = "news"
        encoded_query = urllib.parse.quote(query)
        url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page=5&orientation=landscape"
        headers = {"Authorization": os.environ.get("PEXELS_API_KEY", "")}
        
        try:
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
        except requests.RequestException as e:
            raise ConnectionError(f"Request failed: {e}")

    def _overlay_text(self, image, headline, source, brand_name, tagline, accent_hex, is_breaking, category=None, viral_score=0):
        """
        Composites a polished multi-layer UI overlay onto the image.
        Returns an RGB PIL Image.
        """
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
            W, H = image.size  # expected: 1200 x 630

            # ── Layer 1: dark bottom overlay (y 400..630, alpha 120) ──────────
            overlay1 = Image.new('RGBA', image.size, (0, 0, 0, 0))
            d1 = ImageDraw.Draw(overlay1)
            d1.rectangle([0, 400, W, H], fill=(0, 0, 0, 120))
            image = Image.alpha_composite(image, overlay1)

            # ── Layer 2: accent top-border on dark overlay (y 400..418, alpha 200) ──
            overlay2 = Image.new('RGBA', image.size, (0, 0, 0, 0))
            d2 = ImageDraw.Draw(overlay2)
            d2.rectangle([0, 400, W, 418], fill=(*accent_rgb, 200))
            image = Image.alpha_composite(image, overlay2)

            draw = ImageDraw.Draw(image)

            # ── Category colour pill (top-left) ───────────────────────────────
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

            # ── Viral score bar (top-right) ───────────────────────────────────
            score_val  = max(0, min(100, int(viral_score or 0)))
            bar_x, bar_y = W - 140, 20
            bar_w, bar_h = 120, 8
            label_text  = f"Score: {score_val}"

            draw.text((bar_x, bar_y - 16), label_text, font=font_score, fill=(255, 255, 255), anchor="la")
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(60, 60, 60))  # bg
            fg_w = int(score_val / 100 * bar_w)
            if fg_w > 0:
                draw.rectangle([bar_x, bar_y, bar_x + fg_w, bar_y + bar_h], fill=accent_rgb)

            # ── Headline text with shadow (y starting at 420) ─────────────────
            wrapped = textwrap.wrap(headline or "", width=48)
            line_h  = 46
            text_y  = 420

            for i, line in enumerate(wrapped[:3]):
                # Shadow (black, offset +2/+2)
                draw.text((26, text_y + 2), line, font=font_headline, fill=(0, 0, 0, 80), anchor="la")
                # Main white text
                draw.text((24, text_y), line, font=font_headline, fill=(255, 255, 255), anchor="la")
                text_y += line_h

            # ── Source + brand footer ─────────────────────────────────────────
            draw.text((24, 596), source or "", font=font_source, fill=(170, 170, 170), anchor="la")
            draw.text((W - 24, 582), brand_name or "", font=font_brand, fill=accent_rgb, anchor="ra")
            draw.text((W - 24, 606), tagline or "", font=font_tagline, fill=(136, 136, 136), anchor="ra")

            return image.convert("RGB")

        except Exception as exc:
            print(f"_overlay_text error (falling back to basic): {exc}")
            # Minimal safe fallback
            image = image.convert("RGB")
            draw = ImageDraw.Draw(image)
            font = self._get_font(28)
            for i, line in enumerate(textwrap.wrap(headline or "", 52)[:3]):
                draw.text((24, 420 + i * 42), line, font=font, fill=(255, 255, 255))
            return image

    def generate_headline_card(self, headline, source, category, is_breaking, output_path=None, article_id=None, viral_score=0):
        import time
        if article_id is None:
            output_path = os.path.join(self.images_dir, f"card_{int(time.time())}.png")
        else:
            output_path = os.path.join(self.images_dir, f"{article_id}_card.png")
            
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
        try:
            query = self._build_image_query(headline, category)
            base_image = self._fetch_pexels_photo(query)
            final_image = self._overlay_text(
                base_image,
                headline,
                source,
                self.config["brand_name"],
                self.config["tagline"],
                self.config["accent_color"],
                is_breaking,
                category=category,
                viral_score=viral_score,
            )
            final_image.save(output_path, format="PNG")
            print(f"  [Pexels] {article_id}: query='{query}'")
            return output_path
        except Exception as e:
            print(f"  [Fallback to solid card] {e}")
            # Call the original solid-color generation logic as fallback
            width, height = 1200, 630
            
            # Background mapping
            primary_hex = self.CATEGORY_COLORS.get(
                (category or "").lower(),
                self.config.get("primary_color", "#1E3A8A")
            )
            bg_rgb = self._hex_to_rgb(primary_hex)
            
            img = Image.new("RGB", (width, height), color=bg_rgb)
            draw = ImageDraw.Draw(img)
            
            if is_breaking:
                # Red breaking news banner across top 60px
                draw.rectangle([(0, 0), (width, 60)], fill="#C62828")
                font_breaking = self._get_font(22)
                # anchor 'mm' strictly centers the text both horizontally and vertically
                draw.text((width // 2, 30), "BREAKING NEWS", font=font_breaking, fill="#FFFFFF", anchor="mm")
                
            font_headline = self._get_font(38)
            wrapped_lines = textwrap.wrap(headline or "", width=42)
            
            # Inject textual data dynamically auto-wrapping at 42 lines starting at Y=120
            current_y = 120
            line_height = 45 
            for line in wrapped_lines:
                # anchor 'ma' strictly horizontally centers the text aligning to the top
                draw.text((width // 2, current_y), line, font=font_headline, fill="#FFFFFF", anchor="ma")
                current_y += line_height
                
            # Draw aesthetic border split
            accent_hex = self.config.get("accent_color", "#00E5FF")
            draw.line([(0, 480), (width, 480)], fill=accent_hex, width=2)
            
            # Footer components (Left Source signature)
            font_source = self._get_font(20)
            draw.text((40, 500), source or "", font=font_source, fill="#BBBBBB", anchor="la")
            
            # Footer components (Right Corporate signatures)
            brand_name = self.config.get("brand_name", "")
            # right-aligned constraint `ra` ensures variable width string anchors precisely to the margin
            draw.text((1160, 500), brand_name, font=font_source, fill=accent_hex, anchor="ra")
            
            tagline = self.config.get("tagline", "")
            font_tagline = self._get_font(15)
            # Below the brand name boundary
            draw.text((1160, 528), tagline, font=font_tagline, fill="#888888", anchor="ra")
            
            # Safety enforcement on path constraints
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            img.save(output_path, format="PNG")
            
            return output_path

    def save_image_record(self, article_id, image_path, image_type, db_conn):
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO images (article_id, image_path, image_type, is_branded)
                VALUES (%s, %s, %s, TRUE)
                """,
                (article_id, image_path, image_type)
            )
        db_conn.commit()
