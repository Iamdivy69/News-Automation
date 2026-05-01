import psycopg2

SQL = """
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

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    stage TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    articles_in INT DEFAULT 0,
    articles_out INT DEFAULT 0,
    errors INT DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS feed_sources (
    id           SERIAL PRIMARY KEY,
    name         TEXT,
    url          TEXT UNIQUE,
    category     TEXT,
    language     TEXT DEFAULT 'en',
    active       BOOLEAN DEFAULT TRUE,
    last_checked TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS error_logs (
    id          SERIAL PRIMARY KEY,
    agent       TEXT,
    message     TEXT,
    stack_trace TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_status     ON articles (status);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles (created_at);
CREATE INDEX IF NOT EXISTS idx_articles_top30 ON articles (top_30_selected);
CREATE INDEX IF NOT EXISTS idx_articles_stage ON articles (processing_stage);
"""


def create_tables(conn_string: str) -> None:
    conn = psycopg2.connect(conn_string)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(SQL)
    finally:
        conn.close()


if __name__ == "__main__":
    conn_string = "host=localhost port=5432 dbname=news_system user=postgres"
    create_tables(conn_string)
    print("Tables and indexes created successfully.")
