from dotenv import load_dotenv
load_dotenv()

import os
import psycopg2
from datetime import datetime, timezone
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
        self.conn_string = os.environ.get('DATABASE_URL')

    def _get_conn(self):
        return psycopg2.connect(self.conn_string)

    def _count(self, conn, where):
        try:
            with conn.cursor() as c:
                c.execute('SELECT COUNT(*) FROM articles WHERE ' + where)
                return c.fetchone()[0]
        except Exception:
            conn.rollback()
            return 0

    def run(self):
        started = datetime.now(timezone.utc)
        conn = self._get_conn()

        STAGES = [
            ('Stage 1', 'discovery',         NewsDiscoveryAgent,   None),
            ('Stage 2', 'viral_scoring',      ViralScoreEngine,     "status='approved'"),
            ('Stage 3', 'deduplication',      DuplicateMerger,      "status='ranked'"),
            ('Stage 4', 'top30_selection',    Top30Selector,        "status='approved_unique'"),
            ('Stage 5', 'summarisation',      SummarisationAgent,   "status='top30_selected' AND top_30_selected=TRUE"),
            ('Stage 6', 'visual_generation',  VisualGenerationAgent,"status='summarised' AND top_30_selected=TRUE"),
            ('Stage 7', 'publishing',         PublishingAgent,      "status='image_ready'"),
        ]

        summary = {}

        for disp, name, Cls, cond in STAGES:
            if cond and self._count(conn, cond) == 0:
                print(f'[PIPELINE] {disp} ({name}): SKIPPED')
                summary[name] = {'status': 'skipped'}
                continue

            print(f'[PIPELINE] {disp} ({name}): RUNNING')
            summary[name] = run_stage(name, Cls, conn)

        conn.close()
        return summary
