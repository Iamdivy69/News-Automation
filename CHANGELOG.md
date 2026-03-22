# Changelog

## Recent Updates

### Added
- **Dashboard Search**: Added a headline search bar to the sidebar in the Articles Feed.
- **Dashboard Counts**: Appended live exact article counts next to the Status and Category filters in the dashboard sidebar.
- **API Search Endpoint**: Added a `search` query parameter to `GET /api/articles` to allow for case-insensitive partial matches (`ILIKE`).
- **Task Scheduling**: Created a complete `celery_app.py` module to automate the execution of `MasterPipeline` every 30 minutes via Celery Beat + Redis.
- **Pipeline Metrics**: Implemented a dedicated logging system in `MasterPipeline.run()` to record full execution durations and aggregated metrics into a structured `pipeline_runs` table.
- **Phase 5 Configuration prep**: Initialized the `config/` directory with `__init__.py` and an empty `brand_config.json` stub.
- **Automated Social Branding**: Introduced a comprehensive `BrandingLayer` (`config/branding_layer.py`) to systematically apply brand styling, tone guarantees, auto-insert custom hashtag prefixes, dynamically strip banned/sensationalist terminology, and seamlessly append standard brand signatures directly to generated text outputs. Also supports localized alpha-overlay watermarking of media assets using the Pillow library.
- **Brand Configuration Profile**: Activated `config/brand_config.json` to act as the rigid, centralized data profile containing styling constraints and operational rules.
- **Visual Generation Agent**: Engineered `agents/visual_generation_agent.py` utilizing Pillow to procedurally export 1200x630 aesthetically branded social media compositions per article.
- **Image Serving Node**: Launched `GET /api/articles/<id>/image` inside the Flask core handling native MIME-mapped binary distribution of the cached graphics directly to the web client.

### Changed
- **Viral Scoring Engine**: Completely rewrote the `ViralScoreEngine.score()` method to use a robust, deterministic point assignment algorithm (factoring in source reputation, publication recency, headline length, and keyword matches), removing all prior randomization.
- **Article Promotion Logic**: Upgraded `IntelligencePipeline._update_article_score()` to proactively upgrade non-breaking articles to `approved` status if their viral score mathematically crosses the high-value threshold (`>= 60`).
- **API Backend Refactor**: Replaced raw standalone `psycopg2` queries throughout `api/api.py` with an optimized **SQLAlchemy** engine connection pool configured with `pool_size=5`, `max_overflow=10`, and `pool_pre_ping=True`.
- **SummarisationAgent Pipeline**: Integrated the `BrandingLayer` securely into the core compilation cycle inside `SummarisationAgent.run()` so output texts (Twitter, LinkedIn, Instagram, Facebook, and operational hashtags) automatically undergo rigorous tone filtering before committing to the database alongside an `is_branded = TRUE` toggle.
- **Pipeline Graphics Extraction**: Extended `MasterPipeline.run()` natively via `Phase 3` integrations to seamlessly cross-reference articles missing `.png` deliverables and iteratively execute visual generations scaling neatly down to the local `/images/` directory structure.
- **Dashboard Interactive Imagery**: Constructed intelligent networking hooks straight into `dashboard.py` expansion nodes using conditional Streamlit fetching mechanisms that render auto-generated headline media live into the core monitoring feed.

### Fixed
- **Service Orchestrator Paths**: Corrected broken paths in `scripts/start_services.py` due to project restructuring (`api.py` -> `api/api.py`, `dashboard.py` -> `dashboard/dashboard.py`).
- **Ollama Timeout Protections**: Implemented a hard limit of `50` articles per batch explicitly ordered by viral score in `SummarisationAgent.run()` to prevent inference timeouts under severe system load constraints.
- **Batch Processing Resiliency**: Shifted the `try/except` boundary block inside of the active looping structure in `SummarisationAgent.run()` so a single article inference failure logs an error independently without aggressively wiping out the entire batch transaction logic.
