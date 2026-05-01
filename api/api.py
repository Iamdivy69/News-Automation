import os
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import threading
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pipeline.master_pipeline import MasterPipeline

# Global lock to prevent overlapping pipeline executions
pipeline_running = threading.Event()

def _run_pipeline_background():
    """Background worker method for the MasterPipeline."""
    try:
        pipeline = MasterPipeline()
        pipeline.run()  # Pipeline internally handles its own database run logging
    except Exception as e:
        print(f"Background pipeline failed: {e}")
    finally:
        pipeline_running.clear()

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Allow requests from React dev server on both Vite (5173) and CRA (3000)
CORS(app, origins=[
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
])

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise ValueError("DATABASE_URL is not set in environment or .env file.")

# SQLAlchemy requires postgresql:// instead of postgres://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    db_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

# Global error handler to catch ALL exceptions and return 500 JSON
@app.errorhandler(Exception)
def handle_exception(e):
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    return jsonify({
        "error": "Internal Server Error",
        "message": str(e)
    }), 500

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@app.route('/api/articles', methods=['GET'])
def get_articles():
    """
    Returns paginated list of articles.
    Query Params:
      page (default 1)
      per_page (default 20)
      status (filter by status, default='summarised')
      category (optional filter)
      search (optional filter)
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', 'summarised')
    category = request.args.get('category')
    search = request.args.get('search')
    
    offset = (page - 1) * per_page
    
    query = """
        SELECT id, headline, source, category, viral_score, is_breaking, status, created_at
        FROM articles
        WHERE status = :status
    """
    params = {"status": status}
    
    if category:
        query += " AND category = :category"
        params["category"] = category
        
    if search:
        query += " AND headline ILIKE :search"
        params["search"] = f"%{search}%"
        
    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    params.update({"limit": per_page, "offset": offset})
    
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        articles = [dict(row) for row in result.mappings()]
        
        # Format datetime for JSON serialization
        for a in articles:
            if a.get('created_at'):
                a['created_at'] = a['created_at'].isoformat()
        
        return jsonify(articles)


@app.route('/api/articles/<int:article_id>', methods=['GET'])
def get_article(article_id):
    """
    Returns a single article with all initial fields plus its 
    summary details joined from the summaries table.
    """
    query = """
        SELECT 
            a.id, a.headline, a.full_text, a.url, a.source, a.category, 
            a.viral_score, a.is_breaking, a.status, a.created_at,
            s.twitter_text, s.linkedin_text, s.instagram_caption, 
            s.facebook_text, s.hashtags, s.tone
        FROM articles a
        LEFT JOIN summaries s ON a.id = s.article_id
        WHERE a.id = :article_id
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query), {"article_id": article_id})
        row = result.mappings().fetchone()
        
        if not row:
            return jsonify({"error": "Article not found"}), 404
            
        row = dict(row)
        summary_fields = ['twitter_text', 'linkedin_text', 'instagram_caption', 'facebook_text', 'hashtags', 'tone']
        
        has_summary = any(row[f] is not None for f in summary_fields)
        
        summary = None
        if has_summary:
            summary = {f: row[f] for f in summary_fields}
            
        article = {k: v for k, v in row.items() if k not in summary_fields}
        article['summary'] = summary
        
        if article.get('created_at'):
            article['created_at'] = article['created_at'].isoformat()
            
        return jsonify(article)


@app.route('/api/articles/<int:article_id>/image', methods=['GET'])
def get_article_image(article_id):
    query = """
        SELECT image_path 
        FROM images 
        WHERE article_id = :article_id 
        ORDER BY created_at DESC 
        LIMIT 1
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), {"article_id": article_id}).fetchone()
        
        if not result or not result[0]:
            return jsonify({"error": "No image found"}), 404
            
        image_path = result[0]
        
        # Fast path: stored path still exists
        if os.path.exists(image_path):
            return send_file(image_path, mimetype='image/png')

        # Slow path: search all date subfolders under images/
        filename = os.path.basename(image_path)
        images_root = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
            'images'
        )
        for entry in sorted(os.scandir(images_root), key=lambda e: e.name, reverse=True):
            if entry.is_dir():
                candidate = os.path.join(entry.path, filename)
                if os.path.exists(candidate):
                    return send_file(candidate, mimetype='image/png')

        return jsonify({"error": "Image file missing from disk", "path": image_path}), 404

@app.route('/api/articles/<int:article_id>/portrait', methods=['GET'])
def get_portrait_image(article_id):
    query = """
        SELECT image_path FROM images
        WHERE article_id = :article_id
          AND image_type = 'portrait'
        ORDER BY created_at DESC LIMIT 1
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), {"article_id": article_id}).fetchone()
        if not result or not result[0]:
            return jsonify({"error": "No portrait image"}), 404
        image_path = result[0]
        if not os.path.exists(image_path):
            return jsonify({"error": "Portrait file missing"}), 404
        return send_file(image_path, mimetype='image/png')


@app.route('/api/articles/<int:article_id>/thumbnail', methods=['GET'])
def get_article_thumbnail(article_id):
    query = """
        SELECT image_path 
        FROM images 
        WHERE article_id = :article_id 
        ORDER BY created_at DESC 
        LIMIT 1
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), {"article_id": article_id}).fetchone()
        
        if not result or not result[0]:
            return jsonify({"error": "No image found"}), 404
            
        image_path = result[0]
        
        if not os.path.exists(image_path):
            return jsonify({"error": "Image file missing from disk", "path": image_path}), 404
            
        from PIL import Image
        import io
        img = Image.open(image_path)
        img.thumbnail((400, 210), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """
    Returns global system statistics.
    """
    with engine.connect() as conn:
        total_articles = conn.execute(text("SELECT COUNT(*) FROM articles")).scalar()
        
        summarised_today = conn.execute(text(
            "SELECT COUNT(*) FROM articles WHERE status = 'summarised' AND created_at >= CURRENT_DATE"
        )).scalar()
        
        breaking_today = conn.execute(text(
            "SELECT COUNT(*) FROM articles WHERE is_breaking = TRUE AND created_at >= CURRENT_DATE"
        )).scalar()
        
        status_res = conn.execute(text("SELECT status, COUNT(*) as count FROM articles GROUP BY status"))
        articles_by_status = {row['status']: row['count'] for row in status_res.mappings() if row['status']}
        
        cat_res = conn.execute(text("SELECT category, COUNT(*) as count FROM articles GROUP BY category"))
        articles_by_category = {row['category']: row['count'] for row in cat_res.mappings() if row['category']}
        
        top_res = conn.execute(text("""
            SELECT source, COUNT(*) as source_count 
            FROM articles 
            WHERE source IS NOT NULL 
            GROUP BY source 
            ORDER BY source_count DESC 
            LIMIT 5
        """))
        top_sources = {row['source']: row['source_count'] for row in top_res.mappings() if row['source']}
        
        return jsonify({
            "total_articles": total_articles,
            "summarised_today": summarised_today,
            "breaking_today": breaking_today,
            "articles_by_status": articles_by_status,
            "articles_by_category": articles_by_category,
            "top_sources": top_sources
        })

@app.route('/api/images/stats', methods=['GET'])
def get_images_stats():
    with engine.connect() as conn:
        total_images = conn.execute(text("SELECT COUNT(*) FROM images")).scalar()
        summarised = conn.execute(text("SELECT COUNT(*) FROM articles WHERE status = 'summarised'")).scalar()
        latest = conn.execute(text("SELECT MAX(created_at) FROM images")).scalar()
        
        coverage = 0.0
        if summarised and summarised > 0:
            coverage = (total_images / summarised) * 100.0
            
        return jsonify({
            "total_images": total_images,
            "coverage_pct": round(coverage, 2),
            "latest_image_at": latest.isoformat() if latest else None
        })


@app.route('/api/health', methods=['GET'])
def get_health():
    """
    Returns health status of PostgreSQL, Ollama, Gemini, Pexels, Cloudinary and current timestamp.
    """
    try:
        health = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "postgresql": "error",
            "ollama": "error",
            "gemini": "error",
            "pexels": "disabled",
            "cloudinary": "disabled"
        }
        
        # Check PostgreSQL
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            health["postgresql"] = "ok"
        except Exception:
            pass
            
        # Check Ollama
        try:
            ollama_host = os.getenv("OLLAMA_HOST", "localhost:11434")
            if "://" not in ollama_host:
                ollama_host = f"http://{ollama_host}"
            resp = requests.get(ollama_host, timeout=3)
            if resp.status_code == 200:
                health["ollama"] = "ok"
        except Exception:
            pass
            
        # Check Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                resp = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}", timeout=3)
                if resp.status_code == 200:
                    health["gemini"] = "ok"
            except Exception:
                pass
                
        # Check Pexels
        pexels_key = os.getenv("PEXELS_API_KEY")
        if pexels_key:
            try:
                resp = requests.get("https://api.pexels.com/v1/search?query=test&per_page=1", 
                                  headers={"Authorization": pexels_key}, timeout=3)
                if resp.status_code == 200:
                    health["pexels"] = "ok"
                else:
                    health["pexels"] = "error"
            except Exception:
                health["pexels"] = "error"

        # Check Cloudinary
        cloudinary_url = os.getenv("CLOUDINARY_URL")
        if cloudinary_url:
            health["cloudinary"] = "ok"
                
        return jsonify(health)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/pipeline/run', methods=['POST'])
def run_pipeline_api():
    if pipeline_running.is_set():
        return jsonify({"status": "busy", "message": "Pipeline already running"}), 409
        
    pipeline_running.set()
    thread = threading.Thread(target=_run_pipeline_background)
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "started", "message": "Pipeline triggered in background"}), 200


@app.route('/api/pipeline/status', methods=['GET'])
def get_pipeline_status():
    try:
        query = """
            SELECT id, run_type, discovered, scored, merged, breaking, 
                   summarised, images_generated, duration_sec, 
                   started_at, finished_at
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT 1
        """
        with engine.connect() as conn:
            result = conn.execute(text(query)).mappings().fetchone()
            
            last_run = None
            if result:
                row = dict(result)
                # Serialize datetime objects securely for JSON
                if row.get('started_at'):
                    row['started_at'] = row['started_at'].isoformat()
                if row.get('finished_at'):
                    row['finished_at'] = row['finished_at'].isoformat()
                last_run = row
                
        return jsonify({
            "is_running": pipeline_running.is_set(),
            "last_run": last_run
        }), 200
        
    except Exception as e:
        return jsonify({"error": "Failed to fetch pipeline status", "details": str(e)}), 500


@app.route('/api/posts/pending', methods=['GET'])
def get_pending_posts():
    try:
        query = """
            SELECT 
                a.id, a.headline, a.source, a.category, a.viral_score, a.is_breaking,
                s.twitter_text, s.linkedin_text, s.instagram_caption,
                s.facebook_text, s.hashtags,
                (SELECT image_path FROM images i 
                 WHERE i.article_id = a.id 
                 ORDER BY i.created_at DESC LIMIT 1) as image_path
            FROM articles a
            JOIN summaries s ON a.id = s.article_id
            WHERE a.status = 'approved'
            AND EXISTS (
                SELECT 1 FROM images i WHERE i.article_id = a.id
            )
            ORDER BY a.viral_score DESC
            LIMIT 50
        """
        with engine.connect() as conn:
            result = conn.execute(text(query))
            articles = [dict(row) for row in result.mappings()]
            
            for article in articles:
                if article.get('image_path'):
                    article['image_url'] = f"/api/articles/{article['id']}/image"
                else:
                    article['image_url'] = None
            
        return jsonify(articles), 200
    except Exception as e:
        return jsonify({"error": "Database error fetching pending posts", "details": str(e)}), 500


@app.route('/api/posts/queued', methods=['GET'])
def get_queued_posts():
    try:
        query = """
            SELECT 
                a.id, a.headline, a.source, a.category, a.viral_score, a.is_breaking,
                s.twitter_text, s.linkedin_text, s.instagram_caption, s.facebook_text, s.hashtags
            FROM articles a
            LEFT JOIN summaries s ON a.id = s.article_id
            WHERE a.status = 'publish_approved'
            ORDER BY a.viral_score DESC
            LIMIT 50
        """
        with engine.connect() as conn:
            result = conn.execute(text(query))
            articles = [dict(row) for row in result.mappings()]
            
        return jsonify(articles), 200
    except Exception as e:
        return jsonify({"error": "Database error fetching queued posts", "details": str(e)}), 500


@app.route('/api/posts/<int:article_id>/approve', methods=['POST'])
def approve_post(article_id):
    try:
        query = "UPDATE articles SET status = 'publish_approved' WHERE id = :id"
        with engine.connect() as conn:
            with conn.begin():
                result = conn.execute(text(query), {"id": article_id})
                if result.rowcount == 0:
                    return jsonify({"error": "Article not found"}), 404

        def _publish_in_background(aid):
            try:
                import sys, os
                sys.path.insert(0, os.path.abspath(
                    os.path.join(os.path.dirname(__file__), '..')
                ))
                from agents.publishing_agent import PublishingAgent
                result = PublishingAgent().publish_article(aid)
                print(f"[BG Publisher] article {aid}: {result}")
            except Exception as e:
                print(f"[BG Publisher] error for article {aid}: {e}")

        threading.Thread(
            target=_publish_in_background,
            args=(article_id,),
            daemon=True
        ).start()

        return jsonify({"status": "approved", "article_id": article_id}), 200
    except Exception as e:
        return jsonify({"error": "Database error approving article", "details": str(e)}), 500


@app.route('/api/pipeline/publish-now', methods=['POST'])
def publish_now():
    def _run():
        try:
            import sys, os
            sys.path.insert(0, os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..')
            ))
            from agents.publishing_agent import PublishingAgent
            result = PublishingAgent().run(limit=20)
            print(f"[Manual Publish] {result}")
        except Exception as e:
            print(f"[Manual Publish] error: {e}")
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "publishing", "message": "Publishing all pending articles in background"}), 200


@app.route('/api/posts/queue', methods=['DELETE'])
def clear_queue():
    try:
        query = "UPDATE articles SET status = 'rejected' WHERE status = 'publish_approved'"
        with engine.connect() as conn:
            with conn.begin():
                result = conn.execute(text(query))
        return jsonify({"status": "cleared", "count": result.rowcount}), 200
    except Exception as e:
        return jsonify({"error": "Failed to clear queue", "details": str(e)}), 500


@app.route('/api/posts/<int:article_id>/reject', methods=['POST'])
def reject_post(article_id):
    try:
        query = "UPDATE articles SET status = 'rejected' WHERE id = :id"
        with engine.connect() as conn:
            with conn.begin():
                result = conn.execute(text(query), {"id": article_id})
                if result.rowcount == 0:
                    return jsonify({"error": "Article not found"}), 404
                    
        return jsonify({"status": "rejected", "article_id": article_id}), 200
    except Exception as e:
        return jsonify({"error": "Database error rejecting article", "details": str(e)}), 500


@app.route('/api/pipeline/history', methods=['GET'])
def get_pipeline_history():
    try:
        query = """
            SELECT id, run_type, discovered, scored, merged, breaking,
                   summarised, images_generated, duration_sec, started_at, finished_at
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT 10
        """
        with engine.connect() as conn:
            result = conn.execute(text(query))
            runs = []
            for row in result.mappings():
                r = dict(row)
                if r.get('started_at'): r['started_at'] = r['started_at'].isoformat()
                if r.get('finished_at'): r['finished_at'] = r['finished_at'].isoformat()
                runs.append(r)
        return jsonify(runs), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch pipeline history", "details": str(e)}), 500


@app.route('/api/insights', methods=['GET'])
def get_insights():
    try:
        query = "SELECT value FROM system_config WHERE key = 'latest_insight_report' LIMIT 1"
        with engine.connect() as conn:
            result = conn.execute(text(query)).fetchone()
            if result:
                return jsonify({"report": result[0]}), 200
            else:
                return jsonify({"report": None}), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch insight report", "details": str(e)}), 500


@app.route('/api/posts/tracker', methods=['GET'])
def get_posts_tracker():
    """
    Returns the 100 most recent posts with joined article and image info
    for use in the platform tracking UI.
    """
    try:
        query = """
            SELECT
                p.id, p.platform, p.posted_at, p.status, p.post_id,
                a.id AS article_id, a.headline, a.source, a.category,
                a.viral_score, a.is_breaking,
                i.image_path
            FROM posts p
            JOIN articles a ON p.article_id = a.id
            LEFT JOIN images i ON a.id = i.article_id
            ORDER BY p.posted_at DESC
            LIMIT 100
        """
        with engine.connect() as conn:
            rows = conn.execute(text(query)).mappings().fetchall()
            result = []
            for row in rows:
                r = dict(row)
                if r.get('posted_at'):
                    r['posted_at'] = r['posted_at'].isoformat()
                result.append(r)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch tracker data", "details": str(e)}), 500


@app.route('/api/posts/tracker/stats', methods=['GET'])
def get_posts_tracker_stats():
    """
    Returns aggregate posting statistics for the tracking dashboard.
    """
    try:
        with engine.connect() as conn:
            total_posted = conn.execute(
                text("SELECT COUNT(*) FROM posts WHERE status = 'published'")
            ).scalar() or 0

            platform_rows = conn.execute(
                text("SELECT platform, COUNT(*) AS n FROM posts WHERE status = 'published' GROUP BY platform")
            ).mappings().fetchall()
            posted_by_platform = {r['platform']: r['n'] for r in platform_rows}

            posted_today = conn.execute(
                text("SELECT COUNT(*) FROM posts WHERE status = 'published' AND posted_at >= CURRENT_DATE")
            ).scalar() or 0

            last_post_at_raw = conn.execute(
                text("SELECT MAX(posted_at) FROM posts WHERE status = 'published'")
            ).scalar()
            last_post_at = last_post_at_raw.isoformat() if last_post_at_raw else None

            total_rows = conn.execute(
                text("SELECT COUNT(*) FROM posts")
            ).scalar() or 0
            failed_rows = conn.execute(
                text("SELECT COUNT(*) FROM posts WHERE status = 'failed'")
            ).scalar() or 0
            success_rate = round(
                (total_posted / (total_posted + failed_rows) * 100) if (total_posted + failed_rows) > 0 else 0.0,
                2
            )

        return jsonify({
            "total_posted": total_posted,
            "posted_by_platform": posted_by_platform,
            "posted_today": posted_today,
            "last_post_at": last_post_at,
            "success_rate": success_rate,
        }), 200
    except Exception as e:
        return jsonify({"error": "Failed to fetch tracker stats", "details": str(e)}), 500

@app.route('/api/pipeline/stages', methods=['GET'])
def get_pipeline_stages():
    try:
        query = """
            SELECT status, COUNT(*) as cnt FROM articles GROUP BY status
        """
        with engine.connect() as conn:
            result = conn.execute(text(query)).mappings().fetchall()
            
        stages = {
            "raw": 0, "approved": 0, "ranked": 0, "approved_unique": 0,
            "top30_selected": 0, "discarded": 0, "summarised": 0,
            "image_ready": 0, "published": 0, "failed": 0
        }
        for row in result:
            s = row['status']
            if s in stages:
                stages[s] = row['cnt']
        return jsonify(stages), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/articles/top30', methods=['GET'])
def get_top30():
    try:
        query = """
            SELECT id, headline, source, viral_score, status, category,
                   captions, image_url, processing_stage
            FROM articles
            WHERE top_30_selected = TRUE
            ORDER BY viral_score DESC
        """
        with engine.connect() as conn:
            result = conn.execute(text(query)).mappings().fetchall()
        return jsonify([dict(r) for r in result]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/articles/<int:article_id>', methods=['PATCH'])
def update_article(article_id):
    try:
        data = request.json
        headline = data.get("headline")
        captions = data.get("captions")
        
        updates = []
        params = {"id": article_id}
        if headline is not None:
            updates.append("headline = :headline")
            params["headline"] = headline
        if captions is not None:
            import json
            updates.append("captions = :captions")
            params["captions"] = json.dumps(captions)
            
        if not updates:
            return jsonify({"error": "No valid fields provided"}), 400
            
        updates.append("processing_stage = 'manually_edited'")
        
        query = f"UPDATE articles SET {', '.join(updates)} WHERE id = :id"
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text(query), params)
                
        return jsonify({"status": "success", "article_id": article_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/articles/<int:article_id>/regenerate-image', methods=['POST'])
def regenerate_image(article_id):
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM articles WHERE id = :id"), {"id": article_id}).mappings().fetchone()
            
        if not row:
            return jsonify({"error": "Article not found"}), 404
            
        art = dict(row)
        
        import sys, os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from agents.headline_generator import HeadlineGenerator
        from agents.image_renderer import ImageRenderer
        
        hg = HeadlineGenerator()
        headline_data = hg.generate({
            "title": art.get("headline", ""),
            "summary": art.get("summary") or art.get("full_text", ""),
            "category": art.get("category", ""),
            "is_breaking": art.get("is_breaking", False)
        })
        
        renderer = ImageRenderer()
        output_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'images', datetime.now().strftime('%Y-%m-%d'))
        os.makedirs(output_dir, exist_ok=True)
        filename = f"visual_{article_id}_{int(datetime.now().timestamp())}.png"
        local_path = os.path.join(output_dir, filename)
        
        render_data = headline_data.copy()
        render_data.update(art)
        
        img_path = renderer.render(render_data, local_path)
        
        cloudinary_url = os.environ.get("CLOUDINARY_URL")
        final_url = img_path
        if cloudinary_url:
            try:
                import cloudinary
                import cloudinary.uploader
                upload_res = cloudinary.uploader.upload(img_path)
                final_url = upload_res.get("secure_url")
            except Exception as e:
                print(f"Cloudinary upload failed: {e}")
                
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("""
                    UPDATE articles 
                    SET image_url = :url, image_source = 'gemini_template', image_prompt = :prompt
                    WHERE id = :id
                """), {"url": final_url, "prompt": headline_data.get("headline", ""), "id": article_id})
                
        return jsonify({
            "image_url": final_url,
            "image_source": "gemini_template",
            "headline_data": headline_data
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/articles/<int:article_id>/approve', methods=['POST'])
def approve_article_top30(article_id):
    try:
        query = "UPDATE articles SET top_30_selected = TRUE, status = 'top30_selected' WHERE id = :id"
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text(query), {"id": article_id})
        return jsonify({"status": "approved", "article_id": article_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/articles/<int:article_id>/discard', methods=['POST'])
def discard_article(article_id):
    try:
        query = "UPDATE articles SET top_30_selected = FALSE, status = 'discarded' WHERE id = :id"
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text(query), {"id": article_id})
        return jsonify({"status": "discarded", "article_id": article_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/pipeline/logs', methods=['GET'])
def get_pipeline_logs():
    try:
        query = """
            SELECT stage, started_at, completed_at, articles_in, articles_out, error_message as errors
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT 50
        """
        with engine.connect() as conn:
            result = conn.execute(text(query)).mappings().fetchall()
            logs = []
            for row in result:
                r = dict(row)
                if r.get('started_at'): r['started_at'] = r['started_at'].isoformat()
                if r.get('completed_at'): r['completed_at'] = r['completed_at'].isoformat()
                logs.append(r)
        return jsonify(logs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Run globally on port 5000
    app.run(host='0.0.0.0', port=5000)
