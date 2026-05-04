#!/usr/bin/env python3
"""
Re-generate images for all articles that already exist in DB.
Run after upgrading the image renderer.
Usage: python scripts/regen_all_images.py
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

import psycopg2, psycopg2.extras
from datetime import datetime
from agents.headline_generator import HeadlineGenerator
from agents.image_renderer import ImageRenderer

conn = psycopg2.connect(os.environ['DATABASE_URL'])
hgen = HeadlineGenerator()
renderer = ImageRenderer()

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
images_dir = os.path.join(project_root, 'output', 'images', datetime.now().strftime('%Y-%m-%d'))
os.makedirs(images_dir, exist_ok=True)

# Get all articles (not just top30 — regenerate everything that has been processed)
with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
    cur.execute("""
        SELECT id, headline, full_text, summary, category, is_breaking, viral_score
        FROM articles
        WHERE status IN ('published', 'image_ready', 'image_failed', 'summarised')
        ORDER BY viral_score DESC
    """)
    articles = cur.fetchall()

print(f"Re-generating images for {len(articles)} articles...")

ok = fail = 0
for art in articles:
    try:
        art = dict(art)
        hdata = hgen.generate({
            'title': art['headline'] or '',
            'summary': art['summary'] or art['full_text'] or '',
            'category': art['category'] or '',
            'is_breaking': art['is_breaking'] or False,
        })
        
        fname = f"visual_{art['id']}_{int(datetime.now().timestamp())}.png"
        path = os.path.join(images_dir, fname)
        
        renderer.render({**art, **hdata}, path)
        
        api_url = f"/api/articles/{art['id']}/image"
        
        with conn.cursor() as c:
            c.execute("""
                UPDATE articles
                SET image_url='%s', image_source='gemini_template', image_prompt='%s'
                WHERE id=%s
            """ % (api_url, hdata.get('headline','').replace("'","''"), art['id']))
            
            c.execute("""
                INSERT INTO images (article_id, image_path, image_type)
                VALUES (%s, %s, 'portrait') ON CONFLICT DO NOTHING
            """, (art['id'], path))
            
        conn.commit()
        print(f" OK: article {art['id']} — {hdata['headline']}")
        ok += 1
    except Exception as e:
        conn.rollback()
        print(f" FAIL: article {art['id']} — {e}")
        fail += 1

conn.close()

print(f"\nComplete: {ok} OK, {fail} failed")
print("Refresh the Feed page — all images should now show the new style.")
