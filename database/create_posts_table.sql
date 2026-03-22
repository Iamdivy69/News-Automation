CREATE TABLE IF NOT EXISTS posts (
    id               SERIAL PRIMARY KEY,
    article_id       INT REFERENCES articles(id),
    platform         TEXT NOT NULL,
    post_id          TEXT,
    posted_at        TIMESTAMPTZ DEFAULT NOW(),
    status           TEXT DEFAULT 'published',
    engagement_score FLOAT DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_posts_platform_date
ON posts (platform, posted_at);
ALTER TABLE pipeline_runs
ADD COLUMN IF NOT EXISTS published INT DEFAULT 0;
