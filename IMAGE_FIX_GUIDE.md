# Image Generation Fix Guide
## Autonomous AI News System — Phase 6 Debug

> Two problems identified from the dashboard screenshot.
> Fix them in order. Do not skip steps.

---

## Problem Summary

| # | Problem | Symptom | File |
|---|---|---|---|
| 1 | Deprecated parameter | Yellow warning bar in dashboard | `dashboard/dashboard.py` |
| 2 | Broken image icon | Tiny icon + "0" text, no image renders | `agents/visual_generation_agent.py` + `api/api.py` + `dashboard/dashboard.py` |

---

## Fix 1 — Deprecated Parameter (30 seconds)

Open `dashboard/dashboard.py`. Find this exact line:

```python
st.image(img_url, caption="Generated visual card", use_column_width=True)
```

Replace with:

```python
st.image(img_url, caption="Generated visual card", use_container_width=True)
```

No Antigravity needed. One word change. Done.

---

## Fix 2 — Absolute Paths in VisualGenerationAgent

**Why images are not generating:** When `api.py` or `master_pipeline.py`
runs from a different working directory than the project root, the relative
path `"images/123_card.png"` resolves to the wrong location. The file gets
saved somewhere random or the save fails silently.

Open a fresh Antigravity conversation and paste this prompt exactly:

---

### ANTIGRAVITY PROMPT — Fix 1: Absolute Paths

```
In agents/visual_generation_agent.py, fix the file path handling so
images always save to the correct location regardless of which directory
the script is run from. Make these exact changes:

1) In __init__, add:
   self.project_root = os.path.abspath(
       os.path.join(os.path.dirname(__file__), '..')
   )
   self.images_dir = os.path.join(self.project_root, 'images')
   os.makedirs(self.images_dir, exist_ok=True)

2) In generate_headline_card(), ignore the output_path parameter
   entirely. Instead build the path internally as:
   output_path = os.path.join(self.images_dir, f"{article_id}_card.png")
   where article_id is extracted from the headline or passed as a new
   optional parameter article_id=None. If article_id is None, use a
   timestamp: output_path = os.path.join(self.images_dir,
   f"card_{int(time.time())}.png")

3) In save_image_record(), store the absolute path (output_path as
   built above) in the database — not whatever was passed in.

Show only the modified __init__ method signature and body, the changed
lines in generate_headline_card(), and the changed line in
save_image_record(). Do not rewrite the full file.
```

---

## Fix 3 — Flask Image Endpoint

**Why the broken icon appears:** The endpoint returns a 404 JSON response
when the image file is missing, but `st.image()` receives any response
body and tries to render it as an image — producing the broken icon.

In the **same Antigravity conversation**, paste this prompt:

---

### ANTIGRAVITY PROMPT — Fix 2: Flask send_file

```
In api/api.py, rewrite only the GET /api/articles/<id>/image endpoint.
The new version must:

1) Add send_file to the flask import line at the top of the file.

2) Query the images table for the most recent image for article_id
   ordered by created_at DESC LIMIT 1.

3) If no database row found:
   return jsonify({"error": "No image found"}), 404

4) If database row found but os.path.exists(image_path) is False:
   return jsonify({"error": "Image file missing from disk",
                   "path": image_path}), 404

5) If file exists:
   return send_file(image_path, mimetype='image/png')

Show only the updated import line and the complete replacement
endpoint function. Nothing else.
```

---

## Fix 4 — Dashboard Image Display

**Why the broken icon appears in Streamlit:** `st.image()` with a URL
does not check the HTTP status code before rendering. Passing a 404 URL
produces a broken icon. Fix it by fetching the bytes manually first.

In the **same Antigravity conversation**, paste this prompt:

---

### ANTIGRAVITY PROMPT — Fix 3: Dashboard Image Fetch

```
In dashboard/dashboard.py, inside the expander block in page_feed(),
replace the entire image display section (the try/except block that
calls st.image with the img_url) with this pattern:

try:
    img_resp = requests.get(
        f"http://localhost:5000/api/articles/{a['id']}/image",
        timeout=3
    )
    if img_resp.status_code == 200:
        from io import BytesIO
        st.image(
            BytesIO(img_resp.content),
            caption="Generated visual card",
            use_container_width=True
        )
    else:
        st.caption("Visual card not yet generated.")
except Exception:
    pass

Show only this replacement block and the exact line it replaces.
Nothing else.
```

---

## Fix 5 — Backfill Images for Existing Articles

After applying all three code fixes above, run this once from your
project root to generate images for articles that were summarised
before Phase 6 was added. These articles exist in the database but
have no corresponding image file.

Open PowerShell in `D:\PROJECTS\NA` and run:

```powershell
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2
from agents.visual_generation_agent import VisualGenerationAgent

conn = psycopg2.connect(os.environ['DATABASE_URL'])
agent = VisualGenerationAgent()

with conn.cursor() as cur:
    cur.execute('''
        SELECT a.id, a.headline, a.source, a.category, a.is_breaking
        FROM articles a
        LEFT JOIN images i ON a.id = i.article_id
        WHERE a.status = 'summarised' AND i.id IS NULL
        LIMIT 20
    ''')
    articles = cur.fetchall()

print(f'Found {len(articles)} articles needing images')

for row in articles:
    aid, headline, source, category, is_breaking = row
    try:
        path = agent.generate_headline_card(
            headline or '',
            source or '',
            category or '',
            is_breaking or False,
            article_id=aid
        )
        agent.save_image_record(aid, path, 'headline_card', conn)
        conn.commit()
        print(f'  [OK] Article {aid}: {(headline or \"\")[:50]}')
    except Exception as e:
        print(f'  [FAIL] Article {aid}: {e}')

conn.close()
print('Backfill complete.')
"
```

Expected output: one `[OK]` line per article. If you see `[FAIL]`
lines, paste the exact error into Antigravity using the prompt below.

---

## Fix 6 — If Images Still Not Appearing After Backfill

Run this diagnostic SQL to confirm the database and file system agree:

```sql
SELECT
    i.article_id,
    i.image_path,
    a.headline
FROM images i
JOIN articles a ON i.article_id = a.id
ORDER BY i.created_at DESC
LIMIT 5;
```

Then verify those files actually exist on disk:

```powershell
# Replace 123 with an actual article_id from the SQL result above
Test-Path "D:\PROJECTS\NA\images\123_card.png"
```

If SQL returns rows but `Test-Path` returns `False`, the path stored in
the database is wrong (relative instead of absolute). This means Fix 2
was not applied correctly — reapply the absolute path prompt above.

If SQL returns no rows at all, the backfill script did not run
successfully. Check the `[FAIL]` output for the error message.

---

## Universal Debug Prompt

If any fix produces a Python error, paste this into a fresh
Antigravity conversation:

```
I am fixing image generation in an autonomous news system on Python 3.13
Windows. This exact code produced this exact error. Fix only the error —
do not refactor or rewrite unrelated code. Return only the corrected
lines plus one sentence explaining the root cause.

Code: [PASTE THE FAILING CODE BLOCK]
Error: [PASTE THE EXACT ERROR MESSAGE]
```

---

## Verification Checklist

After all fixes are applied:

- [ ] No yellow deprecation warning in dashboard
- [ ] `python -c "import agents.visual_generation_agent"` runs without error
- [ ] Backfill script prints at least one `[OK]` line
- [ ] `GET http://localhost:5000/api/articles/1/image` returns a PNG in browser
- [ ] Dashboard expander shows the image card below the hashtags
- [ ] Breaking news articles show the red BREAKING banner on their image card

All 6 checked = Phase 6 fully working. Ready for Phase 7 Control Panel.

---

*End of Fix Guide*
