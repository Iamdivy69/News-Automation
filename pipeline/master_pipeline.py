import os
import psycopg2
from pipeline.stage_runner import run_stage

from agents.news_discovery_agent import NewsDiscoveryAgent
from agents.viral_score_engine import ViralScoreEngine
from agents.duplicate_merger import DuplicateMerger
from agents.top30_selector import Top30Selector
from agents.summarisation_agent import SummarisationAgent
from agents.visual_generation_agent import VisualGenerationAgent
from agents.publishing_agent import PublishingAgent

class MasterPipeline:
    def __init__(self):
        self.conn_string = os.environ.get("DATABASE_URL")
        
    def _get_conn(self):
        return psycopg2.connect(self.conn_string)
        
    def _count_articles(self, conn, condition):
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM articles WHERE {condition}")
                return cur.fetchone()[0]
        except Exception as e:
            print(f"Error checking status: {e}")
            conn.rollback()
            return 0
            
    def run(self):
        conn = self._get_conn()
        
        stages = [
            ("Stage 1", "discovery", NewsDiscoveryAgent, None),
            ("Stage 2", "viral_scoring", ViralScoreEngine, "status = 'approved'"),
            ("Stage 3", "duplicate_merging", DuplicateMerger, "status = 'ranked'"),
            ("Stage 4", "top30_selection", Top30Selector, "status = 'approved_unique'"),
            ("Stage 5", "summarisation", SummarisationAgent, "status = 'top30_selected' AND top_30_selected = TRUE"),
            ("Stage 6", "visual_generation", VisualGenerationAgent, "status = 'summarised' AND top_30_selected = TRUE"),
            ("Stage 7", "publishing", PublishingAgent, "status IN ('image_ready', 'queued')")
        ]
        
        summary = {}
        
        for display_name, stage_name, agent_class, condition in stages:
            if condition:
                count = self._count_articles(conn, condition)
                if count == 0:
                    print(f"[PIPELINE] {display_name}: {stage_name} skipped (0 articles waiting in required status)")
                    summary[stage_name] = {"status": "skipped", "reason": "no input"}
                    continue
            
            # Run the stage
            res = run_stage(stage_name, agent_class, conn)
            summary[stage_name] = res
            
        conn.close()
        return summary
