ALTER TABLE articles ADD COLUMN IF NOT EXISTS viral_score INT DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_breaking BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS cluster_id INT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS merged_from TEXT;

CREATE TABLE IF NOT EXISTS trending_keywords (
    id SERIAL PRIMARY KEY,
    keyword TEXT,
    region TEXT,
    rank INT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS story_clusters (
    id SERIAL PRIMARY KEY,
    primary_article_id INT REFERENCES articles(id),
    member_article_ids TEXT,
    similarity_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trending_keywords_keyword ON trending_keywords (keyword);
