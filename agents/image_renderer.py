import os
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

class ImageRenderer:
    def __init__(self):
        self.width = 1080
        self.height = 1350
        self.bg_color = "#FFFFFF"
        self.font_path = "assets/fonts/PlayfairDisplay-Bold.ttf"
        self._ensure_font()

    def _ensure_font(self):
        os.makedirs(os.path.dirname(self.font_path), exist_ok=True)
        if not os.path.exists(self.font_path):
            # Multiple fallback URLs for Playfair Display Bold
            font_urls = [
                "https://fonts.gstatic.com/s/playfairdisplay/v30/nuFvD-vYSZviVYUb_rj3ij__anPXJzDwcbmjWBN2PKdFvXDXbtXK-F2qC0s.ttf",
                "https://github.com/googlefonts/playfair/raw/main/fonts/ttf/PlayfairDisplay-Bold.ttf",
            ]
            for url in font_urls:
                try:
                    resp = requests.get(url, timeout=30)
                    resp.raise_for_status()
                    with open(self.font_path, "wb") as f:
                        f.write(resp.content)
                    print(f"[FONT] Downloaded from {url}")
                    break
                except Exception as e:
                    print(f"[FONT] Failed URL {url}: {e}")


    def _get_font(self, size):
        try:
            return ImageFont.truetype(self.font_path, size)
        except Exception:
            try:
                return ImageFont.load_default(size=size)
            except TypeError:
                return ImageFont.load_default()

    def render(self, data: dict, output_path: str) -> str:
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        headline = data.get("headline", "").upper()
        highlight_words = [w.upper() for w in data.get("highlight_words", [])]
        subtext = data.get("subtext", "")
        tag = data.get("tag", "default").lower()
        
        # Color Routing
        tag_colors = {
            "sports": "#CC0000",
            "finance": "#B8860B",
            "politics": "#003366",
            "breaking": "#CC0000",
            "default": "#CC0000"
        }
        accent_color = tag_colors.get(tag, tag_colors["default"])

        # 1. TOP BAR (50px black)
        draw.rectangle([0, 0, self.width, 50], fill="#000000")
        
        bar_font = self._get_font(24)
        date_str = datetime.now().strftime("%B %d, %Y").upper()
        draw.text((20, 10), date_str, font=bar_font, fill="#FFFFFF")
        
        tag_str = tag.upper()
        center_text = f"{tag_str} EDITION"
        bbox = draw.textbbox((0, 0), center_text, font=bar_font)
        cw = bbox[2] - bbox[0]
        draw.text(((self.width - cw) // 2, 10), center_text, font=bar_font, fill=accent_color)
        
        cat_str = data.get("category", tag).upper()
        c_bbox = draw.textbbox((0, 0), cat_str, font=bar_font)
        ccw = c_bbox[2] - c_bbox[0]
        draw.text((self.width - ccw - 20, 10), cat_str, font=bar_font, fill="#FFFFFF")

        # Breaking Banner Strip
        y_offset = 50
        if tag == "breaking":
            draw.rectangle([0, y_offset, self.width, y_offset + 40], fill="#CC0000")
            b_font = self._get_font(28)
            b_text = "BREAKING NEWS"
            b_bbox = draw.textbbox((0,0), b_text, font=b_font)
            bw = b_bbox[2] - b_bbox[0]
            draw.text(((self.width - bw) // 2, y_offset + 5), b_text, font=b_font, fill="#FFFFFF")
            y_offset += 40

        # 2. HEADLINE ZONE
        y_offset += 80
        font_size = 90
        max_w = 1000
        
        # Word wrap logic with font scaling
        lines = []
        while font_size > 20:
            h_font = self._get_font(font_size)
            words = headline.split()
            lines = []
            curr_line = []
            
            for word in words:
                curr_line.append(word)
                test_line = " ".join(curr_line)
                bbox = draw.textbbox((0, 0), test_line, font=h_font)
                if (bbox[2] - bbox[0]) > max_w:
                    curr_line.pop()
                    if curr_line:
                        lines.append(" ".join(curr_line))
                    curr_line = [word]
            if curr_line:
                lines.append(" ".join(curr_line))
                
            if len(lines) <= 3:
                too_wide = False
                for line in lines:
                    bbox = draw.textbbox((0,0), line, font=h_font)
                    if (bbox[2] - bbox[0]) > max_w:
                        too_wide = True
                        break
                if not too_wide:
                    break
                    
            font_size -= 5

        # Draw headline lines
        h_font = self._get_font(font_size)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=h_font)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            x_start = (self.width - lw) // 2
            
            # Draw word by word to colorize highlight_words
            words = line.split()
            curr_x = x_start
            for word in words:
                clean_word = word.strip(".,!?\"'")
                color = "#CC0000" if clean_word in highlight_words else "#000000"
                w_bbox = draw.textbbox((0,0), word, font=h_font)
                ww = w_bbox[2] - w_bbox[0]
                draw.text((curr_x, y_offset), word, font=h_font, fill=color)
                # Space width
                s_bbox = draw.textbbox((0,0), " ", font=h_font)
                curr_x += ww + (s_bbox[2] - s_bbox[0])
            y_offset += lh + 20

        # RED RULE
        y_offset += 30
        draw.rectangle([(self.width - 100) // 2, y_offset, (self.width + 100) // 2, y_offset + 4], fill="#CC0000")
        
        # SUBTEXT
        y_offset += 40
        sub_font = self._get_font(28)
        sub_bbox = draw.textbbox((0,0), subtext, font=sub_font)
        sw = sub_bbox[2] - sub_bbox[0]
        draw.text(((self.width - sw) // 2, y_offset), subtext, font=sub_font, fill="#555555")
        y_offset += sub_bbox[3] - sub_bbox[1] + 80

        # 3. CONTENT CARD
        card_margin = 60
        card_w = self.width - (card_margin * 2)
        card_h = 400
        card_x0 = card_margin
        card_y0 = y_offset
        card_x1 = card_x0 + card_w
        card_y1 = card_y0 + card_h
        
        draw.rectangle([card_x0, card_y0, card_x1, card_y1], outline="#DDDDDD", width=3)
        
        content_font = self._get_font(36)
        
        if tag == "sports":
            t1 = data.get("team1", "HOME")
            t2 = data.get("team2", "AWAY")
            wl = data.get("winner_label", "")
            perf = data.get("performers", "")
            last5 = data.get("last5", "")
            
            cy = card_y0 + 50
            
            vs_text = f"{t1} vs {t2}"
            vs_bbox = draw.textbbox((0,0), vs_text, font=self._get_font(48))
            draw.text(((self.width - (vs_bbox[2]-vs_bbox[0])) // 2, cy), vs_text, font=self._get_font(48), fill="#000000")
            cy += 80
            
            if wl:
                wl_text = f"Winner: {wl}"
                wl_bbox = draw.textbbox((0,0), wl_text, font=content_font)
                draw.text(((self.width - (wl_bbox[2]-wl_bbox[0])) // 2, cy), wl_text, font=content_font, fill="#CC0000")
                cy += 60
            if perf:
                perf_text = f"Key Performers: {perf}"
                draw.text((card_x0 + 40, cy), perf_text, font=content_font, fill="#333333")
                cy += 60
            if last5:
                last_text = f"Last 5: {last5}"
                draw.text((card_x0 + 40, cy), last_text, font=content_font, fill="#555555")
        else:
            # Fallback basic content card
            cy = card_y0 + 100
            cx = self.width // 2
            r = 60
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent_color)
            letter = cat_str[0] if cat_str else "N"
            l_font = self._get_font(70)
            l_bbox = draw.textbbox((0,0), letter, font=l_font)
            draw.text((cx - (l_bbox[2]-l_bbox[0])//2, cy - (l_bbox[3]-l_bbox[1])//2 - 15), letter, font=l_font, fill="#FFFFFF")
            
            k_text = f"{cat_str} HIGHLIGHTS"
            k_bbox = draw.textbbox((0,0), k_text, font=content_font)
            draw.text(((self.width - (k_bbox[2]-k_bbox[0])) // 2, cy + 120), k_text, font=content_font, fill="#333333")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path, quality=95)
        
        print(f"[RENDER] output={output_path} size={self.width}x{self.height} tag={tag} source=gemini_template")
        return output_path

if __name__ == "__main__":
    renderer = ImageRenderer()
    data = {
        "headline": "STOCK MARKET CRASHES AMID GLOBAL SELLOFF",
        "highlight_words": ["CRASHES", "SELLOFF"],
        "subtext": "Global indices plunge 5% as tech stocks see their worst day since 2008.",
        "tag": "finance"
    }
    renderer.render(data, "assets/images/test_render.jpg")
