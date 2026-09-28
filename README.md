# Nexura — AI-Assisted Media Intelligence & Editorial Publishing Platform

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python Version"/></a>
  <a href="https://flask.palletsprojects.com/"><img src="https://img.shields.io/badge/Flask-3.1%2B-000000?style=flat-square&logo=flask&logoColor=white" alt="Flask Framework"/></a>
  <a href="https://www.postgresql.org/"><img src="https://img.shields.io/badge/PostgreSQL-15%2B%20(GIN%20%2F%20TSVector)-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"/></a>
  <a href="https://redis.io/"><img src="https://img.shields.io/badge/Redis-7%2B-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis"/></a>
  <a href="https://docs.celeryq.dev/"><img src="https://img.shields.io/badge/Celery-5.4%2B-37814A?style=flat-square&logo=celery&logoColor=white" alt="Celery Distributed Queue"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="MIT License"/></a>
  <a href="tests/"><img src="https://img.shields.io/badge/Tests-Passing-brightgreen?style=flat-square&logo=pytest&logoColor=white" alt="Pytest Status"/></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff Code Style" style="flat-square"/></a>
</p>

---

## Executive Overview

**Nexura** is an enterprise-grade media intelligence, content syndication, and editorial publishing platform engineered for high-throughput technical journalism and multimedia delivery. Built as a modular monolith adhering to a strict **Layered Service-Repository Architecture**, Nexura harmonizes automated multi-channel ingestion, Natural Language Processing (NLP), and editorial oversight with a responsive, personalized reader experience.

The platform continuously aggregates articles and video broadcasts from global feeds, extracts clean semantic text, scores sentiment and readability, detects duplicate coverage, and benchmarks publishing readiness through an automated **Editorial Readiness Index (ERI)**. Newsrooms and editorial teams utilize a centralized control plane featuring **Demand vs. Supply gap intelligence**, **momentum velocity tracking**, and automated **multi-platform syndication drafting**, while readers benefit from full-text discovery, personalized affinity feeds, and secure interactive discussions.

---

## Key Capabilities & System Highlights

### 1. Multi-Source Ingestion Pipeline
* **Multi-Provider Ingestion Orchestration:** Scheduled workers query NewsAPI.ai, YouTube Data API v3, and syndicated RSS feeds for breaking technology journalism and media broadcasts.
* **Semantic Document Extraction:** Leverages Diffbot Knowledge Graph and Trafilatura to extract structured article bodies, lead paragraphs, publication metadata, high-resolution imagery, and author attributions.
* **Transformer-Based NLP Enrichment:** Real-time sentiment classification and polarity scoring powered by transformer inference pipelines.
* **Transactional Reliability & Savepoints:** Every ingested item executes within isolated database transaction savepoints (`SAVEPOINT`), guaranteeing that third-party network timeouts or parsing anomalies never leave orphaned records or corrupted discovery queues.

### 2. Data Integrity & Editorial Quality Gates
* **Three-Tier Deduplication Engine:**
  * *Exact Match:* Deterministic URL canonicalization and SHA-256 URI fingerprinting.
  * *Fuzzy Token Shingling:* N-gram tokenization and MinHash/Jaccard similarity preventing cross-syndicated wire republication.
  * *Semantic Clustering:* Entity collision detection across shared taxonomy classifications.
* **Editorial Readiness Index (ERI):** Automated heuristic rubric evaluating submissions across five dimensions:
  1. *Substance Density:* Word count validation and structural paragraph distribution.
  2. *Readability Level:* Reading ease assessment tailored for technical audiences.
  3. *Sentiment Polarity:* Confidence thresholding on model inference classifications.
  4. *Entity Graph Completeness:* Relational linkage to canonical brand, organization, and concept entities.
  5. *Media Asset Quality:* Aspect ratio and attribution validation for featured hero assets.
* **Deterministic Lifecycle (FSM):** Enforces a state-machine progression:
  `discovered` &rarr; `scraped` &rarr; `processed` &rarr; `scored` &rarr; `published` / `rejected`.

### 3. Full-Text Search & Discovery
* **PostgreSQL Native TSVECTOR & GIN Indexing:** High-performance lexical search utilizing generated `tsvector` columns with language-specific stemming indexed via Generalized Inverted Indexes (`GIN`).
* **Weighted Document Relevance:** Hierarchical term weighting using PostgreSQL `setweight`:
  * **Weight A:** Headline & Primary Title
  * **Weight B:** Subtitle, Editorial Hook & Summary
  * **Weight C:** Full Markdown & Sanitized Body Content
  * **Weight D:** Taxonomy Tags, Brands & Concept Entities
* **Multi-Signal Hybrid Ranking:** Balances text relevance with temporal freshness decay, engagement volume, and reader affinity.
* **Trigram Autocomplete:** Real-time search suggestions powered by PostgreSQL `pg_trgm` GIN indexes.

### 4. Personalized Reader Portal & Community
* **Dynamic User Affinity Vectors:** Implicit and explicit telemetry tracking calculates personalized category, section, and entity weights based on reader interactions (reading history, likes, bookmarks).
* **Curated User Library:** Private reader collections, bookmark organization, reading progression tracking, and view history.
* **Threaded, Sanitized Discussions:** Interactive nested commentary secured by strict whitelist sanitization via `bleach` and `DOMPurify` rules.
* **Double Opt-In Newsletter Engine:** RFC 8058 compliant newsletter distribution supporting cryptographic confirmation tokens and one-click unsubscribe headers.

### 5. Editorial Control Plane & Media Intelligence
* **Demand vs. Supply Gap Matrix:** Correlates real-time reader search queries against published category volume to identify unmet editorial demand.
* **Momentum Velocity Tracking:** Calculates interaction velocity over rolling windows (1h, 6h, 24h) to surface breakout stories.
* **Content Decay Detection:** Analyzes engagement half-life to alert editors when high-value evergreen content requires updates.
* **Deduplication Workbench:** Visual editorial console to compare conflicting coverage, merge sources, and resolve cluster collisions.
* **Multi-Platform Syndication Generator:** Automated draft generation of channel-optimized social copy, hashtags, and UTM campaign parameters for major social distribution platforms.

---

## Architectural Topology & Design Patterns

Nexura is architected as a **Layered Service-Repository Modular Monolith**, enforcing strict separation of concerns, high testability, and isolated failure domains:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION / HTTP LAYER                       │
│      Flask Blueprints · Jinja2 Templates · CSS3 Design System · AJAX    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Request / ViewModel
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         SERVICE / DOMAIN LAYER                         │
│   EmailService · ContentService · InteractionService · IngestionPipeline│
│   Deduplication · QualityGate · RecommendationService · SearchService  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Domain Entities / Transactions
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA ACCESS / REPO LAYER                        │
│   ContentRepo · ArticleRepo · UserRepo · SearchRepo · AnalyticsRepo    │
│            SQLAlchemy 2.0 ORM · Eager Loading Strategies               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ SQL Queries / GIN / Savepoints
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE & INFRASTRUCTURE LAYER                  │
│       PostgreSQL 15+ (Relational + TSVector) · Redis (Cache/Broker)    │
│              Celery Workers / Beat · Alembic Migrations                │
└────────────────────────────────────────────────────────────────────────┘
```

### The Polymorphic Content Hub Pattern

To support diverse media types (long-form articles, tutorials, video broadcasts) without schema redundancy, Nexura employs a **Polymorphic Content Hub** design:

* **`contents` Table (The Central Spine):** Single source of truth for platform-wide concerns: UUIDs, title, slug, publication status, view/like/share counters, primary taxonomy, and full-text search vectors.
* **Specialized Payload Tables (`articles`, `videos`):** Joined 1-to-1 with `contents.id` to house type-specific payloads (markdown body, reading time, Diffbot dump vs. YouTube video ID, duration, channel metadata).
* **Polymorphic Interactions:** Engagement entities (`views`, `saves`, `reactions`, `comments`) attach directly to `contents.id`, ensuring uniform reporting and aggregate metrics across all content types.

---

## Technology Stack

| Component | Technology | Rationale / Purpose |
|---|---|---|
| **Core Framework** | Python 3.11+ / Flask 3.1+ | Application Factory pattern, lightweight, deterministic execution |
| **Database & ORM** | PostgreSQL 15+ / SQLAlchemy 2.0+ | Relational integrity, ACID compliance, GIN full-text indexation |
| **Schema Migrations** | Alembic / Flask-Migrate | Version-controlled, reproducible transactional DDL migrations |
| **Distributed Queue** | Celery 5.4+ / Redis 7+ | Asynchronous ingestion pipelines, batch analytics, background tasks |
| **Scheduler** | Celery Beat / APScheduler | Periodic RSS/API ingestion polling and decay calculation sweeps |
| **Caching Layer** | Redis / Flask-Caching | Multi-tier caching for hot feeds, sitemaps, and taxonomy trees |
| **Authentication & IAM**| Flask-Login / Authlib | Session authentication, RBAC, Google OAuth 2.0 with OIDC Nonce |
| **NLP & Ingestion** | Diffbot API / HuggingFace / Trafilatura | Article semantic extraction, entity resolution, sentiment scoring |
| **Security & Sanitization** | Bleach / Flask-WTF / Flask-Limiter | CSRF protection, HTML XSS neutralization, distributed rate limiting |
| **Frontend Architecture**| Jinja2 / CSS3 Design Tokens / Vanilla JS | High-performance, zero-bundle overhead, custom theme tokens |
| **Testing & Quality** | Pytest / Pytest-Flask / Ruff | Unit/integration testing suite, sub-second linting, PEP 8 formatting |

---

## Security & Architecture Hardening

Nexura incorporates enterprise security best practices across all layers:

* **Decoupled Verification & Reset Lifecycles:** Dedicated database columns and independent cryptographic token lifecycles for email verification (`email_verification_token`) and password recovery (`password_reset_token`).
* **Account Verification Gates:** Enforced verification checks during authentication, supported by rate-limited token regeneration endpoints.
* **Cryptographic OAuth Nonce Validation:** OpenID Connect `nonce` parameter enforcement across OAuth authorization redirects and token exchange callbacks.
* **Content Security Policy (CSP):** Nonce-based CSP headers dynamically injected on all HTTP responses:
  ```http
  Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-...'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; object-src 'none'; base-uri 'self';
  ```
* **Security Headers Suite:** Standard enforcement of `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`.
* **Rate Limiting & Abuse Prevention:** Granular endpoint throttling via Redis-backed `Flask-Limiter` across sensitive authentication and interactive endpoints.
* **Credential Protection:** Salted `scrypt` and `pbkdf2:sha256` password hashing combined with client-side and server-side entropy validation.

---

## Directory & Module Structure

```
Nexura/
├── app/
│   ├── __init__.py               # Application factory (create_app) & blueprint registration
│   ├── extensions.py             # Extension singletons (db, migrate, limiter, mail, cache, oauth)
│   ├── caching.py                # Cache invalidation helpers & key generators
│   │
│   ├── models/                   # Declarative SQLAlchemy domain models
│   │   ├── content.py            # Unified Content hub, ContentEntity junction, facets
│   │   ├── article.py            # Article payload, ArticleSource, ArticleAuthor
│   │   ├── video.py              # Video payload & YouTube metadata
│   │   ├── user.py               # User accounts, verification tokens, NewsletterSubscriber
│   │   ├── taxonomy.py           # Sections, Categories, Brands, Entities
│   │   ├── interaction.py        # Views, Saves, Reactions (Likes/Dislikes), Comments
│   │   ├── recommendation.py     # Impression & click telemetry models
│   │   └── distribution.py       # Syndication platforms & generated post logs
│   │
│   ├── repositories/             # Data access layer (SQLAlchemy query encapsulation)
│   │   ├── content_repo.py       # Content hub queries, polymorphic eager loading
│   │   ├── article_repo.py       # Article CRUD, draft management, batch status
│   │   ├── video_repo.py         # Video listings & duration filters
│   │   ├── user_repo.py          # User retrieval, password updates, bookmark libraries
│   │   ├── search_repo.py        # PostgreSQL TSVECTOR, GIN ranking, trigram suggestions
│   │   └── analytics_repo.py     # Editorial matrix, velocity, momentum, decay metrics
│   │
│   ├── services/                 # Pure domain business logic & orchestration
│   │   ├── email_service.py      # Transactional emails (verification, reset) with fallback
│   │   ├── content_service.py    # Article publishing FSM & editorial approval flows
│   │   ├── interaction_service.py# Reaction toggles, polymorphic bookmarking, comments
│   │   ├── recommendation_service.py # User affinity scoring & personalized feed generation
│   │   ├── search_service.py     # Query normalization, multi-signal ranking, autocomplete
│   │   ├── syndication_service.py# Multi-platform social copy & UTM link generator
│   │   ├── newsletter_service.py # Double opt-in subscriptions & verification dispatch
│   │   └── scheduler_service.py  # Background job lifecycle & task orchestration
│   │
│   ├── ingestion/                # External harvesting & enrichment pipeline
│   │   ├── pipeline.py           # Master ingestion loop with transaction savepoints
│   │   ├── newsapi_client.py     # NewsAPI.ai client integration
│   │   ├── youtube_client.py     # YouTube Data API v3 integration
│   │   ├── diffbot_client.py     # Diffbot article text & metadata extraction
│   │   ├── huggingface_client.py # Sentiment analysis & entity inference API
│   │   ├── normalizer.py         # Payload normalization into unified schemas
│   │   ├── deduplication.py      # URL hash, MinHash, & Jaccard shingle similarity
│   │   ├── quality_gate.py       # Editorial Readiness Index (ERI) calculator
│   │   ├── validation.py         # Pydantic schema validation for external feeds
│   │   └── task_tracker.py       # Ingestion task execution logging & state monitoring
│   │
│   ├── routes/                   # HTTP Controller Blueprints
│   │   ├── public.py             # Reader portal: Home, Sections, Story views, RSS
│   │   ├── auth.py               # Register, login, verification, OAuth, password reset
│   │   ├── interactions.py       # AJAX endpoints for likes, saves, comments, shares
│   │   ├── library.py            # User private reading library & collections
│   │   ├── seo.py                # Dynamic XML sitemaps (/sitemap_index.xml), robots.txt
│   │   └── admin/                # Editorial Control Plane
│   │       ├── contents.py       # Content workbench, manual editor, ERI inspector
│   │       ├── ingestions.py     # Ingestion pipelines trigger & task monitors
│   │       ├── deduplication.py  # Deduplication collision workbench & resolver
│   │       ├── moderation.py     # Comment moderation queue & user management
│   │       ├── taxonomy.py       # Category, Section, and Entity governance
│   │       └── syndication.py    # Social distribution drafts & campaign tracker
│   │
│   ├── serializers/              # JSON serializable data transfer schemas
│   └── utils/                    # Security, sanitization, slugify, and health readiness
│
├── migrations/                   # Alembic schema version migrations
│   ├── env.py                    # Migration execution environment
│   └── versions/                 # Linear, immutable migration scripts
│
├── static/                       # UI assets (CSS design tokens, vanilla JS)
│   ├── css/                      # Modular CSS design system (layout, components, typography)
│   └── js/                       # Core client scripts (interactions, analytics, search)
│
├── templates/                    # Semantic Jinja2 template hierarchies
│   ├── public/                   # Public reader pages (article, home, video, library)
│   ├── auth/                     # Authentication views & transactional HTML email templates
│   ├── admin/                    # Editorial control plane views & intelligence matrices
│   └── macros/                   # Reusable UI component macros (cards, comments, badges)
│
├── tests/                        # Comprehensive Pytest test suite
├── config.py                     # Environment-aware configuration classes
├── main.py                       # WSGI entrypoint for web workers
├── requirements.txt              # Production Python dependency manifests
└── pyproject.toml                # Build configuration & Ruff code quality settings
```

---

## Getting Started & Local Development

### Prerequisites
* **Python:** Version `3.11` or `3.12`
* **PostgreSQL:** Version `15+` with `pg_trgm` extension installed
* **Redis:** Version `7+` (for caching, rate limiting, and task queues)

### 1. Repository Setup & Virtual Environment

```bash
# Clone the repository
git clone https://github.com/your-username/nexura.git
cd nexura

# Create and activate an isolated virtual environment
python -m venv venv

# On Linux/macOS:
source venv/bin/activate
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the project root by copying the template:

```bash
cp .env.example .env
```

Ensure the following critical environment variables are populated:

```env
# Flask Core
FLASK_ENV=development
SECRET_KEY=your_secret_key_here

# Database Connectivity (PostgreSQL)
DATABASE_URL=postgresql+psycopg2://username:password@localhost:5432/nexura_db

# Distributed Cache & Task Broker
REDIS_URL=redis://localhost:6379/0

# Ingestion & AI Intelligence APIs
DIFFBOT_TOKEN=your_diffbot_api_token
NEWSAPI_AI_API_KEY=your_newsapi_ai_token
YOUTUBE_API_KEY=your_google_youtube_api_key
HUGGINGFACE_API_KEY=your_huggingface_api_token
HF_API_URL=https://api-inference.huggingface.co/models/your-sentiment-model

# Google OAuth 2.0 Credentials
GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret

# Mail Dispatch (SMTP)
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_smtp_username
MAIL_PASSWORD=your_smtp_password
MAIL_DEFAULT_SENDER=Nexura Editorial <noreply@example.com>
MAIL_ENABLED=False  # Set to True in staging/production to enable live dispatch
```

### 4. Database Initialization & Migrations

```bash
# Apply all linear Alembic database migrations
flask db upgrade
```

### 5. Running the Application

#### Development Server:
```bash
flask run --host=127.0.0.1 --port=5000 --debug
```

#### Production Server (Gunicorn WSGI):
```bash
gunicorn --workers=4 \
         --threads=2 \
         --bind=0.0.0.0:8000 \
         --access-logfile=- \
         --error-logfile=- \
         main:app
```

#### Distributed Background Workers (Celery):
```bash
# Start Celery asynchronous worker
celery -A app.celery_worker.celery worker --loglevel=info -c 4

# Start Celery periodic beat scheduler
celery -A app.celery_worker.celery beat --loglevel=info
```

The application will be accessible at **`http://localhost:5000`** (or `http://localhost:8000` under Gunicorn).

---

## Testing & Quality Assurance

Nexura maintains a test suite verifying routes, database operations, service layers, and security barriers:

```bash
# Execute full test suite
pytest

# Run tests with verbose output and test coverage report
pytest -v --cov=app --cov-report=term-missing
```

### Code Formatting & Static Analysis

Nexura utilizes [Ruff](https://github.com/astral-sh/ruff) for linting and code formatting conforming to PEP 8:

```bash
# Check for linting violations and code errors
ruff check .

# Automatically apply safe fixes and imports reordering
ruff check . --fix

# Format codebase
ruff format .
```

---

## Deployment & Operational Hardening

For production environments (Docker, Kubernetes, or Cloud VMs), observe the following operational checklist:

* **Session Security:** Ensure `SESSION_COOKIE_SECURE=True` and `SESSION_COOKIE_SAMESITE=Strict` in production (configured automatically in `config.py` under `ProductionConfig`).
* **Connection Pooling:** Configure SQLAlchemy connection pool limits (`pool_size=20`, `max_overflow=40`, `pool_pre_ping=True`) to maintain connection health during traffic surges.
* **Static Assets & CDN:** In high-volume production deployments, serve static assets via an edge CDN (Cloudflare, AWS CloudFront).
* **Reverse Proxy Headers:** Always deploy behind a reverse proxy (Nginx, Caddy, Cloudflare) with `X-Forwarded-For` and `X-Forwarded-Proto` enabled to ensure accurate client IP resolution and rate-limiting enforcement.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for complete details.

---

<p align="center">
  <sub>Nexura Editorial Publishing Platform &copy; All rights reserved.</sub>
</p>
