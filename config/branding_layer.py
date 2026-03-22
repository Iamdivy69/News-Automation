import os
import json
import re
from PIL import Image, ImageDraw, ImageFont

class BrandingLayer:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'brand_config.json'
            )
        config_path = os.path.normpath(config_path)
        self.config = self.load_config(config_path)

    def load_config(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found at {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        required_fields = [
            "brand_name", "tagline", "primary_color", "accent_color", 
            "background_color", "font_name", "logo_path", "signature", 
            "tone_description", "tone_keywords", "banned_words", 
            "posting_style", "hashtag_prefix"
        ]
        
        for field in required_fields:
            if field not in config:
                raise ValueError(field)
                
        return config

    def apply_tone(self, text, platform):
        if not text:
            return text
            
        # 1. Replace banned words (case-insensitive) with a neutral alternative
        banned_words = self.config.get("banned_words", [])
        if banned_words:
            # Sort by length descending to match longest phrases first (e.g. "you won't believe")
            banned_sorted = sorted(banned_words, key=len, reverse=True)
            pattern = re.compile(r'\b(' + '|'.join(map(re.escape, banned_sorted)) + r')\b', re.IGNORECASE)
            text = pattern.sub("notable", text)
            
        # 2. Ensure at least one tone_keyword appears
        keywords = self.config.get("tone_keywords", [])
        if keywords:
            text_lower = text.lower()
            if not any(kw.lower() in text_lower for kw in keywords):
                first_keyword = keywords[0].capitalize()
                text = f"{first_keyword}: {text}"
                
        # 3. Append the brand signature on a new line
        signature = self.config.get("signature", "")
        if signature:
            text = f"{text}\n\n{signature}"
            
        return text

    def apply_hashtag_prefix(self, hashtags_string):
        if not hashtags_string:
            return self.config.get("hashtag_prefix", "")
            
        prefix = self.config.get("hashtag_prefix", "").strip()
        if not prefix:
            return hashtags_string
            
        # Split commas and clean up spacing
        tags = [t.strip() for t in hashtags_string.split(',')]
        tags = [t for t in tags if t] 
        
        prefix_lower = prefix.lower()
        if not any(t.lower() == prefix_lower for t in tags):
            tags.insert(0, prefix)
            
        return ", ".join(tags)

    def _hex_to_rgb(self, hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

    def apply_visual_brand(self, image_path, output_path):
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            width, height = img.size
            
            # Bottom 18% of image
            overlay_height = int(height * 0.18)
            overlay_y = height - overlay_height
            
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Parse background_color mapping
            bg_hex = self.config.get("background_color", "#000000")
            r, g, b = self._hex_to_rgb(bg_hex)
            
            # Draw semi-transparent rectangle (alpha 180) across bottom 18%
            draw.rectangle(
                [(0, overlay_y), (width, height)],
                fill=(r, g, b, 180)
            )
            
            # Composite overlay onto original image
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)
            
            # Load fonts with fail-safes for standard availability
            try:
                font_title = ImageFont.truetype("arialbd.ttf", 28)
            except IOError:
                try:
                    font_title = ImageFont.load_default(size=28)
                except TypeError:
                    font_title = ImageFont.load_default()
                    
            try:
                font_tagline = ImageFont.truetype("arial.ttf", 16)
            except IOError:
                try:
                    font_tagline = ImageFont.load_default(size=16)
                except TypeError:
                    font_tagline = ImageFont.load_default()

            # Write brand_name (white bold, size 28, left-aligned with 20px padding)
            brand_name = self.config.get("brand_name", "")
            title_x = 20
            # Vertically align within the 18% band (accounting for font height)
            title_y = overlay_y + (overlay_height // 2) - 25
            
            draw.text((title_x, title_y), brand_name, font=font_title, fill=(255, 255, 255, 255))
            
            # Write tagline (accent_color, size 16, below brand name)
            tagline = self.config.get("tagline", "")
            accent_hex = self.config.get("accent_color", "#FFFFFF")
            ar, ag, ab = self._hex_to_rgb(accent_hex)
            
            tagline_y = title_y + 32
            draw.text((title_x, tagline_y), tagline, font=font_tagline, fill=(ar, ag, ab, 255))
            
            out_img = img.convert("RGB")
            out_img.save(output_path)
            
        return output_path

    def brand_summary(self, summary_dict):
        result = summary_dict.copy()
        
        # Apply tone constraint to social text keys
        target_keys = ["twitter_text", "linkedin_text", "instagram_caption", "facebook_text"]
        for field in target_keys:
            if field in result and result[field]:
                platform = field.split('_')[0]
                result[field] = self.apply_tone(result[field], platform)
                
        # Apply hashtag prefixes
        if "hashtags" in result and result["hashtags"]:
            result["hashtags"] = self.apply_hashtag_prefix(result["hashtags"])
            
        return result
