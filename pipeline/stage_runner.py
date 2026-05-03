import time
import traceback
from datetime import datetime

def run_stage(stage_name, agent_class, log_conn) -> dict:
    start_time = time.time()
    status = "success"
    error_msg = None
    metrics = {}
    
    try:
        agent = agent_class()
        raw = agent.run()
        metrics = raw if isinstance(raw, dict) else {'processed': raw or 0}
    except Exception as e:
        status = "failed"
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        try:
            with log_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO error_logs (agent, message, stack_trace) VALUES (%s, %s, %s)",
                    (stage_name, error_msg, traceback_str)
                )
            log_conn.commit()
        except Exception:
            log_conn.rollback()
            
    duration = int(time.time() - start_time)
    
    # Try to extract 'processed', 'selected' from metrics
    articles_in = metrics.get('processed', metrics.get('articles_in', 0))
    articles_out = metrics.get('selected', metrics.get('articles_out', articles_in))
    
    try:
        with log_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pipeline_runs
                (stage, started_at, completed_at, articles_in, articles_out, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                stage_name,
                datetime.fromtimestamp(start_time),
                datetime.now(),
                articles_in,
                articles_out,
                error_msg
            ))
        log_conn.commit()
    except Exception as e:
        log_conn.rollback()
        print(f"Failed to log pipeline_runs for {stage_name}: {e}")
        
    print(f"[PIPELINE] stage={stage_name} in={articles_in} out={articles_out} duration={duration}s")
    
    return {
        "stage": stage_name,
        "status": status,
        "duration": duration,
        "metrics": metrics,
        "error": error_msg
    }
