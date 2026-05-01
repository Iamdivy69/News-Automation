import os
import psycopg2
import psycopg2.extras
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.news_discovery_agent import NewsDiscoveryAgent
from agents.duplicate_merger import DuplicateMerger
from agents.viral_score_engine import ViralScoreEngine


class IntelligencePipeline:
    """Orchestrates news discovery, viral scoring, and deduplication clustering."""
    
    def __init__(self):
        self.conn_string = os.environ["DATABASE_URL"]

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def _get_unscored_articles(self, cur):
        cur.execute(
            """
            SELECT id, url, headline, full_text, source, published_date, category, status, viral_score
            FROM articles 
            WHERE status = 'new' AND viral_score = 0
            """
        )
        return cur.fetchall()

    def _update_article_score(self, cur, article_id: int, viral_score: int, is_breaking: bool):
        # Promote to 'publish_approved' if it's breaking news OR has a high viral score (>= 65)
        # Articles scoring below 65 are automatically discarded to keep the queue clean
        if is_breaking:
            new_status = 'approved'
        elif viral_score >= 65:
            new_status = 'approved'
        else:
            new_status = 'new'
        
        cur.execute(
            """
            UPDATE articles 
            SET viral_score = %s, is_breaking = %s, status = %s
            WHERE id = %s
            """,
            (viral_score, is_breaking, new_status, article_id)
        )

    def _log_summary(self, scored: int, merged: int, breaking: int):
        message = f"Pipeline Summary: Scored={scored}, Merged={merged}, Breaking={breaking}"
        try:
            conn = self._get_conn()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO error_logs (agent, message, stack_trace) VALUES (%s, %s, NULL)",
                        ('intelligence', message)
                    )
            conn.close()
        except Exception as e:
            print(f"Failed to write logs: {e}")

    def run(self) -> dict:
        """Executes the full pipeline sequence and returns metrics."""
        summary = {
            "discovered": 0,
            "scored": 0,
            "merged": 0,
            "breaking": 0
        }

        # 1. Fetch new articles via Discovery Agent
        agent = NewsDiscoveryAgent()
        print("Running NewsDiscoveryAgent...")
        summary["discovered"] = agent.run()
        
        # 2. Score articles
        scorer = ViralScoreEngine()
        conn = self._get_conn()
        try:
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    unscored = self._get_unscored_articles(cur)
                    for article in unscored:
                        article_dict = dict(article)
                        headline = article_dict.get('headline') or ""
                        
                        v_score = scorer.score(article_dict)
                        breaking = scorer.is_breaking(headline)
                        
                        self._update_article_score(cur, article["id"], v_score, breaking)
                        
                        summary["scored"] += 1
                        if breaking:
                            summary["breaking"] += 1
                            
        finally:
            conn.close()

        # 3. Merge duplicate clusters (DuplicateMerger must use its own connection flow)
        merger = DuplicateMerger()
        conn = self._get_conn()
        try:
            print("Running DuplicateMerger...")
            summary["merged"] = merger.run(conn)
        finally:
            conn.close()

        # 4 & 5. Log activity
        self._log_summary(summary["scored"], summary["merged"], summary["breaking"])

        return summary


if __name__ == "__main__":
    import json
    # Guarantee the DATABASE_URL exists for manual testing
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = "host=localhost port=5432 dbname=news_system user=postgres"
        
    pipeline = IntelligencePipeline()
    print("IntelligencePipeline starting...")
    result = pipeline.run()
    print("\nPipeline finished! Results:")
    print(json.dumps(result, indent=2))
