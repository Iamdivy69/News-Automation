# Intelligence & Pipeline Enhancements

This document tracks the advanced architectural additions built to act as the core brain of the Autonomous AI News System.

## 1. Database Schema Extensions (`extend_schema.sql`)
The PostgreSQL database was extended to support advanced AI features and analytics, without disrupting the existing tables.
- **`articles` Table Expansion**: Added columns `viral_score` (INT), `is_breaking` (BOOLEAN), `cluster_id` (INT), and `merged_from` (TEXT).
- **`trending_keywords` Table**: Added for tracking dynamic topic popularity over time by region.
- **`story_clusters` Table**: Stores identically matched or highly related articles mapped to a primary article, along with its specific similarity threshold.
- **`system_config` Table**: Simple Key/Value table for persistent global variables or crawler flags.

## 2. Text Deduplication (`duplicate_merger.py`)
- **`DuplicateMerger`**: Developed a fully functional natural language processing class.
- **TF-IDF & Cosine Similarity**: Uses `scikit-learn` to vectorize article bodies mathematically. Items yielding a similarity of `0.80` or greater are actively grouped.
- **Merge Strategy**: The article with the highest `viral_score` is automatically nominated as the canonical source. All derivative articles within that cluster are flipped to `status = 'merged'` to maintain database hygiene and prevent redundant downstream processing.

## 3. Viral and Breaking Scoring (`viral_score_engine.py`)
- **`ViralScoreEngine`**: An evaluation engine developed to proxy the velocity or virality of incoming news content.
- **Breaking News Detection**: Scans for high-urgency keywords (e.g., *breaking*, *urgent*, *exclusive*) to flag critical world events in real-time.

## 4. Master Orchestrator (`intelligence_pipeline.py`)
- **`IntelligencePipeline`**: The main execution loop coordinating all autonomous subsystems.
- **Flow**:
  1. Executes `NewsDiscoveryAgent` to scrape new RSS payloads.
  2. Iterates over newly fetched articles and requests analysis from the `ViralScoreEngine`.
  3. **Fast-tracking**: Instantly intercepts any article returning `is_breaking = True` and promotes its status directly to `'approved'`, bypassing standard approval queues.
  4. Triggers `DuplicateMerger` to deduplicate and cluster the remaining standard items.
  5. Finalizes by writing an aggregate summary `{ "scored": X, "merged": Y, "breaking": Z }` into `error_logs` for historical monitoring.
