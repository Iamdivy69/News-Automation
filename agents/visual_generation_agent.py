import os
import json
import time
import textwrap
import urllib.parse
from io import BytesIO
import psycopg2
import psycopg2.extras
import requests
import traceback
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from agents.headline_generator import HeadlineGenerator
from agents.image_renderer import ImageRenderer

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

    def __init__(self):
        self.conn_string = os.environ.get("DATABASE_URL")
        
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        today = datetime.now().strftime('%Y-%m-%d')
        self.images_dir = os.path.join(self.project_root, 'images', today)
        os.makedirs(self.images_dir, exist_ok=True)
        
        self.headline_gen = HeadlineGenerator()
        self.renderer = ImageRenderer()

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def _upload_to_cloudinary(self, file_path: str) -> str:
        cloudinary_url = os.environ.get("CLOUDINARY_URL")
        if not cloudinary_url:
            return file_path
            
        try:
            import cloudinary
            import cloudinary.uploader
            resp = cloudinary.uploader.upload(file_path, folder="synthetix_news")
            return resp.get("secure_url", file_path)
        except Exception as e:
            print(f"Cloudinary upload failed: {e}")
            return file_path

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

    def _validate_image(self, img):
        result = {"pass": False, "issues": []}
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
                
            result["pass"] = True
        except Exception as e:
            result["issues"].append(f"corrupted file: {e}")
            
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

    def run(self):
        conn = self._get_conn()
        if not conn:
            print("No DATABASE_URL configured.")
            return {}
            
        metrics = {
            "processed": 0,
            "gemini_template": 0,
            "pexels_fallback": 0,
            "failed": 0
        }
        
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, headline, full_text, category, is_breaking, source, viral_score
                    FROM articles 
                    WHERE status = 'summarised' AND top_30_selected = TRUE 
                    LIMIT 30
                """)
                articles = cur.fetchall()
        except Exception as e:
            print(f"Error fetching articles: {e}")
            conn.close()
            return metrics
            
        for db_art in articles:
            article_id = db_art["id"]
            
            art_dict = {
                "id": article_id,
                "title": db_art.get("headline", ""),
                "summary": db_art.get("full_text", "")[:500] if db_art.get("full_text") else "",
                "category": db_art.get("category", ""),
                "is_breaking": db_art.get("is_breaking", False),
                "source": db_art.get("source", ""),
                "viral_score": db_art.get("viral_score", 0)
            }
            
            try:
                # 2a. Call HeadlineGenerator
                headline_data = self.headline_gen.generate(art_dict)
                
                # Combine data for renderer
                render_data = headline_data.copy()
                render_data.update(art_dict)
                
                fname = f"{article_id}_render_{int(time.time())}.jpg"
                output_path = os.path.join(self.images_dir, fname)
                
                try:
                    # 2b. Call ImageRenderer
                    final_path = self.renderer.render(render_data, output_path)
                    source_label = "gemini_template"
                    metrics["gemini_template"] += 1
                except Exception as render_err:
                    print(f"ImageRenderer failed for {article_id}: {render_err}. Trying Pexels fallback.")
                    # 3. FALLBACK: Call old Pexels fetch using pexels_fallback query logic
                    category = (art_dict.get("category") or "").lower()
                    pexels_fallback = "breaking news event"
                    if "tech" in category: pexels_fallback = "futuristic product launch"
                    elif "politic" in category: pexels_fallback = "podium parliament"
                    elif "financ" in category or "stock" in category: pexels_fallback = "stock market office"
                    elif "sport" in category: pexels_fallback = "stadium crowd"
                    elif "war" in category: pexels_fallback = "command room world map"
                    elif "scienc" in category: pexels_fallback = "lab discovery"
                    elif "weather" in category: pexels_fallback = "storm satellite"

                    base_image = self._fetch_pexels_photo(pexels_fallback)
                    
                    is_breaking_flag = any(w in art_dict.get("title", "").lower() for w in ["breaking", "urgent"])
                    
                    final_image = self._overlay_text(
                        base_image,
                        headline_data.get("headline", art_dict.get("title", "")),
                        art_dict.get("source", ""),
                        "Synthetix News",
                        "Real-time updates",
                        "#E53935",
                        is_breaking_flag,
                        category=art_dict.get("category"),
                        viral_score=art_dict.get("viral_score", 0)
                    )
                    final_image.save(output_path, format="JPEG", quality=90)
                    final_path = output_path
                    source_label = "pexels_fallback"
                    metrics["pexels_fallback"] += 1
                
                # 2c. Upload to Cloudinary (if set) or use local path
                uploaded_url = self._upload_to_cloudinary(final_path)
                
                # 2d. UPDATE DB
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE articles SET
                            image_url = %s,
                            image_prompt = %s,
                            image_source = %s,
                            status = 'image_ready',
                            processing_stage = 'image_ready',
                            updated_at = NOW()
                        WHERE id = %s
                    """, (
                        uploaded_url,
                        headline_data.get("headline", ""),
                        source_label,
                        article_id
                    ))
                conn.commit()
                metrics["processed"] += 1
                
            except Exception as e:
                conn.rollback()
                print(f"Error processing article {article_id}: {e}")
                metrics["failed"] += 1
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO error_logs (agent, message, stack_trace) VALUES (%s, %s, %s)",
                            (self.AGENT_NAME, f"Visual generation error for article {article_id}: {e}", traceback.format_exc())
                        )
                    conn.commit()
                except:
                    pass
                
        conn.close()
        print(f"[VISUAL] processed={metrics['processed']} gemini_template={metrics['gemini_template']} pexels_fallback={metrics['pexels_fallback']} failed={metrics['failed']}")
        return metrics

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    agent = VisualGenerationAgent()
    agent.run()
