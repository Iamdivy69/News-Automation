import os
import psycopg2
import psycopg2.extras
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from agents.headline_generator import HeadlineGenerator
from agents.image_renderer import ImageRenderer


class VisualGenerationAgent:
    AGENT_NAME = "visual_generation"

    def __init__(self):
        self.conn_string = os.environ.get('DATABASE_URL')
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.images_dir = os.path.join(root, 'output', 'images', datetime.now().strftime('%Y-%m-%d'))
        os.makedirs(self.images_dir, exist_ok=True)
        self.headline_gen = HeadlineGenerator()
        self.renderer = ImageRenderer()

    def run(self):
        metrics = {'processed': 0, 'success': 0, 'failed': 0}

        conn = psycopg2.connect(self.conn_string)

        try:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT id, headline, full_text, summary, category,
                           is_breaking, viral_score, source
                    FROM articles
                    WHERE status = 'summarised' AND top_30_selected = TRUE
                    LIMIT 30
                """)
                articles = cur.fetchall()
        except Exception as e:
            print(f"[VISUAL] Failed to fetch articles: {e}")
            conn.close()
            return metrics

        for art in articles:
            metrics['processed'] += 1
            try:
                hdata = self.headline_gen.generate({
                    'title':      art['headline'] or '',
                    'summary':    art['summary'] or art['full_text'] or '',
                    'category':   art['category'] or '',
                    'is_breaking': art['is_breaking'] or False,
                })

                fname = f"visual_{art['id']}_{int(datetime.now().timestamp())}.png"
                path  = os.path.join(self.images_dir, fname)

                rdata = {**dict(art), **hdata}
                self.renderer.render(rdata, path)

                # Step A: Write to images table
                try:
                    with conn.cursor() as c:
                        c.execute("""
                            INSERT INTO images (article_id, image_path, image_type)
                            VALUES (%s, %s, 'portrait')
                            ON CONFLICT DO NOTHING
                        """, (art['id'], path))
                except Exception as e:
                    print(f'[VISUAL] images table write failed: {e}')
                    # Non-fatal — continue anyway

                # Step B: Store HTTP URL in articles.image_url
                api_image_url = f"/api/articles/{art['id']}/image"
                with conn.cursor() as c:
                    c.execute("""
                        UPDATE articles
                        SET image_url = %s,
                            image_source = 'gemini_template',
                            image_prompt = %s,
                            status = 'image_ready',
                            processing_stage = 'image_ready'
                        WHERE id = %s
                    """, (api_image_url, hdata.get('headline', ''), art['id']))
                conn.commit()
                metrics['success'] += 1
                print(f"[VISUAL] article={art['id']} image={path} url={api_image_url}")

            except Exception as e:
                conn.rollback()
                metrics['failed'] += 1
                print(f"[VISUAL] FAILED article {art['id']}: {e}")

        conn.close()
        print(
            f"[VISUAL] processed={metrics['processed']} "
            f"success={metrics['success']} "
            f"failed={metrics['failed']}"
        )
        return metrics


if __name__ == '__main__':
    agent = VisualGenerationAgent()
    agent.run()
