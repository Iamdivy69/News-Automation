import os
import sys
import time
import signal
import json
import psutil
import psycopg2
import requests
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv()

from agents.news_discovery_agent import NewsDiscoveryAgent
from agents.viral_score_engine import ViralScoreEngine
from agents.duplicate_merger import DuplicateMerger
from agents.visual_generation_agent import VisualGenerationAgent
from agents.posting_time_engine import PostingTimeEngine
from agents.publishing_agent import PublishingAgent
from agents.feedback_loop_engine import FeedbackLoopEngine

LOCK_FILE = "main.lock"
SHUTDOWN_SIGNALED = False
PUBLISHING_CRASHES = 0

os.makedirs("logs", exist_ok=True)

def log_json(data):
    data["timestamp"] = datetime.now().isoformat()
    try:
        with open("logs/main.log", "a") as f:
            f.write(json.dumps(data) + "\n")
    except Exception:
        pass

def handle_sigint(signum, frame):
    global SHUTDOWN_SIGNALED
    print("\n[MAIN] Graceful shutdown initiated. Waiting for current cycle to finish...")
    log_json({"event": "shutdown_initiated"})
    SHUTDOWN_SIGNALED = True

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            if not psutil.pid_exists(pid):
                os.remove(LOCK_FILE)
                log_json({"event": "stale_lock_removed", "pid": pid})
            else:
                return False
        except Exception:
            os.remove(LOCK_FILE)
            
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return False

def release_lock():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass

def send_telegram_alert(msg):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID")
    if bot_token and chat_id:
        try:
            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                          json={"chat_id": chat_id, "text": msg}, timeout=10)
        except Exception:
            pass

def run_module(module_name, engine_class):
    if SHUTDOWN_SIGNALED:
        return True, {}
    start = time.time()
    try:
        engine = engine_class()
        metrics = engine.run() or {}
        elapsed = int(time.time() - start)
        print(f"[MAIN] {module_name} done {elapsed}s")
        log_json({"event": "module_done", "module": module_name, "duration": elapsed, "status": "ok"})
        return True, metrics
    except Exception as e:
        elapsed = int(time.time() - start)
        print(f"[MAIN] {module_name} crashed after {elapsed}s: {e}")
        log_json({"event": "module_crashed", "module": module_name, "duration": elapsed, "error": str(e)})
        return False, {}

def check_activity(conn):
    breaking_posted = False
    no_activity_6h = False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE status='published' 
                AND posted_at >= NOW() - INTERVAL '15 minutes' 
                AND (headline ILIKE '%breaking%' OR priority_level > 0)
            """)
            if cur.fetchone()[0] > 0:
                breaking_posted = True
                
            cur.execute("""
                SELECT COUNT(*) FROM articles
                WHERE created_at >= NOW() - INTERVAL '6 hours'
                OR posted_at >= NOW() - INTERVAL '6 hours'
            """)
            if cur.fetchone()[0] == 0:
                no_activity_6h = True
    except Exception:
        pass
    return breaking_posted, no_activity_6h

def update_health(duration, modules_ok, errors, db_conn=None):
    queued = 0
    if db_conn:
        try:
            with db_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM articles WHERE status IN ('queued', 'image_ready', 'scheduled')")
                queued = cur.fetchone()[0]
        except Exception:
            pass
            
    health = {
        "last_cycle": datetime.now().isoformat(),
        "duration": duration,
        "modules_ok": modules_ok,
        "errors": errors,
        "queued_articles": queued
    }
    try:
        with open("status.json", "w") as f:
            json.dump(health, f, indent=2)
    except Exception:
        pass

def main():
    global SHUTDOWN_SIGNALED, PUBLISHING_CRASHES
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    if not acquire_lock():
        print(f"[MAIN] Another instance is already running ({LOCK_FILE} exists). Exiting.")
        sys.exit(1)

    print("[MAIN] version=1.0 booted")
    log_json({"event": "boot", "version": "1.0"})

    try:
        last_feedback_run = None
        
        while not SHUTDOWN_SIGNALED:
            cycle_start = time.time()
            print("\n[MAIN] starting cycle")
            log_json({"event": "cycle_start"})
            
            modules_ok = 0
            errors = 0

            for name, cls in [
                ("discovery", NewsDiscoveryAgent),
                ("viral", ViralScoreEngine),
                ("dedup", DuplicateMerger),
                ("visual", VisualGenerationAgent),
                ("timing", PostingTimeEngine)
            ]:
                ok, _ = run_module(name, cls)
                if ok: modules_ok += 1
                else: errors += 1

            pub_ok, _ = run_module("publishing", PublishingAgent)
            if pub_ok: 
                modules_ok += 1
                PUBLISHING_CRASHES = 0
            else: 
                errors += 1
                PUBLISHING_CRASHES += 1
                if PUBLISHING_CRASHES >= 3:
                    send_telegram_alert("🚨 [MAIN] ALERT: Publishing Agent crashed 3 cycles in a row!")
                    log_json({"event": "alert_sent", "reason": "publishing_crashed_3_times"})
                    PUBLISHING_CRASHES = 0

            now = datetime.now()
            if now.isoweekday() == 7 and now.hour == 23:
                if last_feedback_run is None or (now - last_feedback_run).total_seconds() > 3600:
                    fb_ok, _ = run_module("feedback_loop", FeedbackLoopEngine)
                    if fb_ok: modules_ok += 1
                    else: errors += 1
                    last_feedback_run = now

            cycle_elapsed = int(time.time() - cycle_start)
            print(f"[MAIN] cycle complete {cycle_elapsed}s")
            log_json({"event": "cycle_complete", "duration": cycle_elapsed, "modules_ok": modules_ok, "errors": errors})

            # Check DB for adaptive loop and health
            breaking_posted, no_activity_6h = False, False
            conn = None
            try:
                conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
                breaking_posted, no_activity_6h = check_activity(conn)
                update_health(cycle_elapsed, modules_ok, errors, conn)
            except Exception:
                pass
            finally:
                if conn: conn.close()

            sleep_duration = 900
            if breaking_posted:
                sleep_duration = 300
                log_json({"event": "adaptive_loop", "sleep": 300, "reason": "breaking_news"})
            elif no_activity_6h:
                sleep_duration = 1800
                log_json({"event": "adaptive_loop", "sleep": 1800, "reason": "no_activity_6h"})

            slept = 0
            while slept < sleep_duration and not SHUTDOWN_SIGNALED:
                time.sleep(1)
                slept += 1

    finally:
        release_lock()
        print("[MAIN] Exited safely.")
        log_json({"event": "shutdown_complete"})

if __name__ == "__main__":
    main()
