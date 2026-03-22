# Image Generation — Root Cause Analysis & Fix Guide
## Autonomous AI News System — NA Project

> This guide is based on a full code audit of the uploaded project zip.
> The image files exist on disk (21 PNGs confirmed). The generation code
> works correctly in isolation. The problem is entirely path-related.

---

## Diagnosis Summary

The image generation agent itself is working perfectly. Running it
directly produces valid 1200x630 PNG files. The bug is that
**the wrong file paths are being stored in the database**, so when
`api.py` tries to serve the image it looks in the wrong place and
returns 404. The dashboard then shows a broken icon.

### Confirmed bugs found (4 total)

| # | Severity | File | Line | Problem |
|---|---|---|---|---|
| 1 | CRITICAL | `pipeline/master_pipeline.py` | 58 | Saves relative path `images/123_card.png` to DB |
| 2 | CRITICAL | `pipeline/master_pipeline.py` | 69 | Passes that same relative path to `save_image_record()` |
| 3 | HIGH | `agents/visual_generation_agent.py` | `__init__` | `config_path` default is relative — breaks when called from `api/` |
| 4 | HIGH | `config/branding_layer.py` | `__init__` | Same relative `config_path` default — breaks in subprocesses |

### Why this breaks in production but works in isolation

When you run `python pipeline/master_pipeline.py` from `D:\PROJECTS\NA`,
the current working directory is the project root, so `images/1793_card.png`
resolves correctly to `D:\PROJECTS\NA\images\1793_card.png`.

But when `api.py` runs from `D:\PROJECTS\NA\api\` and calls
`os.path.exists("images/1793_card.png")`, it looks for
`D:\PROJECTS\NA\api\images\1793_card.png` — which does not exist.
The endpoint returns 404. The dashboard shows a broken icon.

The visual generation agent already computes the correct absolute path
internally (`self.images_dir` is set to the absolute path in `__init__`).
The fix is to use that absolute path everywhere instead of the hardcoded
relative string in `master_pipeline.py`.

---

## Fix 1 — master_pipeline.py (CRITICAL — do this first)

Open a fresh Antigravity conversation and paste this prompt:

```
In pipeline/master_pipeline.py, fix the Phase 3 visual generation block.
The current code on line 58 sets:
    output_path = f"images/{article_id}_card.png"
and then passes this relative path to both generate_headline_card() and
save_image_record(). This breaks when the script is run from any directory
other than the project root.

Make these exact changes only:

1) Remove line 58 entirely:
   output_path = f"images/{article_id}_card.png"

2) Change the generate_headline_card() call to NOT pass output_path —
   the agent already builds the correct absolute path internally using
   self.images_dir. Just pass article_id=article_id instead:
   
   actual_path = visual_agent.generate_headline_card(
       headline=article["headline"],
       source=article["source"],
       category=article["category"],
       is_breaking=article["is_breaking"],
       article_id=article_id
   )

3) Change the save_image_record() call to use actual_path (the return
   value from generate_headline_card) instead of output_path:
   
   visual_agent.save_image_record(article_id, actual_path, "headline_card", save_conn)

4) Change os.makedirs("images", exist_ok=True) to use the agent's
   images_dir instead — move it to after VisualGenerationAgent() is
   instantiated:
   os.makedirs(visual_agent.images_dir, exist_ok=True)

Show only the changed Phase 3 block — not the full file.
```

---

## Fix 2 — visual_generation_agent.py config path (HIGH)

In the **same Antigravity conversation**, paste this:

```
In agents/visual_generation_agent.py, fix the config_path default so it
works regardless of which directory the script is called from.

Replace the __init__ signature:
    def __init__(self, config_path="config/brand_config.json"):

With this:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', 'config', 'brand_config.json'
            )
        config_path = os.path.normpath(config_path)

Show only the modified __init__ method.
```

---

## Fix 3 — branding_layer.py config path (HIGH)

In the **same Antigravity conversation**, paste this:

```
In config/branding_layer.py, apply the same absolute path fix to the
__init__ method.

Replace:
    def __init__(self, config_path="config/brand_config.json"):

With:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'brand_config.json'
            )
        config_path = os.path.normpath(config_path)
        self.config = self.load_config(config_path)

Note: branding_layer.py lives inside the config/ folder, so the path
is just brand_config.json relative to __file__, not ../config/brand_config.json.

Show only the modified __init__ method.
```

---

## Fix 4 — Backfill existing articles (run after code fixes)

The 21 PNG files in your images/ folder were generated but their paths
in the database are relative strings like `images/1793_card.png`. These
need to be updated to absolute paths so `api.py` can find them.

Run this from `D:\PROJECTS\NA` in PowerShell after applying Fixes 1-3:

```powershell
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
project_root = os.path.abspath('.')

with conn.cursor() as cur:
    cur.execute('SELECT id, image_path FROM images')
    rows = cur.fetchall()
    updated = 0
    for img_id, path in rows:
        if not os.path.isabs(path):
            abs_path = os.path.normpath(os.path.join(project_root, path))
            cur.execute('UPDATE images SET image_path = %s WHERE id = %s',
                       (abs_path, img_id))
            updated += 1
            print(f'  Updated: {path} -> {abs_path}')

conn.commit()
conn.close()
print(f'Done. Updated {updated} image paths.')
"
```

Expected output: one line per image showing the relative path updated
to its absolute equivalent. After this runs, the API will find all
existing images immediately.

---

## Fix 5 — Verify everything works

Run these checks in order:

**Check 1 — Test the API endpoint directly in your browser:**
```
http://localhost:5000/api/articles/1793/image
```
Should return a PNG image, not a JSON error.

**Check 2 — Check a sample path in the database:**
```sql
SELECT image_path FROM images LIMIT 3;
```
Paths should start with `D:\PROJECTS\NA\images\` — not `images\`.

**Check 3 — Test image generation end-to-end:**
```powershell
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2
from agents.visual_generation_agent import VisualGenerationAgent

agent = VisualGenerationAgent()
print('Config loaded from:', agent.config.get('brand_name'))
print('Images dir:', agent.images_dir)

path = agent.generate_headline_card(
    'Test article headline for verification',
    'Test Source', 'technology', False, article_id=0
)
print('Generated at:', path)
print('File exists:', os.path.exists(path))
print('Is absolute path:', os.path.isabs(path))
"
```

All three checks should pass. If Check 3 shows `Is absolute path: True`,
the fix was applied correctly.

---

## Improvements (apply after fixes)

These are not bugs — the system works after the fixes above. These make
it better.

---

### Improvement 1 — Better font rendering

The default Pillow bitmap font looks pixelated at large sizes. On Windows
you can use system fonts for much sharper text:

```
In agents/visual_generation_agent.py, replace the _get_font() method
with one that tries Windows system fonts before falling back to default:

def _get_font(self, size):
    font_candidates = [
        "C:/Windows/Fonts/arialbd.ttf",   # Arial Bold
        "C:/Windows/Fonts/arial.ttf",      # Arial
        "C:/Windows/Fonts/calibrib.ttf",   # Calibri Bold
        "C:/Windows/Fonts/segoeui.ttf",    # Segoe UI
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                from PIL import ImageFont
                return ImageFont.truetype(font_path, size=size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()

Show only the replacement method.
```

---

### Improvement 2 — Category colour coding

Right now all cards use the same dark blue background from brand_config.
Different categories should have distinct colours so cards are immediately
recognisable in the feed:

```
In agents/visual_generation_agent.py, add a CATEGORY_COLORS dict as a
class constant and use it in generate_headline_card():

CATEGORY_COLORS = {
    "technology": "#0D47A1",
    "business":   "#1B5E20",
    "sports":     "#4A148C",
    "health":     "#880E4F",
    "science":    "#E65100",
    "india":      "#B71C1C",
    "world":      "#004D40",
}

In generate_headline_card(), replace the primary_hex line with:
primary_hex = self.CATEGORY_COLORS.get(
    (category or "").lower(),
    self.config.get("primary_color", "#1E3A8A")
)

Show only the class constant and the changed line in generate_headline_card().
```

---

### Improvement 3 — Thumbnail endpoint for dashboard feed

Currently the full 1200x630 PNG is loaded for every article card in the
feed. With 20 articles per page that is 20 full images loading at once,
which is slow. Add a thumbnail endpoint:

```
Add a new endpoint to api/api.py: GET /api/articles/<id>/thumbnail

It works like the /image endpoint but before sending, resizes the image
to 400x210 pixels using Pillow and sends the resized version. Use
io.BytesIO as an in-memory buffer so no temp file is created:

from PIL import Image
import io

# ... inside the endpoint after confirming file exists:
img = Image.open(image_path)
img.thumbnail((400, 210), Image.LANCZOS)
buf = io.BytesIO()
img.save(buf, format='PNG')
buf.seek(0)
return send_file(buf, mimetype='image/png')

Then in dashboard.py, change the image fetch URL from /image to
/thumbnail for the feed view. Keep /image for the full-size view.

Show only the new endpoint function and the changed URL in dashboard.py.
```

---

### Improvement 4 — Image generation progress in dashboard

The Control Panel currently shows pipeline metrics but not image
generation status. Add a simple image coverage metric:

```
Add one new endpoint to api/api.py: GET /api/images/stats
Returns:
{
  "total_images": int,        -- COUNT(*) FROM images
  "coverage_pct": float,      -- images / summarised_articles * 100
  "latest_image_at": str      -- MAX(created_at) from images
}

Then in dashboard.py page_control(), add a 6th st.metric card below
the existing 5 showing "Image Coverage" as coverage_pct with a % suffix.

Show only the new endpoint and the added st.metric line.
```

---

## Checklist

- [ ] Apply Fix 1 (master_pipeline absolute paths)
- [ ] Apply Fix 2 (visual_generation_agent config path)
- [ ] Apply Fix 3 (branding_layer config path)
- [ ] Run Fix 4 backfill script
- [ ] Verify Fix 5 checks all pass
- [ ] (Optional) Apply Improvement 1 — better fonts
- [ ] (Optional) Apply Improvement 2 — category colours
- [ ] (Optional) Apply Improvement 3 — thumbnails
- [ ] (Optional) Apply Improvement 4 — image coverage metric

Fixes 1-4 are required. Improvements are optional but each takes one
Antigravity call and noticeably improves the dashboard experience.

---

*End of Image Fix Guide*
