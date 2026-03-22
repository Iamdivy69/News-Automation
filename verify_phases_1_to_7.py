"""
================================================================
  Autonomous News System — Phase Verification Script (1 to 7)
  Run from project root: D:\\PROJECTS\\NA
  Command: python verify_phases_1_to_7.py
================================================================
"""

import os
import sys
import json
import time
import subprocess
import importlib
from datetime import datetime, timezone, timedelta

# ── colour helpers ────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(label):
    print(f"  {GREEN}[PASS]{RESET} {label}")

def fail(label, reason=""):
    r = f" — {reason}" if reason else ""
    print(f"  {RED}[FAIL]{RESET} {label}{r}")

def warn(label, reason=""):
    r = f" — {reason}" if reason else ""
    print(f"  {YELLOW}[WARN]{RESET} {label}{r}")

def header(phase, title):
    bar = "─" * 56
    print(f"\n{CYAN}{BOLD}{bar}{RESET}")
    print(f"{CYAN}{BOLD}  Phase {phase}: {title}{RESET}")
    print(f"{CYAN}{BOLD}{bar}{RESET}")

passed = 0
failed = 0

def record(success):
    global passed, failed
    if success:
        passed += 1
    else:
        failed += 1
    return success

# ── load .env early ───────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print(f"{YELLOW}[WARN]{RESET} python-dotenv not installed — reading env vars directly")

# ensure project root is importable
sys.path.insert(0, os.path.abspath("."))


# ════════════════════════════════════════════════════════════
#  PHASE 1 — FOUNDATION
# ════════════════════════════════════════════════════════════
header(1, "Foundation & Setup")

# 1-A Python version
import platform
ver = sys.version_info
if ver >= (3, 11):
    ok(f"Python {ver.major}.{ver.minor}.{ver.micro} (>= 3.11)")
    record(True)
else:
    fail(f"Python {ver.major}.{ver.minor} — need 3.11+")
    record(False)

# 1-B Required packages
PACKAGES = [
    "feedparser", "newspaper", "keybert", "celery",
    "psycopg2", "PIL", "requests", "tweepy",
    "streamlit", "flask", "sklearn", "humanize",
    "sqlalchemy", "dotenv",
]
all_pkgs = True
for pkg in PACKAGES:
    try:
        importlib.import_module(pkg)
    except ImportError:
        fail(f"Package missing: {pkg}")
        record(False)
        all_pkgs = False
if all_pkgs:
    ok(f"All {len(PACKAGES)} required packages importable")
    record(True)

# 1-C Ollama reachable
try:
    import requests as req
    r = req.get("http://localhost:11434/api/tags", timeout=4)
    models = [m["name"] for m in r.json().get("models", [])]
    mistral_found = any("mistral" in m for m in models)
    if mistral_found:
        ok(f"Ollama running — mistral model found ({', '.join(m for m in models if 'mistral' in m)})")
        record(True)
    else:
        warn("Ollama running but mistral not pulled", f"models: {models}")
        record(False)
except Exception as e:
    fail("Ollama unreachable", str(e))
    record(False)

# 1-D PostgreSQL
DB_URL = os.environ.get("DATABASE_URL", "")
pg_conn = None
try:
    import psycopg2
    pg_conn = psycopg2.connect(DB_URL)
    pg_conn.autocommit = True
    with pg_conn.cursor() as cur:
        cur.execute("SELECT version()")
        ver_str = cur.fetchone()[0].split(",")[0]
    ok(f"PostgreSQL connected — {ver_str}")
    record(True)
except Exception as e:
    fail("PostgreSQL connection failed", str(e))
    record(False)

# 1-E Redis
try:
    import redis
    r_client = redis.Redis(host="localhost", port=6379)
    r_client.ping()
    ok("Redis ping successful")
    record(True)
except Exception as e:
    fail("Redis unreachable", str(e))
    record(False)

# 1-F .env file present
if os.path.exists(".env"):
    ok(".env file found")
    record(True)
else:
    fail(".env file missing from project root")
    record(False)


# ════════════════════════════════════════════════════════════
#  PHASE 2 — NEWS DISCOVERY
# ════════════════════════════════════════════════════════════
header(2, "News Discovery Agent")

# 2-A Tables exist
REQUIRED_TABLES = [
    "articles", "feed_sources", "error_logs",
    "trending_keywords", "story_clusters", "system_config",
    "summaries", "images", "posts",
]
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            existing = {r[0] for r in cur.fetchall()}
        missing = [t for t in REQUIRED_TABLES if t not in existing]
        if not missing:
            ok(f"All {len(REQUIRED_TABLES)} required tables exist")
            record(True)
        else:
            fail(f"Missing tables: {missing}")
            record(False)
    except Exception as e:
        fail("Could not query tables", str(e))
        record(False)
else:
    warn("Skipped table check — no DB connection")
    record(False)

# 2-B Feed sources seeded
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM feed_sources WHERE active = TRUE")
            count = cur.fetchone()[0]
        if count >= 40:
            ok(f"Feed sources: {count} active feeds (>= 40)")
            record(True)
        else:
            fail(f"Only {count} active feeds — expected >= 40")
            record(False)
    except Exception as e:
        fail("Could not count feed sources", str(e))
        record(False)

# 2-C NewsDiscoveryAgent importable
try:
    from agents.news_discovery_agent import NewsDiscoveryAgent
    agent = NewsDiscoveryAgent()
    ok("NewsDiscoveryAgent imported and instantiated")
    record(True)
except Exception as e:
    fail("NewsDiscoveryAgent import failed", str(e))
    record(False)

# 2-D Articles exist in DB
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM articles")
            total = cur.fetchone()[0]
            cur.execute("SELECT MAX(created_at) FROM articles")
            latest = cur.fetchone()[0]
        if total > 0:
            age = (datetime.now(timezone.utc) - latest).total_seconds() / 3600 if latest else 999
            ok(f"Articles in DB: {total:,} total, latest {age:.1f}h ago")
            record(True)
            if age > 2:
                warn(f"Latest article is {age:.1f}h old — pipeline may not have run recently")
        else:
            fail("No articles in database")
            record(False)
    except Exception as e:
        fail("Could not count articles", str(e))
        record(False)

# 2-E Recency filter check
try:
    from agents.news_discovery_agent import NewsDiscoveryAgent
    a = NewsDiscoveryAgent()
    import time as _time
    now_struct = _time.gmtime()
    old_struct = _time.gmtime(_time.time() - 86400 * 3)   # 3 days ago
    assert a.is_recent(now_struct, hours=48) is True
    assert a.is_recent(old_struct, hours=48) is False
    assert a.is_recent(None, hours=48) is True
    ok("is_recent() filter works correctly (fresh/old/None)")
    record(True)
except Exception as e:
    fail("is_recent() logic error", str(e))
    record(False)


# ════════════════════════════════════════════════════════════
#  PHASE 3 — AI INTELLIGENCE LAYER
# ════════════════════════════════════════════════════════════
header(3, "AI Intelligence Layer")

# 3-A ViralScoreEngine — no random
try:
    from agents.viral_score_engine import ViralScoreEngine
    engine = ViralScoreEngine()
    sample = {"headline": "Breaking: Major flood hits city", "source": "BBC",
               "full_text": "A major flood...", "published_date": datetime.now(timezone.utc),
               "category": "world"}
    scores = [engine.score(sample) for _ in range(5)]
    if len(set(scores)) == 1:
        ok(f"ViralScoreEngine is deterministic — score={scores[0]}/100")
        record(True)
    else:
        fail(f"ViralScoreEngine returns random scores: {scores}")
        record(False)
except Exception as e:
    fail("ViralScoreEngine error", str(e))
    record(False)

# 3-B Breaking detection
try:
    from agents.viral_score_engine import ViralScoreEngine
    e2 = ViralScoreEngine()
    assert e2.is_breaking("BREAKING: Earthquake hits coast") is True
    assert e2.is_breaking("Scientists discover new planet") is False
    ok("is_breaking() detects urgent headlines correctly")
    record(True)
except Exception as e:
    fail("is_breaking() logic error", str(e))
    record(False)

# 3-C Viral scores in DB
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM articles WHERE viral_score > 0")
            scored = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM articles WHERE is_breaking = TRUE")
            breaking = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM articles WHERE status = 'approved'")
            approved = cur.fetchone()[0]
        ok(f"Scored articles: {scored:,} | Breaking: {breaking} | Approved: {approved}")
        record(True)
    except Exception as e:
        fail("Could not query intelligence data", str(e))
        record(False)

# 3-D DuplicateMerger importable
try:
    from agents.duplicate_merger import DuplicateMerger
    DuplicateMerger()
    ok("DuplicateMerger imported and instantiated")
    record(True)
except Exception as e:
    fail("DuplicateMerger import failed", str(e))
    record(False)

# 3-E Story clusters created
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM story_clusters")
            clusters = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM articles WHERE status = 'merged'")
            merged = cur.fetchone()[0]
        ok(f"Story clusters: {clusters} | Merged articles: {merged}")
        record(True)
    except Exception as e:
        fail("Could not query cluster data", str(e))
        record(False)


# ════════════════════════════════════════════════════════════
#  PHASE 4 — SUMMARISATION
# ════════════════════════════════════════════════════════════
header(4, "Summarisation Agent")

# 4-A SummarisationAgent importable
try:
    from agents.summarisation_agent import SummarisationAgent
    SummarisationAgent()
    ok("SummarisationAgent imported and instantiated")
    record(True)
except Exception as e:
    fail("SummarisationAgent import failed", str(e))
    record(False)

# 4-B Summaries in DB
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM summaries")
            total_s = cur.fetchone()[0]
            cur.execute("""
                SELECT COUNT(*) FROM summaries
                WHERE twitter_text IS NOT NULL
                  AND linkedin_text IS NOT NULL
                  AND instagram_caption IS NOT NULL
            """)
            complete = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM summaries WHERE is_branded = TRUE")
            branded = cur.fetchone()[0]
        ok(f"Summaries: {total_s} total | {complete} complete (all 4 platforms) | {branded} branded")
        if complete == 0:
            warn("No complete summaries yet — run MasterPipeline with Ollama running")
        record(total_s > 0)
    except Exception as e:
        fail("Could not query summaries", str(e))
        record(False)

# 4-C Quality gate check (spot-check one summary)
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("""
                SELECT twitter_text, linkedin_text, instagram_caption, facebook_text
                FROM summaries
                WHERE twitter_text IS NOT NULL
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cur.fetchone()
        if row:
            issues = []
            for i, text in enumerate(row):
                if text and len(text) < 40:
                    issues.append(f"field {i} too short ({len(text)} chars)")
                if text and "as an ai" in text.lower():
                    issues.append(f"field {i} contains AI disclaimer")
            if not issues:
                ok("Latest summary passes quality gate checks")
                record(True)
            else:
                warn(f"Summary quality issues: {issues}")
                record(False)
        else:
            warn("No summaries to quality-check")
            record(False)
    except Exception as e:
        fail("Quality gate check error", str(e))
        record(False)

# 4-D Summarised article count
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM articles WHERE status = 'summarised'")
            count = cur.fetchone()[0]
        if count > 0:
            ok(f"Articles with status='summarised': {count}")
            record(True)
        else:
            fail("No articles with status='summarised'")
            record(False)
    except Exception as e:
        fail("Could not count summarised articles", str(e))
        record(False)


# ════════════════════════════════════════════════════════════
#  PHASE 5 — BRANDING LAYER
# ════════════════════════════════════════════════════════════
header(5, "Branding Layer")

# 5-A brand_config.json exists and valid
BRAND_FIELDS = [
    "brand_name", "tagline", "primary_color", "accent_color",
    "background_color", "font_name", "logo_path", "signature",
    "tone_keywords", "banned_words", "posting_style", "hashtag_prefix"
]
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "config", "brand_config.json")
try:
    with open(config_path) as f:
        brand = json.load(f)
    missing_fields = [k for k in BRAND_FIELDS if k not in brand]
    if not missing_fields:
        ok(f"brand_config.json valid — brand: '{brand.get('brand_name')}'")
        record(True)
    else:
        fail(f"brand_config.json missing fields: {missing_fields}")
        record(False)
except FileNotFoundError:
    fail("brand_config.json not found at config/brand_config.json")
    record(False)
except json.JSONDecodeError as e:
    fail("brand_config.json is invalid JSON", str(e))
    record(False)

# 5-B BrandingLayer importable
try:
    from config.branding_layer import BrandingLayer
    bl = BrandingLayer()
    ok(f"BrandingLayer imported — brand: '{bl.config.get('brand_name')}'")
    record(True)
except Exception as e:
    fail("BrandingLayer import failed", str(e))
    record(False)

# 5-C apply_tone works
try:
    from config.branding_layer import BrandingLayer
    bl2 = BrandingLayer()
    result = bl2.apply_tone("This is a shocking and unbelievable story.", "twitter")
    has_banned = any(w in result.lower() for w in ["shocking", "unbelievable"])
    has_sig = bl2.config.get("signature", "") in result
    if not has_banned and has_sig:
        ok("apply_tone() strips banned words and appends signature")
        record(True)
    else:
        issues = []
        if has_banned: issues.append("banned words not removed")
        if not has_sig: issues.append("signature not appended")
        fail(f"apply_tone() issues: {', '.join(issues)}")
        record(False)
except Exception as e:
    fail("apply_tone() error", str(e))
    record(False)

# 5-D Branded summaries in DB
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM summaries WHERE is_branded = TRUE")
            count = cur.fetchone()[0]
        if count > 0:
            ok(f"Branded summaries in DB: {count}")
            record(True)
        else:
            warn("No branded summaries yet — run MasterPipeline to populate")
            record(False)
    except Exception as e:
        fail("Could not count branded summaries", str(e))
        record(False)


# ════════════════════════════════════════════════════════════
#  PHASE 6 — VISUAL GENERATION
# ════════════════════════════════════════════════════════════
header(6, "Visual Generation Agent")

# 6-A VisualGenerationAgent importable
try:
    from agents.visual_generation_agent import VisualGenerationAgent
    vga = VisualGenerationAgent()
    ok(f"VisualGenerationAgent imported — images_dir: {vga.images_dir}")
    record(True)
except Exception as e:
    fail("VisualGenerationAgent import failed", str(e))
    record(False)

# 6-B images/ directory exists and has files
try:
    from agents.visual_generation_agent import VisualGenerationAgent
    vga2 = VisualGenerationAgent()
    images_dir = vga2.images_dir
    if os.path.isdir(images_dir):
        pngs = [f for f in os.listdir(images_dir) if f.endswith(".png")]
        if pngs:
            ok(f"images/ directory has {len(pngs)} PNG files")
            record(True)
        else:
            warn("images/ directory exists but is empty — run MasterPipeline")
            record(False)
    else:
        fail(f"images/ directory not found at {images_dir}")
        record(False)
except Exception as e:
    fail("Could not check images directory", str(e))
    record(False)

# 6-C Generate a test card
try:
    from agents.visual_generation_agent import VisualGenerationAgent
    from PIL import Image as PILImage
    vga3 = VisualGenerationAgent()
    test_path = vga3.generate_headline_card(
        headline="Verification test: AI news system running successfully",
        source="VerifyScript",
        category="technology",
        is_breaking=False,
        article_id=0
    )
    img = PILImage.open(test_path)
    assert img.size == (1200, 630), f"Wrong size: {img.size}"
    file_size = os.path.getsize(test_path)
    ok(f"Test card generated — 1200x630, {file_size//1024}KB, path is absolute: {os.path.isabs(test_path)}")
    record(True)
    # Clean up test file
    if "0_card.png" in test_path:
        os.remove(test_path)
except Exception as e:
    fail("Test card generation failed", str(e))
    record(False)

# 6-D Config path is absolute (the critical bug fix)
try:
    from agents.visual_generation_agent import VisualGenerationAgent
    orig_dir = os.getcwd()
    os.chdir(os.path.join(orig_dir, "api"))
    try:
        vga4 = VisualGenerationAgent()
        ok("VisualGenerationAgent loads from api/ subdirectory (absolute config path)")
        record(True)
    except FileNotFoundError:
        fail("VisualGenerationAgent config path bug not fixed — fails from api/ dir")
        record(False)
    finally:
        os.chdir(orig_dir)
except Exception as e:
    warn(f"Could not test subdirectory config loading: {e}")
    record(False)

# 6-E Images in DB with absolute paths
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM images")
            total_imgs = cur.fetchone()[0]
            cur.execute("SELECT image_path FROM images ORDER BY created_at DESC LIMIT 5")
            sample_paths = [r[0] for r in cur.fetchall()]
        relative_paths = [p for p in sample_paths if p and not os.path.isabs(p)]
        if total_imgs > 0 and not relative_paths:
            ok(f"Images table: {total_imgs} records, all paths absolute")
            record(True)
        elif relative_paths:
            fail(f"Relative paths still in DB: {relative_paths[:2]} — run backfill script")
            record(False)
        else:
            warn("No image records in DB yet — run MasterPipeline")
            record(False)
    except Exception as e:
        fail("Could not query images table", str(e))
        record(False)

# 6-F Pexels API key present
pexels_key = os.environ.get("PEXELS_API_KEY", "")
if pexels_key and len(pexels_key) > 10:
    ok(f"PEXELS_API_KEY set ({len(pexels_key)} chars)")
    record(True)
else:
    warn("PEXELS_API_KEY not set — Pexels photos disabled, using solid-color fallback")
    record(False)


# ════════════════════════════════════════════════════════════
#  PHASE 7 — CONTROL PANEL
# ════════════════════════════════════════════════════════════
header(7, "Control Panel (API + Dashboard)")

# 7-A Flask API reachable
try:
    import requests as req
    r = req.get("http://localhost:5000/api/health", timeout=4)
    health = r.json()
    pg_ok = health.get("postgresql") == "ok"
    ol_ok = health.get("ollama") == "ok"
    status_line = f"postgresql={health.get('postgresql')} ollama={health.get('ollama')}"
    if pg_ok:
        ok(f"Flask API reachable — {status_line}")
        record(True)
    else:
        warn(f"Flask API up but services degraded — {status_line}")
        record(False)
except Exception as e:
    fail("Flask API not reachable at localhost:5000", str(e))
    record(False)

# 7-B Articles endpoint
try:
    import requests as req
    r = req.get("http://localhost:5000/api/articles?per_page=1", timeout=4)
    data = r.json()
    if isinstance(data, list):
        ok(f"GET /api/articles working — returned {len(data)} article(s)")
        record(True)
    else:
        fail("GET /api/articles returned unexpected format", str(data)[:80])
        record(False)
except Exception as e:
    fail("GET /api/articles failed", str(e))
    record(False)

# 7-C Stats endpoint
try:
    import requests as req
    r = req.get("http://localhost:5000/api/stats", timeout=4)
    stats = r.json()
    required_keys = ["total_articles", "summarised_today", "breaking_today",
                     "articles_by_status", "articles_by_category", "top_sources"]
    missing = [k for k in required_keys if k not in stats]
    if not missing:
        ok(f"GET /api/stats working — total articles: {stats.get('total_articles', 0):,}")
        record(True)
    else:
        fail(f"GET /api/stats missing keys: {missing}")
        record(False)
except Exception as e:
    fail("GET /api/stats failed", str(e))
    record(False)

# 7-D Image endpoint
if pg_conn:
    try:
        import requests as req
        with pg_conn.cursor() as cur:
            cur.execute("""
                SELECT a.id FROM articles a
                JOIN images i ON a.id = i.article_id
                LIMIT 1
            """)
            row = cur.fetchone()
        if row:
            article_id = row[0]
            r = req.get(f"http://localhost:5000/api/articles/{article_id}/image",
                        timeout=5)
            if r.status_code == 200 and r.headers.get("content-type") == "image/png":
                ok(f"GET /api/articles/{article_id}/image returns valid PNG")
                record(True)
            elif r.status_code == 404:
                fail(f"Image endpoint 404 for article {article_id} — path bug not fixed")
                record(False)
            else:
                warn(f"Image endpoint returned status {r.status_code}")
                record(False)
        else:
            warn("No articles with images — skipping image endpoint test")
            record(False)
    except Exception as e:
        fail("Image endpoint test failed", str(e))
        record(False)

# 7-E Pipeline control endpoints
try:
    import requests as req
    r = req.get("http://localhost:5000/api/pipeline/status", timeout=4)
    data = r.json()
    if "is_running" in data:
        ok(f"GET /api/pipeline/status working — is_running={data.get('is_running')}")
        record(True)
    else:
        fail("GET /api/pipeline/status missing 'is_running' field")
        record(False)
except Exception as e:
    fail("GET /api/pipeline/status failed", str(e))
    record(False)

# 7-F Pipeline history
try:
    import requests as req
    r = req.get("http://localhost:5000/api/pipeline/history", timeout=4)
    data = r.json()
    if isinstance(data, list):
        ok(f"GET /api/pipeline/history working — {len(data)} run(s) recorded")
        record(True)
    else:
        fail("GET /api/pipeline/history returned unexpected format")
        record(False)
except Exception as e:
    fail("GET /api/pipeline/history failed", str(e))
    record(False)

# 7-G Pending posts endpoint
try:
    import requests as req
    r = req.get("http://localhost:5000/api/posts/pending", timeout=4)
    data = r.json()
    if isinstance(data, list):
        ok(f"GET /api/posts/pending working — {len(data)} post(s) awaiting approval")
        record(True)
    else:
        fail("GET /api/posts/pending returned unexpected format")
        record(False)
except Exception as e:
    fail("GET /api/posts/pending failed", str(e))
    record(False)

# 7-H Streamlit reachable
try:
    import requests as req
    r = req.get("http://localhost:8501", timeout=5)
    if r.status_code == 200:
        ok("Streamlit dashboard reachable at localhost:8501")
        record(True)
    else:
        warn(f"Streamlit returned status {r.status_code}")
        record(False)
except Exception as e:
    fail("Streamlit not reachable at localhost:8501 — start with: streamlit run dashboard/dashboard.py", str(e))
    record(False)

# 7-I Celery app importable
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("celery_app", "celery_app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ok("celery_app.py importable — Celery + Beat configured")
    record(True)
except Exception as e:
    fail("celery_app.py import failed", str(e))
    record(False)

# 7-J Pipeline runs table populated
if pg_conn:
    try:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), MAX(started_at) FROM pipeline_runs")
            count, latest = cur.fetchone()
        if count and count > 0:
            age_h = (datetime.now(timezone.utc) - latest).total_seconds() / 3600 if latest else 999
            ok(f"pipeline_runs table: {count} run(s) recorded, last {age_h:.1f}h ago")
            record(True)
        else:
            warn("pipeline_runs table is empty — trigger a pipeline run from Control Panel")
            record(False)
    except Exception as e:
        fail("Could not query pipeline_runs", str(e))
        record(False)


# ════════════════════════════════════════════════════════════
#  FINAL SUMMARY
# ════════════════════════════════════════════════════════════
total = passed + failed
pct   = int(passed / total * 100) if total else 0

print(f"\n{'═'*58}")
print(f"{BOLD}  VERIFICATION COMPLETE{RESET}")
print(f"{'═'*58}")
print(f"  {GREEN}Passed:{RESET} {passed}")
print(f"  {RED}Failed:{RESET} {failed}")
print(f"  {BOLD}Score:  {pct}% ({passed}/{total}){RESET}")
print(f"{'═'*58}")

if failed == 0:
    print(f"\n  {GREEN}{BOLD}All phases verified. Ready for Phase 8 — Publishing Agent.{RESET}\n")
elif pct >= 80:
    print(f"\n  {YELLOW}{BOLD}Most checks passing. Fix the FAIL items above before Phase 8.{RESET}\n")
else:
    print(f"\n  {RED}{BOLD}Several issues found. Review FAIL items before continuing.{RESET}\n")

if pg_conn:
    pg_conn.close()
