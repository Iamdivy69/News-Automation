import os
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

class ImageRenderer:
    def __init__(self):
        self.width = 1080
        self.height = 1080 # CHANGED: square canvas like reference
        self.bg_color = "#FAFAF8" # CHANGED: very slight warm white, not pure white
        # Font paths in priority order
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        font_dir = os.path.join(self.project_root, 'assets', 'fonts')
        os.makedirs(font_dir, exist_ok=True)
        self.font_headline = os.path.join(font_dir, 'PlayfairDisplay-Bold.ttf')
        self.font_subtext = os.path.join(font_dir, 'OpenSans-Bold.ttf')
        self._ensure_fonts(font_dir)

    def _ensure_fonts(self, font_dir):
        '''Download fonts from working CDN sources. Never crash if download fails.'''
        fonts_needed = [
            # (local_path, working_download_urls_list)
            (self.font_headline, [
                'C:/Windows/Fonts/georgiab.ttf', # local copy first for Windows
                'C:/Windows/Fonts/timesbd.ttf',
                'https://github.com/clauseggers/playfair/raw/master/fonts/ttf/PlayfairDisplay-Bold.ttf',
                'https://noto-website-2.storage.googleapis.com/pkgs/Playfair_Display.zip', # skip if fails
            ]),
            (self.font_subtext, [
                '/usr/share/fonts/truetype/open-sans/OpenSans-Bold.ttf', # local copy first
                'C:/Windows/Fonts/arialbd.ttf', # local copy first for Windows
                'https://fonts.gstatic.com/s/opensans/v40/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsjZ0B4gaVc.ttf',
            ]),
        ]
        for local_path, sources in fonts_needed:
            if os.path.exists(local_path) and os.path.getsize(local_path) > 30000:
                continue # valid font already exists
            for src in sources:
                if not src.startswith('http') and os.path.exists(src):
                    # local system font — just copy it
                    import shutil
                    shutil.copy2(src, local_path)
                    print(f'[FONT] Copied from system: {src}')
                    break
                if src.startswith('http'):
                    try:
                        import requests
                        r = requests.get(src, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
                        if r.status_code == 200 and len(r.content) > 30000:
                            with open(local_path, 'wb') as f:
                                f.write(r.content)
                            print(f'[FONT] Downloaded: {os.path.basename(local_path)} ({len(r.content)} bytes)')
                            break
                    except Exception as e:
                        print(f'[FONT] Failed {src}: {e}')

    def _get_font(self, size, bold=True):
        '''Get font with full fallback chain. Never returns a bitmap font silently.'''
        # Priority: project fonts → system serif → system sans → PIL default
        candidates = [
            self.font_headline if bold else self.font_subtext,
            '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf',
            '/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
            'C:/Windows/Fonts/georgiab.ttf',
            'C:/Windows/Fonts/timesbd.ttf',
            '/usr/share/fonts/truetype/open-sans/OpenSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            'C:/Windows/Fonts/arialbd.ttf',
        ]
        for path in candidates:
            if path and os.path.exists(path) and os.path.getsize(path) > 10000:
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        # Last resort: PIL default at approximate size
        print(f'[FONT] WARNING: Using PIL default font at size {size}')
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    def render(self, data: dict, output_path: str) -> str:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap, os
        from datetime import datetime

        # Canvas
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        W, H = self.width, self.height

        headline = str(data.get('headline', '')).upper().strip()
        highlight_words = [str(w).upper().strip() for w in data.get('highlight_words', [])]
        subtext = str(data.get('subtext', '')).strip()
        tag = str(data.get('tag', 'world')).lower().strip()

        TAG_COLORS = {
            'breaking': '#CC0000',
            'sports': '#CC0000',
            'finance': '#B8860B',
            'politics': '#003366',
            'technology': '#0066CC',
            'world': '#CC0000',
            'india': '#CC6600',
        }
        accent = TAG_COLORS.get(tag, '#CC0000')

        # 1. AUTO-SIZE HEADLINE
        # Start at 180px, shrink until all words fit in max 3 lines within 900px wide
        MAX_W = 900
        MAX_LINES = 3
        font_size = 180
        h_font = None
        h_lines = []

        while font_size >= 60:
            h_font = self._get_font(font_size, bold=True)
            words = headline.split()
            lines = []
            cur = []
            for w in words:
                cur.append(w)
                bb = draw.textbbox((0,0), ' '.join(cur), font=h_font)
                if (bb[2] - bb[0]) > MAX_W:
                    cur.pop()
                    if cur:
                        lines.append(' '.join(cur))
                    cur = [w]
            if cur:
                lines.append(' '.join(cur))
                
            fits = len(lines) <= MAX_LINES and all(
                (draw.textbbox((0,0), l, font=h_font)[2] - draw.textbbox((0,0), l, font=h_font)[0]) <= MAX_W
                for l in lines
            )
            if fits:
                h_lines = lines
                break
            font_size -= 10
            
        if not h_lines:
            h_lines = [headline[:30], headline[30:60], headline[60:]]
            h_lines = [l.strip() for l in h_lines if l.strip()]
            h_font = self._get_font(80, bold=True)
            font_size = 80

        # 2. CALCULATE TOTAL HEADLINE HEIGHT
        line_h = draw.textbbox((0,0), 'Ag', font=h_font)[3] - draw.textbbox((0,0), 'Ag', font=h_font)[1]
        line_gap = int(font_size * 0.18) # 18% of font size between lines
        total_h_height = len(h_lines) * line_h + (len(h_lines) - 1) * line_gap

        # 3. VERTICAL LAYOUT
        # Layout centers the whole composition vertically with more weight at top
        top_pad = int(H * 0.10) # 10% top padding
        rule_gap = int(font_size * 0.35)
        rule_h = 5
        subtext_gap = 40
        tag_bottom = 60

        # Measure subtext height (will be computed after wrap)
        s_font = self._get_font(38, bold=False)
        s_lines = self._wrap_text(draw, subtext, s_font, MAX_W - 40)
        s_line_h = draw.textbbox((0,0), 'Ag', font=s_font)[3] - draw.textbbox((0,0), 'Ag', font=s_font)[1]
        total_s_height = len(s_lines) * (s_line_h + 10)

        # Start headline at top_pad
        y_extra = self._apply_tag_treatment(draw, img, tag, accent, W, H)
        y = top_pad + y_extra

        # 4. DRAW HEADLINE (word-by-word coloring)
        for line in h_lines:
            bb = draw.textbbox((0,0), line, font=h_font)
            lw = bb[2] - bb[0]
            x_start = (W - lw) // 2
            words = line.split()
            cx = x_start
            for word in words:
                clean = word.strip(".,!?'\"-")
                is_hl = any(clean == hw or clean.startswith(hw) for hw in highlight_words)
                color = accent if is_hl else '#0A0A0A'
                draw.text((cx, y), word, font=h_font, fill=color)
                wb = draw.textbbox((0,0), word, font=h_font)
                sb = draw.textbbox((0,0), ' ', font=h_font)
                cx += (wb[2] - wb[0]) + (sb[2] - sb[0])
            y += line_h + line_gap
            
        y -= line_gap # remove last gap

        # 5. RED RULE
        y += rule_gap
        rule_w = 80
        rule_x0 = (W - rule_w) // 2
        draw.rectangle([rule_x0, y, rule_x0 + rule_w, y + rule_h], fill=accent)

        # 6. SUBTEXT
        y += rule_h + subtext_gap
        for sl in s_lines:
            sb = draw.textbbox((0,0), sl, font=s_font)
            sw = sb[2] - sb[0]
            draw.text(((W - sw) // 2, y), sl, font=s_font, fill='#444444')
            y += s_line_h + 10

        # 7. TAG BRACKET at bottom
        t_font = self._get_font(32, bold=False)
        tag_text = f'[ {tag} ]'
        tb = draw.textbbox((0,0), tag_text, font=t_font)
        draw.text(((W - (tb[2]-tb[0])) // 2, H - tag_bottom - (tb[3]-tb[1])),
                  tag_text, font=t_font, fill='#999999')

        # DATE WATERMARK
        date_font = self._get_font(24, bold=False)
        date_str = datetime.now().strftime('%b %d, %Y').upper()
        draw.text((40, H - 50), date_str, font=date_font, fill='#CCCCCC')

        # 8. SAVE
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path, 'PNG', quality=95)
        
        print(f'[RENDER] {output_path} | {font_size}px | {len(h_lines)} lines | tag={tag}')
        return output_path

    def _apply_tag_treatment(self, draw, img, tag, accent, W, H):
        '''
        Adds tag-specific visual elements to the top/bottom of the canvas.
        Called BEFORE drawing the headline.
        Returns y_offset (how much space the treatment consumed at top).
        '''
        from datetime import datetime
        if tag == 'breaking':
            # Thin red strip at very top (not a bar — just a 8px line)
            draw.rectangle([0, 0, W, 8], fill=accent)
            # BREAKING label top-left in small caps
            label_font = self._get_font(26, bold=True)
            draw.text((40, 20), 'BREAKING NEWS', font=label_font, fill=accent)
            return 65 # extra top padding consumed
        elif tag == 'finance':
            # Thin gold rule at top
            draw.rectangle([0, 0, W, 6], fill=accent)
            # Small market indicator text top-right
            label_font = self._get_font(22, bold=False)
            txt = datetime.now().strftime('%d %b %Y').upper() + ' | MARKETS'
            tb = draw.textbbox((0,0), txt, font=label_font)
            draw.text((W - (tb[2]-tb[0]) - 40, 18), txt, font=label_font, fill='#999999')
            return 55
        elif tag == 'politics':
            # Navy thin rule at top
            draw.rectangle([0, 0, W, 6], fill=accent)
            return 40
        elif tag == 'sports':
            # Thin red rule at top
            draw.rectangle([0, 0, W, 6], fill=accent)
            return 40
        else:
            # Default: just a thin rule
            draw.rectangle([0, 0, W, 4], fill='#CCCCCC')
            return 30

    def _wrap_text(self, draw, text, font, max_width):
        '''Word-wrap text to max_width. Returns list of lines.'''
        words = text.split()
        lines = []
        cur = []
        for w in words:
            cur.append(w)
            bb = draw.textbbox((0,0), ' '.join(cur), font=font)
            if (bb[2] - bb[0]) > max_width:
                cur.pop()
                if cur:
                    lines.append(' '.join(cur))
                cur = [w]
        if cur:
            lines.append(' '.join(cur))
        return lines if lines else [text]

if __name__ == "__main__":
    renderer = ImageRenderer()
    data = {
        "headline": "STOCK MARKET CRASHES AMID GLOBAL SELLOFF",
        "highlight_words": ["CRASHES", "SELLOFF"],
        "subtext": "Global indices plunge 5% as tech stocks see their worst day since 2008.",
        "tag": "finance"
    }
    renderer.render(data, "assets/images/test_render.jpg")
