# Autonomous AI Viral News System Blueprint

## 1. Full System Architecture
The system transitions from a linear script to an asynchronous, event-driven architecture using **RabbitMQ/Redis** for queuing and **Celery** for distributed task execution.

**Core Components:**
- **Central Orchestrator (Watchdog):** A supervisor process that monitors queue depths, agent health, and triggers recovery protocols.
- **Message Broker (Redis/RabbitMQ):** Manages the state transitions and passes article IDs between agents.
- **PostgreSQL Database:** The central source of truth for article states, analytics, and metadata.
- **Agents as Microservices:** Each agent (Discovery, Scoring, Generation, Publishing) runs independently and scales horizontally.

## 2. Status Lifecycle & Database Schema

### Article State Machine (Status Lifecycle)
Articles move through a strict state machine:
`fetched` ➔ `filtered` ➔ `ranked` ➔ `approved` (or `discarded`) ➔ `summarized` ➔ `image_ready` ➔ `caption_ready` ➔ `queued` ➔ `published` (or `failed` ➔ `retrying`)

### Database Schema (PostgreSQL)

```sql
CREATE TYPE article_status AS ENUM (
    'fetched', 'filtered', 'ranked', 'approved', 'discarded',
    'summarized', 'image_ready', 'caption_ready', 'scheduled', 'queued', 'published', 'failed', 'retrying'
);

CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    headline TEXT NOT NULL,
    full_text TEXT,
    source TEXT,
    published_date TIMESTAMPTZ,
    category TEXT,
    status article_status DEFAULT 'fetched',
    viral_score FLOAT DEFAULT 0.0,
    sentiment_score FLOAT DEFAULT 0.0,
    cluster_id INT, -- For deduplication
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE article_media (
    id SERIAL PRIMARY KEY,
    article_id INT REFERENCES articles(id),
    visual_json JSONB,
    generated_prompt TEXT,
    image_url TEXT,
    vision_validated BOOLEAN DEFAULT FALSE,
    platform_format TEXT -- e.g., 'portrait', 'landscape', 'square'
);

CREATE TABLE social_posts (
    id SERIAL PRIMARY KEY,
    article_id INT REFERENCES articles(id),
    platform TEXT, -- 'x', 'instagram', 'linkedin', 'facebook'
    caption TEXT,
    hashtags TEXT[],
    scheduled_time TIMESTAMPTZ,
    posted_time TIMESTAMPTZ,
    status TEXT, -- 'pending', 'published', 'failed'
    error_log TEXT,
    retry_count INT DEFAULT 0
);

CREATE TABLE analytics (
    id SERIAL PRIMARY KEY,
    post_id INT REFERENCES social_posts(id),
    views INT DEFAULT 0,
    likes INT DEFAULT 0,
    shares INT DEFAULT 0,
    comments INT DEFAULT 0,
    clicks INT DEFAULT 0,
    collected_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 3. Queue & Scheduler System

**Queue Design (Celery + Redis):**
- `discovery_queue`: Fast-running scrapers.
- `nlp_queue`: Summarization and sentiment analysis.
- `gpu_queue`: Image generation (rate-limited/concurrency restricted).
- `publishing_queue`: Outbound API calls.
- `retry_queue`: Backoff queue for failed tasks.

**Scheduler Logic (Celery Beat):**
- Runs Discovery every 5 mins.
- Runs Analytics Sync every 1 hour.
- Predicts optimal posting times and dispatches tasks to `publishing_queue` with an ETA (Estimated Time of Arrival).

## 4. News Filtering & Deduplication

**Massive Flooding Fix:**
1. **Source Trust Filtering:** Drop articles from blacklisted or low-trust domains immediately.
2. **Deduplication (Semantic Clustering):** 
   - Compute embeddings of headlines using a fast model (e.g., `all-MiniLM-L6-v2`).
   - Use DBSCAN or FAISS to cluster articles. 
   - Keep only the article from the highest-trust source in the cluster; mark others as `merged/discarded`.

## 5. Trending News & Viral Score Engine

AI scores news before processing using a weighted formula:
* `viral_score = (W1*Recency) + (W2*SourceTrust) + (W3*ClusterSize) + (W4*Controversy) + (W5*Urgency)`

**Algorithm:**
- **Cluster Size (Mentions):** More duplicates = bigger story.
- **Controversy/Emotion:** LLM fast-pass evaluates emotional impact (1-10).
- **Celebrity/Brand Entities:** Presence of trending entities bumps score.
- **Action:** Only top 5% of articles per hour transition to `approved`. The rest are `discarded`.

## 6. Perfect Image Generation Engine

Fixes the "random image" problem through a rigid 6-step pipeline.

**STEP 1: Deep Extraction (LLM)**
LLM extracts entities. Output format: JSON.

**STEP 2: Visual JSON Output**
```json
{
  "brand": "Apple",
  "product": "futuristic smart glasses",
  "place": "keynote stage California",
  "mood": "premium futuristic",
  "style": "cinematic product launch",
  "camera": "dramatic close shot"
}
```

**STEP 3: Auto-Prompt Generation**
Template: `[Style], [Brand] [Product] at [Place], [Mood] atmosphere, [Camera], photorealistic, 8k, highly detailed, no text, no watermark.`

**STEP 4: Category Templates Strategy**
Use stable diffusion Loras or Midjourney style references specific to categories (e.g., Politics = press conference template).

**STEP 5: Vision AI Validation**
Pass generated image + headline to a Vision Model (e.g., GPT-4o or Claude 3.5 Sonnet).
*Prompt:* "Does this image accurately represent this headline? Are there misspelled words, deformed faces, or wrong contexts? Return JSON: `{'valid': true/false, 'reason': '...'}`."
*Action:* If false, auto-retry up to 2 times.

**STEP 6: Fallback System**
If generation fails 3 times, fetch a Pexels/Unsplash premium API image using safe keywords, and overlay the text using the `visual_generation_agent.py` script.

## 7. Viral Caption Engine & Multi-Platform Distribution

**Agent Prompt (Platform Specific):**
- **X:** "Act as a debate-starter. Write a punchy 2-sentence hook about this news. Ask a polarizing question. Include 2 hashtags."
- **LinkedIn:** "Act as an industry analyst. Provide 3 bullet points of insights from this news. Professional tone. Include 3 hashtags."
- **Instagram:** "Act as a digital creator. Write an emotionally engaging caption. Use emojis. Direct users to link in bio."

**Best Posting Time Engine:**
- Analyzes past `analytics` table.
- Groups engagement by `(platform, hour_of_day, day_of_week)`.
- Updates the `scheduled_time` for the post to the historical peak hour for that category.

## 8. Social Posting Engine & Retry System

- **Posting Engine:** Decoupled API workers. Handles rate limits using Redis token buckets.
- **Retry System:** Celery `autoretry_for=(requests.exceptions.RequestException, APIError)`, `max_retries=5`, `countdown=exponential_backoff`.
- **Silent Failure Fix:** If max retries reached, status goes to `failed`, and a Telegram alert is sent to the admin.

## 9. Auto Analytics Learning Engine

**The Feedback Loop:**
1. **Track:** Fetch API metrics daily (views, likes, CTR).
2. **Learn:** LLM analyzes top 10 posts vs bottom 10 posts weekly.
3. **Optimize:** LLM outputs updated "Style Guidelines" JSON (e.g., "Stop using red colors for finance news").
4. **Apply:** Generation and Caption agents dynamically load these JSON guidelines into their system prompts.

## 10. Monitoring, Logging & Failure Recovery

- **Monitoring Stack:** 
  - Prometheus + Grafana for visualizing queue lengths, success rates, API latency.
  - Sentry for Python exception tracking.
- **Watchdog:** A script running every minute checking if `Celery` workers are alive. If dead, `systemctl restart celery`.
- **Failure Recovery:** Dead Letter Exchanges (DLX) in RabbitMQ catch permanently failed tasks for manual review.

## 11. Recommended Folder Structure

```text
d:\PROJECTS\NA\
├── agents\                 # Core AI logic
│   ├── discovery.py        # Scrapers, RSS feeds
│   ├── filter_dedupe.py    # Embeddings, clustering
│   ├── trending_score.py   # LLM scoring
│   ├── caption_engine.py   # Multi-platform text generation
│   ├── image_engine.py     # Prompt gen, validation, fallback
│   └── feedback_loop.py    # Analytics sync and learning
├── workers\                # Celery task definitions
│   ├── celery_app.py
│   ├── tasks_nlp.py        
│   ├── tasks_media.py      
│   └── tasks_social.py     
├── database\
│   ├── schema.sql
│   └── db_client.py
├── orchestrator\           # Central brain
│   ├── scheduler.py        # Beat schedules
│   └── watchdog.py         # System health monitor
├── config\
│   ├── platforms.json      # API keys, rate limits
│   └── brand_config.json   
├── logs\
└── docker-compose.yml      # For Redis, Postgres, Prometheus
```

## 12. Implementation Roadmap

**Phase 1: Foundation (Days 1-3)**
- Setup Postgres schema with strict `article_status`.
- Implement Redis + Celery infrastructure.
- Migrate `NewsDiscoveryAgent` to push to queue instead of running synchronously.

**Phase 2: Intelligence & Filtering (Days 4-6)**
- Build deduplication using sentence embeddings.
- Implement the Trending Score Engine to cull 90% of junk news automatically.

**Phase 3: The Image Pipeline (Days 7-10)**
- Build the 6-step image engine.
- Integrate Vision AI validation to guarantee zero bad images.

**Phase 4: Multi-Platform & Posting (Days 11-13)**
- Implement robust social API posting with exponential backoff.
- Build platform-specific caption prompts.

**Phase 5: Autonomy & Analytics (Days 14-15)**
- Hook up Celery Beat for infinite, scheduled running.
- Build the feedback loop to pull analytics and adjust prompts.
- Deploy Grafana for monitoring.
