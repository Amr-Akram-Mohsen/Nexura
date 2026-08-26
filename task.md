# Nexura Phase 7 — Task List

## Phase A — Discovery [DONE]
- [x] Read PHASE_7_MASTER_TRUTH.md completely
- [x] Read BUILD_NEXURA.md completely
- [x] Inspect legacy Nexora/ project structure
- [x] Inspect all 11 Alembic migration revisions
- [x] Inspect actual database schema (psql \d)
- [x] Verify row counts for all relevant tables
- [x] Verify brands-entities overlap (all 24 brands have entity slug matches)
- [x] Identify schema deltas needed
- [x] Create database backup (nexora_db_backup_phase7_prebuild.dump)
- [x] Confirm alembic_version = cffe9cd40bfc

## Phase B — Foundation [DONE]
- [x] requirements.txt
- [x] .env.example
- [x] .flaskenv
- [x] config.py (DevelopmentConfig, ProductionConfig, TestingConfig)
- [x] main.py (WSGI entry)
- [x] app/__init__.py (create_app factory)
- [x] app/extensions.py (db, migrate, login_manager, limiter, cache, mail, csrf)

## Phase C — Database (Models + Alembic) [DONE]
- [x] app/models/__init__.py
- [x] app/models/taxonomy.py (Section, Category, Entity, Location, IntentFacet, GenderFacet, PriceTierFacet, Event)
- [x] app/models/source.py (Source)
- [x] app/models/content.py (Content, Article, ArticleSource, Author, article_authors, article_categories)
- [x] app/models/video.py (Video, VideoComment)
- [x] app/models/user.py (User, NewsletterSubscriber, ContactMessage)
- [x] app/models/interaction.py (View, Save, Reaction, Comment, Share)
- [x] app/models/recommendation.py (UserInterest, UserEntityInterest, RecommendationImpression, RecommendationClick)
- [x] app/models/distribution.py (DistributionPlatform, DistributionPost)
- [x] migrations/ (Alembic init, env.py, stamp head, write delta migrations)
- [x] Migration 0001: phase7_schema_delta (add videos.channel_id; restructure comments/shares; contents indexes)
- [x] Migration 0002: phase7_brands (update all 24 brand entity_types to 'brand')
- [x] Migration 0003: phase7_align (views, saves, user_interests, distribution_posts, user reset columns)
- [x] Full database backup verified (`nexora_db_backup_phase7_prebuild.dump` 52.8 MB)
- [x] Verified 100% column match and ORM queries across all 33 tables without data loss

## Phase D — Query/Serialization Layer
- [ ] app/repositories/content_repo.py
- [ ] app/repositories/article_repo.py
- [ ] app/repositories/video_repo.py
- [ ] app/repositories/taxonomy_repo.py
- [ ] app/repositories/user_repo.py
- [ ] app/repositories/search_repo.py
- [ ] app/repositories/analytics_repo.py
- [ ] app/serializers/content_serializers.py (serialize_content_card, serialize_content_detail)
- [ ] app/serializers/utils.py (compact_dict)
- [ ] app/utils/sanitizer.py (4-stage HTML pipeline)
- [ ] app/utils/readiness.py (Editorial Readiness Index 0-100)
- [ ] app/utils/slugify.py

## Phase E — Ingestion Pipeline
- [ ] app/ingestion/task_tracker.py (atomic JSON state files)
- [ ] app/ingestion/normalizer.py (URL canonicalization, text normalization)
- [ ] app/ingestion/deduplication.py (Jaccard >= 0.85)
- [ ] app/ingestion/quality_gate.py (word_count > 250 AND image_url)
- [ ] app/ingestion/newsapi_client.py
- [ ] app/ingestion/youtube_client.py
- [ ] app/ingestion/diffbot_client.py
- [ ] app/ingestion/huggingface_client.py
- [ ] app/ingestion/pipeline.py (orchestration)

## Phase F — Public Routes + Frontend
- [ ] app/routes/public.py (home, section, category, topic, article, video, search)
- [ ] app/routes/seo.py (sitemap_index, sitemap_N)
- [ ] app/cache.py (cache keys, TTLs, cascaded invalidation)
- [ ] static/css/tokens.css (design system tokens)
- [ ] static/css/layout.css
- [ ] static/css/components.css
- [ ] static/js/core.js (global event delegation)
- [ ] static/js/search.js (autocomplete + TreeWalker highlighting)
- [ ] static/js/video.js (YouTube facades)
- [ ] templates/base.html (dark mode, skip-to-content, meta tags, CSRF)
- [ ] templates/macros/content_card.html
- [ ] templates/macros/pagination.html
- [ ] templates/macros/meta_tags.html
- [ ] templates/public/home.html
- [ ] templates/public/section.html
- [ ] templates/public/category.html
- [ ] templates/public/topic.html
- [ ] templates/public/article.html
- [ ] templates/public/video.html
- [ ] templates/public/search.html
- [ ] templates/public/library.html

## Phase G — Auth + Community
- [ ] app/routes/auth.py (register, login, logout, verify, reset, OAuth)
- [ ] app/routes/library.py
- [ ] app/routes/interactions.py (handle-interaction, comments/submit, subscribe)
- [ ] app/services/interaction_service.py
- [ ] templates/auth/*.html
- [ ] static/css/auth.css

## Phase H — Recommendations + Analytics
- [ ] app/services/recommendation_service.py (multi-signal formula)
- [ ] app/services/analytics_service.py (momentum, decay, demand/supply, CTR feedback)
- [ ] app/services/search_service.py (4-component scoring)
- [ ] app/services/content_service.py

## Phase I — Admin Control Plane
- [ ] app/routes/admin/__init__.py (admin_required decorator)
- [ ] app/routes/admin/ingestions.py
- [ ] app/routes/admin/contents.py
- [ ] app/routes/admin/taxonomy.py
- [ ] app/routes/admin/deduplication.py
- [ ] app/routes/admin/moderation.py
- [ ] app/services/syndication_service.py
- [ ] static/css/admin.css
- [ ] static/js/admin.js
- [ ] templates/admin/*.html

## Phase J — Performance + Hardening
- [ ] Rate limiting (subscribe: 5/min, handle-interaction: 30/min)
- [ ] CSRF on all mutating endpoints
- [ ] N+1 audit (joinedload / selectinload)
- [ ] SEO: canonical URLs, OG/Twitter cards, noindex for filter combos, sitemap
- [ ] Accessibility: skip-to-content, focus trapping, aria-labels, reduced-motion
- [ ] Redis support with SimpleCache fallback

## Phase K — Verification + Compliance
- [ ] tests/ (pytest suite)
- [ ] Migration validation script
- [ ] Phase 7 compliance audit report
