# Autonomous News System

A high-reliability, deterministic, and scalable multi-agent architecture for automated news discovery, processing, image generation, and cross-platform publishing.

## Local Setup (Docker Desktop)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Python 3.10+

### Quick Start

```bash
# 1. Clone and enter the project
git clone <repo_url> && cd <repo_directory>

# 2. Copy env template and fill in your Gemini API key
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here

# 3. Start PostgreSQL + Redis in Docker
docker compose up -d

# 4. Initialize the database (creates tables + runs migrations)
python scripts/setup_local.py

# 5. Start the backend API
python api/api.py

# 6. Start the pipeline worker (in a second terminal)
python main.py

# 7. Start the dashboard frontend
cd news-weaver/news-weaver-main && npm install && npm run dev
```

### Running Tests

```bash
# All 22 tests should pass with Docker running
python -m pytest tests/ -v
```

---

## 7-Stage Pipeline

The pipeline follows a strict, status-gated linear execution flow:

```
Stage 1: Discovery          raw            → approved
Stage 2: Viral Score        approved       → ranked
Stage 3: Dedup              ranked         → approved_unique
Stage 4: Top 30 Selector    approved_unique → top30_selected | discarded
Stage 5: Summarisation      top30_selected → summarised
Stage 6: Image Generation   summarised     → image_ready
Stage 7: Publishing         image_ready    → published | failed
```

Each stage:
- Checks for input articles **before** running (no-op if nothing to process)
- Is wrapped in `try/except` — a stage failure does **not** block the next stage
- Logs a row to `pipeline_runs` on completion

---

## Architecture

| Component | Purpose |
|-----------|---------|
| `agents/news_discovery_agent.py` | RSS/web scraping, deduplication |
| `agents/viral_score_engine.py` | Heuristic scoring for article ranking |
| `agents/duplicate_merger.py` | Semantic dedup via title similarity |
| `agents/top30_selector.py` | Filters top 30 by viral score |
| `agents/summarisation_agent.py` | Ollama → Gemini fallback captions |
| `agents/headline_generator.py` | Structured JSON headline via Gemini |
| `agents/image_renderer.py` | Pillow editorial template renderer |
| `agents/visual_generation_agent.py` | Orchestrates headline + image pipeline |
| `agents/publishing_agent.py` | Multi-platform publisher with retries |
| `api/api.py` | Flask REST API for the dashboard |
| `pipeline/master_pipeline.py` | Orchestrates all 7 stages |

---

## Deployment (Render.com)

A `render.yaml` is provided for zero-config deployment:
- **Web service**: Flask API via `gunicorn`
- **Worker service**: `main.py` background pipeline

Set all env vars in the Render dashboard (see `.env.example` for the full list).
