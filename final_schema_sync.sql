-- ============================================================
-- final_schema_sync.sql  — safe to run multiple times
-- ============================================================

-- Core tracking columns
ALTER TABLE articles ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS posted_at TIMESTAMPTZ;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS views INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS likes INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS shares INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS comments INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS clicks INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_status TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE articles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Viral score engine columns
ALTER TABLE articles ADD COLUMN IF NOT EXISTS viral_score INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS priority_level INTEGER DEFAULT 0;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_breaking BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS emotion TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS category_detected TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS score_breakdown_json JSONB;

-- Dedup / visual / publishing columns
ALTER TABLE articles ADD COLUMN IF NOT EXISTS duplicate_of_id TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS image_path TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS caption_json JSONB;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS posted_platforms_json JSONB;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS best_platform TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- Posting time engine columns
ALTER TABLE articles ADD COLUMN IF NOT EXISTS scheduled_post_json JSONB;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS priority_platform TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS post_immediately BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS next_post_at TIMESTAMPTZ;

-- Indexes (created AFTER columns are guaranteed to exist)
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_created_at_desc ON articles(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_viral_score_desc ON articles(viral_score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_priority_level_desc ON articles(priority_level DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_url_unique ON articles(url);
CREATE INDEX IF NOT EXISTS idx_articles_queue ON articles(status, priority_level DESC, viral_score DESC);

-- updated_at auto-trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trg_articles_updated_at ON articles;

CREATE TRIGGER trg_articles_updated_at
BEFORE UPDATE ON articles
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
