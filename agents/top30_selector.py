import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

class Top30Selector:
    AGENT_NAME = "top30_selector"

    def __init__(self):
        self.conn_string = os.environ.get("DATABASE_URL")

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def run(self):
        started_at = datetime.now(timezone.utc)
        metrics = {
            "selected": 0,
            "discarded": 0,
            "top_scores": [],
            "cutoff_score": 0
        }
        
        conn = None
        try:
            conn = self._get_conn()
            if not conn:
                return metrics
            
            # 1. Fetch all articles WHERE status = 'approved_unique' ORDER BY viral_score DESC
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, viral_score 
                    FROM articles 
                    WHERE status = 'approved_unique' 
                    ORDER BY viral_score DESC NULLS LAST
                """)
                rows = cur.fetchall()
            
            total_unique = len(rows)
            if total_unique == 0:
                print("[TOP30] selected=0 discarded=0 cutoff_score=0")
                self._log_run(conn, started_at, total_unique, 0, 0, "No articles to process")
                return metrics
                
            # 2. Take the TOP 30 by viral_score
            top_30 = rows[:30]
            others = rows[30:]
            
            metrics["selected"] = len(top_30)
            metrics["discarded"] = len(others)
            
            top_scores = []
            for r in top_30[:5]:
                if r["viral_score"] is not None:
                    top_scores.append(r["viral_score"])
            metrics["top_scores"] = top_scores
            
            if top_30[-1]["viral_score"] is not None:
                metrics["cutoff_score"] = top_30[-1]["viral_score"]
            else:
                metrics["cutoff_score"] = 0
            
            errors = 0
            
            # 3. For those 30: UPDATE articles SET top_30_selected = TRUE, processing_stage = 'top30', status = 'top30_selected'
            # Add per-article commit/rollback: one bad row must not block the rest.
            for article in top_30:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE articles 
                            SET top_30_selected = TRUE, 
                                processing_stage = 'top30', 
                                status = 'top30_selected'
                            WHERE id = %s
                        """, (article["id"],))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    errors += 1
                    
            # 4. For ALL OTHERS with status = 'approved_unique': UPDATE articles SET status = 'discarded', processing_stage = 'discarded'
            for article in others:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE articles 
                            SET status = 'discarded', 
                                processing_stage = 'discarded'
                            WHERE id = %s
                        """, (article["id"],))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    errors += 1
                    
            # 5. Log a row in pipeline_runs
            self._log_run(conn, started_at, total_unique, metrics["selected"], errors, "Completed successfully")
            
        except Exception as e:
            print(f"Top30Selector error: {e}")
        finally:
            if conn:
                conn.close()
                
        print(f"[TOP30] selected={metrics['selected']} discarded={metrics['discarded']} cutoff_score={metrics['cutoff_score']}")
        return metrics
        
    def _log_run(self, conn, started_at, articles_in, articles_out, errors, notes):
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_runs 
                    (stage, started_at, completed_at, articles_in, articles_out, errors, notes)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s)
                """, ('top30_selector', started_at, articles_in, articles_out, errors, notes))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Failed to log pipeline run: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    agent = Top30Selector()
    agent.run()
