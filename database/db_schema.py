import psycopg2

SQL = """
-- ================================================================
-- Core articles table (full unified schema)
-- ================================================================
CREATE TABLE IF NOT EXISTS articles (
    -- Original Core
    id            SERIAL PRIMARY KEY,
    url           TEXT UNIQUE,
    headline      TEXT,
    full_text     TEXT,
    source        TEXT,
    published_date TIMESTAMPTZ,
    category      TEXT,
    status        TEXT DEFAULT 'new',
    viral_score   INT DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    
    -- Extended & Sync Schema
    last_error    TEXT,
    posted_at     TIMESTAMPTZ,
    views         INT DEFAULT 0,
    likes         INT DEFAULT 0,
    shares        INT DEFAULT 0,
    comments      INT DEFAULT 0,
    clicks        INT DEFAULT 0,
    image_status  TEXT,
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    priority_level INT DEFAULT 0,
    is_breaking   BOOLEAN DEFAULT FALSE,
    emotion       TEXT,
    category_detected TEXT,
    score_breakdown_json JSONB,
    duplicate_of_id TEXT,
    duplicate_confidence FLOAT DEFAULT 0,
    duplicate_reason TEXT,
    image_path    TEXT,
    caption_json  JSONB,
    posted_platforms_json JSONB,
    best_platform TEXT,
    retry_count   INT DEFAULT 0,
    scheduled_post_json JSONB,
    priority_platform TEXT,
    post_immediately BOOLEAN DEFAULT FALSE,
    next_post_at  TIMESTAMPTZ,

    -- Pipeline control
    top_30_selected BOOLEAN DEFAULT FALSE,
    processing_stage TEXT DEFAULT 'raw',

    -- Content generation
    summary TEXT,
    captions JSONB,

    -- Image generation
    image_url TEXT,
    image_source TEXT,
    image_prompt TEXT,

    -- Publishing
    platform_status JSONB,
    published_at TIMESTAMPTZ
);

-- ================================================================
-- Pipeline runs — unified schema (supports both old and new cols)
-- ================================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              SERIAL PRIMARY KEY,
    stage           TEXT,
    run_type        TEXT DEFAULT 'stage',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    articles_in     INT DEFAULT 0,
    articles_out    INT DEFAULT 0,
    errors          INT DEFAULT 0,
    error_message   TEXT,
    notes           TEXT,
    -- Master pipeline summary columns
    discovered      INT DEFAULT 0,
    scored          INT DEFAULT 0,
    merged          INT DEFAULT 0,
    breaking        INT DEFAULT 0,
    summarised      INT DEFAULT 0,
    images_generated INT DEFAULT 0,
    published       INT DEFAULT 0,
    duration_sec    FLOAT DEFAULT 0
);

-- ================================================================
-- Feed sources
-- ================================================================
CREATE TABLE IF NOT EXISTS feed_sources (
    id           SERIAL PRIMARY KEY,
    name         TEXT,
    url          TEXT UNIQUE,
    category     TEXT,
    language     TEXT DEFAULT 'en',
    active       BOOLEAN DEFAULT TRUE,
    last_checked TIMESTAMPTZ
);

-- ================================================================
-- Summaries (social media content for each article)
-- ================================================================
CREATE TABLE IF NOT EXISTS summaries (
    id                 SERIAL PRIMARY KEY,
    article_id         INT UNIQUE REFERENCES articles(id) ON DELETE CASCADE,
    twitter_text       TEXT,
    linkedin_text      TEXT,
    instagram_caption  TEXT,
    facebook_text      TEXT,
    hashtags           TEXT,
    tone               TEXT,
    is_branded         BOOLEAN DEFAULT FALSE,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- Images (generated/fetched images per article)
-- ================================================================
CREATE TABLE IF NOT EXISTS images (
    id           SERIAL PRIMARY KEY,
    article_id   INT REFERENCES articles(id) ON DELETE CASCADE,
    image_path   TEXT,
    image_type   TEXT DEFAULT 'portrait',
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- Posts (publishing log per platform)
-- ================================================================
CREATE TABLE IF NOT EXISTS posts (
    id               SERIAL PRIMARY KEY,
    article_id       INT REFERENCES articles(id) ON DELETE CASCADE,
    platform         TEXT NOT NULL,
    status           TEXT DEFAULT 'pending',
    post_id          TEXT,
    posted_at        TIMESTAMPTZ,
    engagement_score FLOAT DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- System config (key-value store)
-- ================================================================
CREATE TABLE IF NOT EXISTS system_config (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ================================================================
-- Error logs
-- ================================================================
CREATE TABLE IF NOT EXISTS error_logs (
    id          SERIAL PRIMARY KEY,
    agent       TEXT,
    message     TEXT,
    stack_trace TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ================================================================
-- Indexes
-- ================================================================
CREATE INDEX IF NOT EXISTS idx_articles_status          ON articles (status);
CREATE INDEX IF NOT EXISTS idx_articles_created_at      ON articles (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_viral_score     ON articles (viral_score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_priority_level  ON articles (priority_level DESC);
CREATE INDEX IF NOT EXISTS idx_articles_top30           ON articles (top_30_selected);
CREATE INDEX IF NOT EXISTS idx_articles_stage           ON articles (processing_stage);
CREATE INDEX IF NOT EXISTS idx_articles_queue           ON articles (status, priority_level DESC, viral_score DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_url_unique ON articles (url);

CREATE INDEX IF NOT EXISTS idx_summaries_article_id     ON summaries (article_id);
CREATE INDEX IF NOT EXISTS idx_images_article_id        ON images (article_id);
CREATE INDEX IF NOT EXISTS idx_posts_article_id         ON posts (article_id);
CREATE INDEX IF NOT EXISTS idx_posts_platform           ON posts (platform);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs (started_at DESC);

-- ================================================================
-- updated_at trigger for articles
-- ================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_articles_updated_at ON articles;

CREATE TRIGGER trg_articles_updated_at
BEFORE UPDATE ON articles
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
"""

EXPECTED_TABLES = [
    "articles", "pipeline_runs", "feed_sources",
    "summaries", "images", "posts", "system_config", "error_logs"
]


def create_tables(conn_string: str) -> None:
    conn = psycopg2.connect(conn_string)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(SQL)
    finally:
        conn.close()


def verify_tables(conn_string: str) -> list[str]:
    """Returns list of table names that are missing."""
    conn = psycopg2.connect(conn_string)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """)
            existing = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()
    return [t for t in EXPECTED_TABLES if t not in existing]


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    conn_string = os.environ.get("DATABASE_URL")
    if not conn_string:
        raise ValueError("DATABASE_URL not found in environment.")
    create_tables(conn_string)
    missing = verify_tables(conn_string)
    if missing:
        print(f"[WARN] Still missing tables: {missing}")
    else:
        print("All tables and indexes created successfully.")
