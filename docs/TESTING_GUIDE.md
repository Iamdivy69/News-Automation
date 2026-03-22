# How to Test What You've Built

This guide provides step-by-step procedures to verify the infrastructure, database state, and autonomous pipelines of the News System.

## Step 1 — Run the existing `verify_setup.py`
You already have this from Phase 1. Run it first to confirm your infrastructure is still healthy:
```bash
python verify_setup.py
```
All 5 checks (Python, packages, Ollama, PostgreSQL, Redis) should still show **[OK]**.

## Step 2 — Test the Database Schema
Open your terminal and connect to PostgreSQL:
```bash
psql -h localhost -U postgres -d news_system
```
Then run:
```sql
\dt
```
You should see these tables listed: `articles`, `feed_sources`, `error_logs`, `trending_keywords`, `story_clusters`, `system_config`. 

Then check that the feeds were correctly seeded:
```sql
SELECT COUNT(*) FROM feed_sources WHERE active = true;
```
**Expected result**: 50 rows.

## Step 3 — Test the Discovery Agent in isolation
Run it directly from the terminal:
```bash
python news_discovery_agent.py
```
It should print something like `Found 12 new articles` (number varies). Then verify in PostgreSQL:
```sql
SELECT id, source, headline, status, created_at 
FROM articles 
ORDER BY created_at DESC 
LIMIT 10;
```
You should see real headlines with `status = 'new'`.

## Step 4 — Test the Intelligence Pipeline
Run it directly:
```bash
python intelligence_pipeline.py
```
Then verify each component worked with these queries:

### Check viral scores were assigned
```sql
SELECT headline, source, viral_score, is_breaking 
FROM articles 
ORDER BY viral_score DESC 
LIMIT 10;
```

### Check breaking news was fast-tracked
```sql
SELECT headline, viral_score, status 
FROM articles 
WHERE is_breaking = true;
```
*These items should show `status = 'approved'`, bypassing the standard 'new' queue.*

### Check duplicate merging happened
```sql
SELECT COUNT(*) FROM story_clusters;
SELECT COUNT(*) FROM articles WHERE status = 'merged';
```

### Check the intelligence summary log
```sql
SELECT agent, message, created_at 
FROM error_logs 
WHERE agent = 'intelligence' 
ORDER BY created_at DESC 
LIMIT 5;
```
