"""
tests/test_pipeline_v2.py
Full pipeline validation suite with mock DB data.
Run: python -m pytest tests/test_pipeline_v2.py -v
"""
import os
import sys
import json
import random
import pytest
import psycopg2
import psycopg2.extras
from unittest.mock import patch, MagicMock, call
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DB_URL = os.environ.get("DATABASE_URL")

# ─── DB Helpers ───────────────────────────────────────────────────────────────

def get_conn():
    if not DB_URL:
        pytest.skip("DATABASE_URL not set — skipping DB tests")
    try:
        conn = psycopg2.connect(DB_URL)
        return conn
    except psycopg2.OperationalError as e:
        pytest.skip(f"Cannot connect to DB ({e}) — skipping DB-backed tests")


def clear_test_articles(conn):
    """Remove any articles seeded by tests (url LIKE 'http://test-%')."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM articles WHERE url LIKE 'http://test-%'")
    conn.commit()


def seed_articles(conn, count: int, status: str = "approved_unique") -> list[int]:
    """Insert `count` dummy articles, return list of inserted IDs."""
    ids = []
    with conn.cursor() as cur:
        for i in range(count):
            score = round(random.uniform(10.0, 99.0), 2)
            cur.execute(
                """
                INSERT INTO articles
                    (url, headline, full_text, source, status, viral_score, top_30_selected)
                VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                RETURNING id
                """,
                (
                    f"http://test-{i}-{random.randint(1000,9999)}.example.com",
                    f"Test headline number {i} for pipeline validation",
                    f"Full article text for test article {i}. " * 20,
                    "TestSource",
                    status,
                    score,
                ),
            )
            ids.append(cur.fetchone()[0])
    conn.commit()
    return ids


# ─── TEST 1: Top30Selector ────────────────────────────────────────────────────

class TestTop30Selector:
    """Insert 50 dummy articles, run selector, assert exactly 30 selected."""

    def setup_method(self):
        self.conn = get_conn()
        clear_test_articles(self.conn)
        self.inserted_ids = seed_articles(self.conn, 50)

    def teardown_method(self):
        clear_test_articles(self.conn)
        self.conn.close()

    def test_selects_exactly_30(self):
        from agents.top30_selector import Top30Selector

        agent = Top30Selector()
        result = agent.run()

        # Validate return dict
        assert "selected" in result, "Result must have 'selected' key"
        assert "discarded" in result, "Result must have 'discarded' key"
        assert result["selected"] == 30, f"Expected 30 selected, got {result['selected']}"
        assert result["discarded"] == 20, f"Expected 20 discarded, got {result['discarded']}"
        assert len(result.get("top_scores", [])) <= 5, "top_scores should have at most 5 items"
        assert result["cutoff_score"] > 0, "cutoff_score should be > 0"

        # Confirm DB state for our inserted IDs
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM articles WHERE id = ANY(%s) AND top_30_selected = TRUE",
                (self.inserted_ids,)
            )
            selected_count = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM articles WHERE id = ANY(%s) AND status = 'discarded'",
                (self.inserted_ids,)
            )
            discarded_count = cur.fetchone()[0]

        assert selected_count == 30, f"DB: expected 30 top_30_selected=TRUE, got {selected_count}"
        assert discarded_count == 20, f"DB: expected 20 discarded, got {discarded_count}"
        print(f"\n  ✓ Top30Selector: selected={selected_count} discarded={discarded_count} cutoff={result['cutoff_score']:.2f}")

    def test_top_scores_are_ordered_desc(self):
        """Top_scores should be in descending order."""
        from agents.top30_selector import Top30Selector

        agent = Top30Selector()
        result = agent.run()

        scores = result.get("top_scores", [])
        assert scores == sorted(scores, reverse=True), "top_scores should be sorted descending"

    def test_cutoff_is_lowest_of_top30(self):
        """The cutoff_score should be the minimum score that made the cut."""
        from agents.top30_selector import Top30Selector

        agent = Top30Selector()
        result = agent.run()

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT MIN(viral_score) 
                FROM articles 
                WHERE id = ANY(%s) AND top_30_selected = TRUE
                """,
                (self.inserted_ids,)
            )
            min_selected_score = cur.fetchone()[0]

        if min_selected_score is not None:
            assert abs(result["cutoff_score"] - float(min_selected_score)) < 0.01, \
                f"cutoff_score {result['cutoff_score']} != db min {min_selected_score}"


# ─── TEST 2: HeadlineGenerator ────────────────────────────────────────────────

MOCK_GEMINI_RESPONSE = {
    "headline": "SCIENTISTS DISCOVER WATER ON MARS",
    "highlight_words": ["WATER", "MARS"],
    "subtext": "NASA confirms liquid water traces in Martian subsurface.",
    "tag": "technology",
}

SAMPLE_ARTICLE = {
    "title": "Scientists Discover Water on Mars",
    "summary": "NASA has confirmed the presence of liquid water below the Martian surface using ground-penetrating radar.",
    "category": "technology",
    "is_breaking": False,
}

class TestHeadlineGenerator:
    """Mock the Gemini API call, validate returned structure and constraints."""

    def _make_mock_client(self, payload: dict):
        """Build a mock genai.Client whose .models.generate_content() returns payload as text."""
        mock_response = MagicMock()
        mock_response.text = json.dumps(payload)
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    def _run_with_mock(self, payload: dict) -> dict:
        """Reload module, patch Client, instantiate agent, run generate()."""
        import agents.headline_generator as hg_mod
        import importlib
        importlib.reload(hg_mod)

        mock_client = self._make_mock_client(payload)

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-test-key"}):
            with patch.object(hg_mod.genai, "Client", return_value=mock_client):
                agent = hg_mod.HeadlineGenerator()
                return agent.generate(SAMPLE_ARTICLE), mock_client

    def test_all_required_keys_present(self):
        """All 4 required keys must exist in the returned dict."""
        result, _ = self._run_with_mock(MOCK_GEMINI_RESPONSE)

        required_keys = {"headline", "highlight_words", "subtext", "tag"}
        assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"
        print(f"\n  ✓ HeadlineGenerator: all required keys present → {list(result.keys())}")

    def test_highlight_words_in_headline(self):
        """Every highlight word must appear in the headline (case-insensitive)."""
        result, _ = self._run_with_mock(MOCK_GEMINI_RESPONSE)

        headline_upper = result["headline"].upper()
        for hw in result["highlight_words"]:
            assert hw.upper() in headline_upper, \
                f"highlight_word '{hw}' not found in headline '{result['headline']}'"
        print(f"\n  ✓ HeadlineGenerator: highlight_words {result['highlight_words']} all in '{result['headline']}'")

    def test_tag_is_valid_enum(self):
        """The tag must be one of the allowed values."""
        valid_tags = {"breaking", "sports", "finance", "politics", "technology", "world"}
        result, _ = self._run_with_mock(MOCK_GEMINI_RESPONSE)

        assert result["tag"] in valid_tags, \
            f"tag '{result['tag']}' not in valid set {valid_tags}"
        print(f"\n  ✓ HeadlineGenerator: tag '{result['tag']}' is valid")

    def test_headline_is_uppercase(self):
        """The headline field must be uppercase."""
        result, _ = self._run_with_mock(MOCK_GEMINI_RESPONSE)

        assert result["headline"] == result["headline"].upper(), \
            "Headline must be all-uppercase"
        print(f"\n  ✓ HeadlineGenerator: headline is uppercase")

    def test_fallback_when_no_gemini_key(self):
        """Without a Gemini key, should still return a valid fallback dict."""
        import agents.headline_generator as hg_mod
        import importlib
        importlib.reload(hg_mod)

        env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_without_key, clear=True):
            agent = hg_mod.HeadlineGenerator()
            result = agent.generate(SAMPLE_ARTICLE)

        required_keys = {"headline", "highlight_words", "subtext", "tag"}
        assert required_keys.issubset(result.keys()), "Fallback must have all required keys"
        print(f"\n  ✓ HeadlineGenerator: fallback returned correctly when no API key")


# ─── TEST 3: SummarisationAgent Ollama→Gemini Fallback ───────────────────────

class TestSummarisationFallback:
    """Make Ollama unreachable, confirm Gemini fallback is triggered."""

    def setup_method(self):
        self.conn = get_conn()
        clear_test_articles(self.conn)

        # Seed exactly 1 top30_selected article
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO articles
                    (url, headline, full_text, source, status, viral_score, top_30_selected)
                VALUES (%s, %s, %s, %s, 'top30_selected', 75.0, TRUE)
                RETURNING id
                """,
                (
                    "http://test-summ-fallback.example.com",
                    "Climate Summit Reaches Historic Agreement On Carbon",
                    "World leaders gathered in Geneva to sign a landmark climate accord. " * 10,
                    "TestSource",
                ),
            )
            self.article_id = cur.fetchone()[0]
        self.conn.commit()

    def teardown_method(self):
        clear_test_articles(self.conn)
        self.conn.close()

    def test_gemini_fallback_used_when_ollama_down(self):
        """Point Ollama at a bad URL → agent should fall back to Gemini."""
        import importlib
        import agents.summarisation_agent as sam

        bad_ollama_url = "http://127.0.0.1:19999/api/generate"  # nothing listening here

        # Build mock client: client.models.generate_content() returns non-empty text
        mock_response = MagicMock()
        mock_response.text = "A 100-word summary about climate accord signed in Geneva by world leaders."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch.dict(os.environ, {
            "OLLAMA_URL": bad_ollama_url,
            "GEMINI_API_KEY": "fake-gemini-key",
        }):
            importlib.reload(sam)
            with patch.object(sam.genai, "Client", return_value=mock_client):
                agent = sam.SummarisationAgent()
                metrics = agent.run()

        # client.models.generate_content should have been called at least once
        assert mock_client.models.generate_content.called, \
            "Gemini client.models.generate_content was never called — fallback not triggered"

        fallback_calls = mock_client.models.generate_content.call_count
        assert fallback_calls >= 1, \
            f"Expected ≥1 Gemini calls (one per caption format), got {fallback_calls}"

        print(f"\n  ✓ SummarisationAgent: Gemini fallback triggered {fallback_calls} times when Ollama was down")
        print(f"    metrics = {metrics}")


# ─── TEST 4: PublishingAgent Retry Logic ─────────────────────────────────────

class TestPublishingAgentRetry:
    """Insert article with twitter=failed, retry_count=1. Assert retry increments."""

    def setup_method(self):
        self.conn = get_conn()
        clear_test_articles(self.conn)

        platform_status = json.dumps({"twitter": "failed", "telegram": "posted"})

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO articles
                    (url, headline, full_text, source, status, viral_score,
                     top_30_selected, platform_status, retry_count, image_path)
                VALUES (%s, %s, %s, %s, 'image_ready', 80.0,
                        TRUE, %s, 1, NULL)
                RETURNING id
                """,
                (
                    "http://test-retry.example.com",
                    "Test Retry Article For Publishing Agent",
                    "Article full text. " * 20,
                    "TestSource",
                    platform_status,
                ),
            )
            self.article_id = cur.fetchone()[0]
        self.conn.commit()

    def teardown_method(self):
        clear_test_articles(self.conn)
        self.conn.close()

    def test_retry_count_incremented(self):
        """After running PublishingAgent, retry_count should be incremented."""
        from agents.publishing_agent import PublishingAgent

        # Give it a Twitter token so it actually tries; the mock will fail
        with patch.dict(os.environ, {"X_BEARER_TOKEN": "fake-x-token"}):
            agent = PublishingAgent()

            # Force _post_twitter to fail (simulates API rejection)
            agent._post_twitter = MagicMock(return_value=(False, "api_error"))

            metrics = agent.run()

        # Reload DB state
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT retry_count, platform_status FROM articles WHERE id = %s",
                (self.article_id,)
            )
            row = cur.fetchone()

        assert row is not None, "Article not found in DB after agent run"
        new_retry_count = row["retry_count"]
        new_platform_status = row["platform_status"]
        if isinstance(new_platform_status, str):
            new_platform_status = json.loads(new_platform_status)

        assert new_retry_count > 1, \
            f"Expected retry_count > 1 (incremented from 1), got {new_retry_count}"

        print(f"\n  ✓ PublishingAgent: retry_count incremented to {new_retry_count}")
        print(f"    platform_status = {new_platform_status}")

    def test_failed_platform_stays_in_retry_queue(self):
        """Article with twitter=failed + retry_count < 3 must remain accessible to pipeline."""
        from agents.publishing_agent import PublishingAgent

        with patch.dict(os.environ, {"X_BEARER_TOKEN": "fake-x-token"}):
            agent = PublishingAgent()
            agent._post_twitter = MagicMock(return_value=(False, "api_error"))
            agent.run()

        # Article should NOT be in a terminal state (not permanently_failed and not discarded)
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT status, retry_count, platform_status FROM articles WHERE id = %s",
                (self.article_id,)
            )
            row = cur.fetchone()

        assert row is not None, "Article not found"
        new_status = row["status"]
        ps = row["platform_status"]
        if isinstance(ps, str):
            ps = json.loads(ps)

        # After 2 failures total (retry_count was 1, now 2) → not permanently_failed yet
        assert ps.get("twitter") != "permanently_failed", \
            "twitter should not be permanently_failed after only 2 attempts (< 3)"

        # Telegram was already posted — overall status could be 'published' due to partial success
        print(f"\n  ✓ PublishingAgent: twitter still in retry queue, status={new_status}, platform_status={ps}")
