UPDATE articles SET status = 'publish_approved'
WHERE id IN (
    SELECT a.id FROM articles a
    JOIN summaries s ON a.id = s.article_id
    JOIN images i ON a.id = i.article_id
    WHERE a.status = 'summarised'
    ORDER BY a.viral_score DESC
    LIMIT 5
);
SELECT id, headline, viral_score FROM articles
WHERE status = 'publish_approved';
