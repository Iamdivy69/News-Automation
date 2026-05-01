-- ============================================================
-- Run this SQL once to clear stale articles immediately
-- ============================================================
-- Deletes articles older than 12 hours that have NOT been processed
-- (summarised, publish_approved, or published). Safe to run any time.
-- ============================================================

DELETE FROM articles
WHERE created_at < NOW() - INTERVAL '12 hours'
  AND status IN ('new', 'discarded', 'merged', 'approved');

-- Verify result:
-- SELECT status, COUNT(*) FROM articles GROUP BY status ORDER BY status;
