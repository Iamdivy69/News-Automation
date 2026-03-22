CREATE TABLE IF NOT EXISTS summaries (
    id SERIAL PRIMARY KEY,
    article_id INT REFERENCES articles(id) ON DELETE CASCADE UNIQUE,
    twitter_text TEXT,
    linkedin_text TEXT,
    instagram_caption TEXT,
    facebook_text TEXT,
    hashtags TEXT,
    tone TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_summaries_article_id ON summaries(article_id);

ALTER TABLE articles ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'new';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.table_constraints 
        WHERE table_name = 'articles' AND constraint_name = 'articles_status_check'
    ) THEN
        ALTER TABLE articles 
        ADD CONSTRAINT articles_status_check 
        CHECK (status IN ('new', 'approved', 'summarised', 'merged', 'needs_review'));
    END IF;
END $$;
