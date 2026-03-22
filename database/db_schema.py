import psycopg2

SQL = """
CREATE TABLE IF NOT EXISTS articles (
    id            SERIAL PRIMARY KEY,
    url           TEXT UNIQUE,
    headline      TEXT,
    full_text     TEXT,
    source        TEXT,
    published_date TIMESTAMPTZ,
    category      TEXT,
    status        TEXT DEFAULT 'new',
    viral_score   INT DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW()
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
