import os
import sys
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import components from the autonomous news system
from agents.news_discovery_agent import NewsDiscoveryAgent
from pipeline.intelligence_pipeline import IntelligencePipeline
from agents.duplicate_merger import DuplicateMerger

# ANSI colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def print_test_result(test_num, description, success):
    status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
    print(f"Test {test_num:02d}: {description:<50} {status}")

def run_tests():
    # Load environment variables
    load_dotenv()
    
    # Enable ANSI escape characters on Windows
    if sys.platform == "win32":
        os.system("")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print(f"{RED}Error: DATABASE_URL not found in environment or .env file.{RESET}")
        sys.exit(1)

    passed_count = 0
    conn = None

    try:
        # TEST 1: DB Connection
        try:
            conn = psycopg2.connect(db_url)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            success = True
        except Exception as e:
            print(f"DB Error: {e}")
            success = False
        
        print_test_result(1, "DB connection (SELECT 1)", success)
        if success: passed_count += 1
        else:
            print(f"{RED}Aborting tests due to connection failure.{RESET}")
            return passed_count

        # TEST 2: Tables exist
        required_tables = [
            'articles', 'feed_sources', 'error_logs', 
            'trending_keywords', 'story_clusters', 'system_config'
        ]
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                existing_tables = [row[0] for row in cur.fetchall()]
            
            missing = [t for t in required_tables if t not in existing_tables]
            success = len(missing) == 0
            if not success:
                print(f"  Missing tables: {', '.join(missing)}")
        except Exception:
            success = False
        
        print_test_result(2, "Required tables exist", success)
        if success: passed_count += 1

        # TEST 3: Feed sources count
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM feed_sources WHERE active = TRUE")
                count = cur.fetchone()[0]
            success = count >= 40
        except Exception:
            success = False
        
        print_test_result(3, "Feed sources (>= 40 active)", success)
        if success: passed_count += 1

        # TEST 4: Discovery agent
        try:
            agent = NewsDiscoveryAgent()
            # We don't want to wait for a full run if it's too slow, 
            # but the request says call run() and confirm it returns int >= 0.
            result = agent.run()
            success = isinstance(result, int) and result >= 0
        except Exception as e:
            print(f"  Agent error: {e}")
            success = False
        
        print_test_result(4, "Discovery agent run()", success)
        if success: passed_count += 1

        # TEST 5: Articles in DB (status='new')
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM articles WHERE status = 'new'")
                count = cur.fetchone()[0]
            success = count >= 1
        except Exception:
            success = False
        
        print_test_result(5, "Articles in DB (status='new')", success)
        if success: passed_count += 1

        # TEST 6: Viral scores
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM articles WHERE viral_score > 0")
                count = cur.fetchone()[0]
            success = count >= 1
        except Exception:
            success = False
        
        print_test_result(6, "Viral scores (> 0)", success)
        if success: passed_count += 1

        # TEST 7: Intelligence pipeline
        try:
            pipeline = IntelligencePipeline()
            result = pipeline.run()
            expected_keys = {"scored", "merged", "breaking"}
            success = isinstance(result, dict) and expected_keys.issubset(result.keys())
        except Exception as e:
            print(f"  Pipeline error: {e}")
            success = False
        
        print_test_result(7, "Intelligence pipeline run()", success)
        if success: passed_count += 1

        # TEST 8: Breaking news handling
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM articles 
                    WHERE is_breaking = TRUE AND status NOT IN ('approved', 'summarised')
                """)
                count = cur.fetchone()[0]
            success = count == 0
        except Exception:
            success = False
        
        print_test_result(8, "Breaking news (status='approved'/summarised')", success)
        if success: passed_count += 1

        # TEST 9: Duplicate merger
        try:
            merger = DuplicateMerger()
            # find_clusters requires a live db connection
            clusters = merger.find_clusters(conn)
            success = isinstance(clusters, list)
        except Exception as e:
            print(f"  Merger error: {e}")
            success = False
        
        print_test_result(9, "Duplicate merger clusters", success)
        if success: passed_count += 1

        # TEST 10: Error logs
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM error_logs WHERE agent = 'intelligence'")
                count = cur.fetchone()[0]
            success = count >= 1
        except Exception:
            success = False
        
        print_test_result(10, "Intelligence error logs", success)
        if success: passed_count += 1

    finally:
        if conn:
            conn.close()

    print("\n" + "="*30)
    summary_color = GREEN if passed_count == 10 else RED
    print(f"Summary: {summary_color}{passed_count}/10{RESET} tests passed.")
    print("="*30)

    return passed_count

if __name__ == "__main__":
    run_tests()
