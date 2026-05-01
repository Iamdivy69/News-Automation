import os
import psycopg2
import psycopg2.extras
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.visual_generation_agent import VisualGenerationAgent
from pipeline.intelligence_pipeline import IntelligencePipeline
from agents.summarisation_agent import SummarisationAgent
from agents.publishing_agent import PublishingAgent

class MasterPipeline:
    """Orchestrates the entire autonomous news lifecycle: Discovery -> Intelligence -> Summarisation"""

    def __init__(self):
        self.conn_string = os.environ.get("DATABASE_URL")
        if not self.conn_string:
            raise ValueError("DATABASE_URL environment variable is not set.")
            
    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def run(self) -> dict:
        from datetime import datetime, timezone
        started_at = datetime.now(timezone.utc)

        # Phase -1: Purge stale unprocessed articles before running anything else
        print("Phase -1: Purging stale unprocessed articles older than 12h...")
        try:
            from agents.news_discovery_agent import NewsDiscoveryAgent
            disc_agent = NewsDiscoveryAgent()
            purge_conn = self._get_conn()
            purged = disc_agent.purge_stale_articles(purge_conn)
            purge_conn.close()
            print(f"  Purged {purged} stale articles")
        except Exception as e:
            print(f"purge_stale error (non-fatal): {e}")

        # 0. Auto-discard stale low-score articles before running the pipeline
        print("Phase 0: Auto-discarding low-score articles older than 6 hours...")
        try:
            pub_agent_pre = PublishingAgent()
            pre_conn = self._get_conn()
            pub_agent_pre.auto_discard(pre_conn)
            pre_conn.close()
        except Exception as e:
            print(f"auto_discard error (non-fatal): {e}")
        
        # 1. Run Intelligence Pipeline 
        # (This automatically executes NewsDiscoveryAgent, ViralScoreEngine, and DuplicateMerger)
        print("Phase 1: Running Intelligence Pipeline (Discovery, Scoring, Merging)...")
        intel_pipeline = IntelligencePipeline()
        intel_summary = intel_pipeline.run()
        
        # 2. Run Summarisation Agent
        # (This fetches 'approved' articles and generates 5 formats via Ollama)
        print("Phase 2: Running Summarisation Agent...")
        sum_agent = SummarisationAgent()
        summarised_count = sum_agent.run()
        
        # 3. Run Visual Generation Agent
        print("Phase 3: Running Visual Generation Agent...")
        visual_agent = VisualGenerationAgent()
        os.makedirs(visual_agent.images_dir, exist_ok=True)
        images_generated_count = 0
        
        try:
            conn = self._get_conn()
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute("""
                        SELECT articles.id, articles.headline, articles.source, articles.category,
                               articles.is_breaking, articles.viral_score
                        FROM articles
                        LEFT JOIN images ON articles.id = images.article_id
                        WHERE articles.status = 'summarised' AND images.id IS NULL
                    """)
                    articles_for_images = cur.fetchall()
                    
            for article in articles_for_images:
                article_id = article["id"]
                
                output_path = visual_agent.generate_portrait_card(
                    headline=article["headline"],
                    source=article["source"],
                    category=article["category"],
                    is_breaking=article["is_breaking"] or False,
                    article_id=article_id,
                    viral_score=article["viral_score"] or 0,
                )
                
                if output_path:
                    with self._get_conn() as save_conn:
                        visual_agent.save_image_record(
                            article_id, output_path, 'portrait', save_conn
                        )
                    images_generated_count += 1
                
            conn.close()
        except Exception as e:
            print(f"Error generating visual cards: {e}")

        # Phase 3b: Promoting fully-processed articles to publish_approved
        print("Phase 3b: Promoting fully-processed articles to publish_approved...")
        try:
            promo_conn = self._get_conn()
            with promo_conn:
                with promo_conn.cursor() as cur:
                    cur.execute('''
                        UPDATE articles
                        SET status = %s
                        WHERE status = %s
                        AND id IN (SELECT article_id FROM summaries)
                        AND id IN (SELECT article_id FROM images)
                    ''', ('publish_approved', 'approved'))
                    promoted = cur.rowcount
            promo_conn.close()
            print(f"  Promoted {promoted} articles to publish_approved")
            combined_summary["promoted"] = promoted
        except Exception as e:
            print(f"Phase 3b error (non-fatal): {e}")

        # 4. Run Publishing Agent
        print("Phase 4: Running Publishing Agent...")
        pub_agent = PublishingAgent()
        published_count = pub_agent.run(limit=50)

        # 4. Compile Master Summary
        total_discovered = intel_summary.get("discovered", 0)
        total_scored = intel_summary.get("scored", 0)
        total_merged = intel_summary.get("merged", 0)
        total_breaking = intel_summary.get("breaking", 0)
        
        combined_summary = {
            "discovered": total_discovered,
            "scored": total_scored,
            "merged": total_merged,
            "breaking": total_breaking,
            "summarised": summarised_count,
            "images_generated": images_generated_count,
            "published": published_count
        }
        
        print("Phase 5: Running Feedback Loop Engine...")
        try:
            from agents.feedback_loop_engine import FeedbackLoopEngine
            feedback = FeedbackLoopEngine()
            fb_result = feedback.run()
            combined_summary["insight"] = fb_result.get("insight_report", "")[:200]
            print(f"  Insight: {combined_summary['insight']}")
        except Exception as e:
            print(f"Feedback loop error: {e}")
            combined_summary["insight"] = ""
        
        finished_at = datetime.now(timezone.utc)
        duration_sec = (finished_at - started_at).total_seconds()
        
        try:
            conn = self._get_conn()
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO pipeline_runs 
                        (run_type, discovered, scored, merged, breaking, summarised, images_generated, published, duration_sec, started_at, finished_at) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            'master_pipeline',
                            total_discovered,
                            total_scored,
                            total_merged,
                            total_breaking,
                            summarised_count,
                            images_generated_count,
                            published_count,
                            duration_sec,
                            started_at,
                            finished_at
                        )
                    )
            conn.close()
        except Exception as e:
            print(f"Failed to log master pipeline summary to database: {e}")
            
        return combined_summary

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    pipeline = MasterPipeline()
    print("=== STARTING MASTER PIPELINE ===")
    results = pipeline.run()
    
    print("\n=== PIPELINE FINISHED ===")
    print("Final Results:")
    for k, v in results.items():
        print(f"  {k.capitalize()}: {v}")
