-- Pipeline control
ALTER TABLE articles ADD COLUMN IF NOT EXISTS top_30_selected BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS processing_stage TEXT DEFAULT 'raw';

-- Content generation
ALTER TABLE articles ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS captions JSONB;

-- Image generation
ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_source TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_prompt TEXT;

-- Publishing
ALTER TABLE articles ADD COLUMN IF NOT EXISTS platform_status JSONB;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS retry_count INT DEFAULT 0;

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

CREATE INDEX IF NOT EXISTS idx_articles_top30 ON articles (top_30_selected);
CREATE INDEX IF NOT EXISTS idx_articles_stage ON articles (processing_stage);
