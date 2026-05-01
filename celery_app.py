import os
import sys
from celery import Celery
from celery.schedules import crontab

# Ensure project root is in the Python path for Celery to find the pipeline module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Initialize Celery with Redis broker
app = Celery("news_system", broker="redis://localhost:6379/0")

# --- Celery Beat Schedule ---
app.conf.beat_schedule = {
    # Run the full pipeline every 15 minutes
    "run-pipeline-15-mins": {
        "task": "celery_app.run_pipeline",
        "schedule": crontab(minute="*/15"),
    },
    # Run ONLY discovery every 15 minutes (independent of slow summarisation)
    "discover-only-15-mins": {
        "task": "celery_app.discover_only",
        "schedule": crontab(minute="*/15"),
    },
    # Daily cleanup of old low-value articles at 3am UTC
    "cleanup-old-articles-daily": {
        "task": "celery_app.cleanup_old_articles",
        "schedule": crontab(hour=3, minute=0),
    },
    # Weekly cleanup of old image date-folders on Sunday at 4am UTC
    "cleanup-images-weekly": {
        "task": "celery_app.cleanup_images",
        "schedule": crontab(day_of_week=0, hour=4, minute=0),
    },
}
app.conf.timezone = "UTC"


@app.task
def run_pipeline():
    """Import and execute the master pipeline, reporting results back to Celery."""
    try:
        from pipeline.master_pipeline import MasterPipeline
        pipeline = MasterPipeline()
        result = pipeline.run()
        print(f"Pipeline Execution Result: {result}")
        return result
    except Exception as e:
        print(f"Pipeline Execution Failed: {e}")
        raise


@app.task
def discover_only():
    """Run only the NewsDiscoveryAgent — fast, independent of Ollama."""
    try:
        from agents.news_discovery_agent import NewsDiscoveryAgent
        from dotenv import load_dotenv
        load_dotenv()
        agent = NewsDiscoveryAgent()
        count = agent.run()
        print(f"discover_only: {count} new articles")
        return {"discovered": count}
    except Exception as e:
        print(f"discover_only failed: {e}")
        raise


@app.task
def cleanup_old_articles():
    """Delete low-value unprocessed articles older than 24 hours."""
    try:
        import psycopg2
        from dotenv import load_dotenv
        load_dotenv()
        conn_string = os.environ["DATABASE_URL"]
        from agents.news_discovery_agent import NewsDiscoveryAgent
        agent = NewsDiscoveryAgent()
        conn = psycopg2.connect(conn_string)
        deleted = agent.discard_old_articles(conn)
        conn.close()
        print(f"cleanup_old_articles: deleted {deleted} rows")
        return {"deleted": deleted}
    except Exception as e:
        print(f"cleanup_old_articles failed: {e}")
        raise


@app.task
def cleanup_images():
    """Delete image date-subfolders older than 7 days."""
    try:
        from agents.visual_generation_agent import VisualGenerationAgent
        agent = VisualGenerationAgent()
        deleted = agent.cleanup_old_image_folders(days_to_keep=7)
        print(f"cleanup_images: deleted {deleted} folder(s)")
        return {"deleted_folders": deleted}
    except Exception as e:
        print(f"cleanup_images failed: {e}")
        raise


# =====================================================================
# WINDOWS START COMMANDS
# Run these in separate command prompts from the D:\PROJECTS\NA folder.
# NOTE: Windows requires the pool set to 'solo' (-P solo) to work properly.
#
# 1. Start the Celery Worker:
#    celery -A celery_app worker --loglevel=info -P solo
#
# 2. Start the Celery Beat Scheduler:
#    celery -A celery_app beat --loglevel=info
# =====================================================================
