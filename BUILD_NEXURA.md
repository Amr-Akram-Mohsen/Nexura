# NEXORA — PHASE 7 REBUILD EXECUTION PROMPT

## 0. ROLE

You are the principal software architect and implementation engineer responsible for rebuilding the Nexura content platform.

You are working inside a NEW project directory named:

    Nexura/

The previous implementation exists separately as:

    Nexora/

`Nexora/` is the legacy/reference project.

Your job is NOT to modify or clean up `Nexora`.

Your job is to build a NEW Nexura implementation inside the current `Nexura/` directory according to:

    PHASE_7_MASTER_TRUTH.md

That document is the authoritative architectural, domain, database, functional, performance, security, SEO, accessibility, and technology specification.

---

# 1. ABSOLUTE AUTHORITY

Read `PHASE_7_MASTER_TRUTH.md` completely before creating or modifying implementation files.

The Phase 7 document is the authoritative target state.

Do not silently reinterpret, simplify, remove, or replace requirements from it.

Do not introduce technologies, architectures, domain concepts, tables, routes, or features that conflict with it.

If something in the legacy project conflicts with Phase 7:

    Phase 7 wins.

The legacy project is evidence of the existing implementation and database state, NOT the authority for the new architecture.

---

# 2. LEGACY PROJECT BOUNDARY

The directory:

    ../Nexora/

or the actual legacy project location discovered during inspection

must be treated as READ-ONLY reference material.

NEVER:

- modify files inside `Nexora`
- delete files inside `Nexora`
- rename files inside `Nexora`
- remove legacy tables merely because Phase 7 excludes them
- rewrite its migrations
- alter its Git history
- "clean up" its source code
- migrate the legacy project itself into the new architecture

The old project must remain intact as a fallback/reference point.

All new implementation work belongs inside:

    Nexura/

---

# 3. PRIMARY OBJECTIVE

Build a clean, production-oriented Nexura application from the ground up inside this directory.

The resulting project must implement the architecture defined by:

    PHASE_7_MASTER_TRUTH.md

while intelligently reusing compatible knowledge and implementation patterns from:

    Nexora/

The rebuild must preserve existing valuable database data wherever the Phase 7 target schema allows it.

Do NOT assume that rebuilding the application means destroying and recreating the database.

Database migration must be treated as a separate, deliberate engineering task.

---

# 4. REQUIRED INITIAL WORK — DO NOT SKIP

Before implementing substantial application code, perform a complete inspection of both:

A. `PHASE_7_MASTER_TRUTH.md`

B. `Nexora/`

The inspection must cover at minimum:

- project structure
- Python environment/configuration
- Flask application factory
- SQLAlchemy models
- Alembic configuration
- all Alembic revisions
- database configuration
- existing database schema if accessible
- routes/controllers
- services
- repositories/query layers
- background workers
- ingestion code
- NewsAPI integration
- YouTube integration
- Diffbot integration
- authentication
- authorization
- templates
- CSS
- JavaScript
- serializers/DTOs
- caching
- search
- recommendation logic
- analytics
- administrative functionality
- tests
- configuration/environment handling

Do not start deleting or replacing things during this inspection.

First understand what exists.

---

# 5. CREATE AN INTERNAL REBUILD ANALYSIS

Before major implementation, create a temporary/internal analysis of:

    CURRENT LEGACY STATE
                ↓
    PHASE 7 TARGET STATE
                ↓
    REQUIRED TRANSFORMATIONS

Classify existing components as:

1. PRESERVE
   Compatible with Phase 7 and reusable.

2. ADAPT
   Useful implementation exists but must be changed to satisfy Phase 7.

3. REBUILD
   Existing implementation conflicts with the new architecture and should be implemented cleanly again.

4. REPLACE
   Existing implementation exists but Phase 7 explicitly requires a different architecture.

5. EXCLUDE
   Explicitly removed by Phase 7 and must not appear in the new application.

6. NEW
   Required by Phase 7 but absent from the legacy implementation.

Do not blindly copy the old project.

Do not blindly discard the old project.

Use engineering judgment based on the Phase 7 target.

---

# 6. EXPLICITLY EXCLUDED LEGACY FUNCTIONALITY

The new Nexura implementation MUST NOT reintroduce the concepts explicitly excluded by Phase 7.

In particular, do not recreate:

- Product
- ProductVariant
- ProductStoreLink
- commercial product catalog
- AliExpress integrations
- Amazon integrations
- eBay integrations
- BestBuy integrations
- Noon integrations
- Jarir integrations
- affiliate buy buttons
- price comparison bars
- merchant redirect tracking
- `/product-click/`
- product/article affiliate matching
- product opportunity analytics
- commercial intelligence dashboards
- Reddit/forum `Post` models
- forum-specific scoring
- other commercial or forum concepts removed by Phase 7

These exclusions apply to:

- database models
- database tables
- routes
- services
- repositories
- templates
- JavaScript
- APIs
- analytics
- admin pages
- background jobs
- shared utilities

Do not accidentally reintroduce them through copied legacy code.

---

# 7. DATABASE IS A MIGRATION TARGET, NOT A BLANK SLATE

This is one of the most important requirements.

The existing Nexura database may contain valuable data.

Therefore:

DO NOT simply:

    DROP DATABASE
    DROP TABLE
    recreate everything

unless an explicit future instruction authorizes that.

Instead:

1. Inspect the existing database schema.
2. Inspect existing Alembic migration history.
3. Determine which existing tables correspond to Phase 7.
4. Compare columns, constraints, indexes and foreign keys.
5. Determine which existing data can be preserved.
6. Determine which schema changes are required.
7. Create safe Alembic migrations from the current state toward the Phase 7 target state.
8. Test migrations against a copy of the existing database before applying destructive changes.
9. Verify data preservation after migration.

The migration must be based on the ACTUAL existing database state.

Never assume that the old SQLAlchemy models alone perfectly describe the live database.

---

# 8. DATABASE PRESERVATION PRINCIPLE

For every Phase 7 table, determine whether the corresponding legacy table already exists.

For compatible structures:

    preserve existing table
    preserve existing records
    add/modify only what is necessary

For required new structures:

    create them through migrations

For required columns:

    add them through migrations

For changed constraints:

    migrate them safely

For changed relationships:

    migrate foreign keys/junction tables carefully

For data that cannot directly satisfy the new structure:

    write an explicit data migration

Never silently discard data.

Never use destructive SQL merely to make Alembic happy.

---

# 9. DATABASE MIGRATION SAFETY

Every migration must be designed with the following principle:

    DATA FIRST, STRUCTURE SECOND.

Before any potentially destructive operation:

- determine whether the affected table contains data
- determine whether the data can be transformed
- create an appropriate migration path
- preserve data whenever possible
- document genuinely unavoidable destructive operations
- test the migration

Examples of operations that require particular caution:

- dropping columns
- changing column types
- renaming columns
- changing nullable constraints
- replacing foreign keys
- changing unique constraints
- removing legacy relationships
- merging taxonomy entities
- restructuring user-interest data

Do not assume a table is empty.

Verify it.

If a table is known to be empty, that may simplify the migration, but the fact must be verified rather than guessed.

---

# 10. PHASE 7 DATABASE CONTRACT

The target database must conform to the schema defined in Section 5 of:

    PHASE_7_MASTER_TRUTH.md

Preserve:

- table names
- column names
- data types
- nullable requirements
- default values
- foreign keys
- ON DELETE behavior
- unique constraints
- indexes
- compound indexes
- check constraints

unless a specific, explicit Phase 7 requirement establishes otherwise.

Do not omit fields because they appear unused at first.

Do not simplify tables for convenience.

Do not replace relational structures with JSON merely because it is easier.

The Phase 7 schema is the contract.

---

# 11. SQLALCHEMY IMPLEMENTATION

Implement the Phase 7 relational schema using SQLAlchemy 2.x.

Models must accurately represent:

- fields
- relationships
- foreign keys
- constraints
- indexes
- cascade behavior

Use appropriate SQLAlchemy relationship loading strategies.

Avoid N+1 queries.

Use:

- `joinedload`
- `selectinload`

appropriately according to relationship cardinality and query requirements.

Do not create a giant single models file.

Organize domain models into clean modules.

---

# 12. CONTENT ARCHITECTURE

Implement the Phase 7 unified content architecture.

`Content` is the public/master content aggregator.

`Article` owns written article-specific data.

`Video` owns video-specific data.

The implementation must preserve the distinction between:

- platform/on-site engagement metrics
- external YouTube metrics

Do not merge those metrics incorrectly.

`contents.title` and `contents.published_at` remain authoritative for public listing/search/feed presentation.

---

# 13. INGESTION ARCHITECTURE

Implement the Phase 7 ingestion lifecycle.

The architecture must support:

- NewsAPI discovery
- YouTube discovery
- deduplication
- Article creation
- Video creation
- Content creation
- Diffbot deep extraction
- normalization
- quality gating
- taxonomy enrichment
- search-vector population
- publication
- failure retention
- background processing

Maintain the two-phase article lifecycle:

    Phase 1
    Light Discovery
        ↓
    Phase 2
    Deep Diffbot Extraction

Do not turn this into a synchronous request-time scraping architecture.

---

# 14. QUALITY GATES

Implement the Phase 7 worker-level binary quality gate exactly:

    word_count > 250
    AND
    image_url IS NOT NULL

Passing:

    article.status = published
    content.is_published = true

Failing:

    article.status = failed

Retain failed records for administrative inspection.

Do not confuse the binary worker gate with the 0–100 Editorial Readiness Index.

Both systems must exist independently.

---

# 15. DEDUPLICATION

Implement:

- title normalization
- URL canonicalization
- tracking parameter removal
- rolling 7-day duplicate detection
- token Jaccard similarity
- threshold `>= 0.85`
- canonical article selection
- secondary source linking

When a duplicate is identified:

DO NOT create a second public Content record.

Instead, preserve the additional source through `article_sources`.

---

# 16. TAXONOMY

Implement the full Phase 7 taxonomy architecture.

Respect all eight dimensions:

1. Sections
2. Categories
3. Topics/Entities
4. Brands/Entities
5. Geographic Locations
6. Editorial Intent
7. Gender
8. Price Tier

Do not collapse these dimensions simply because some currently contain little data.

Implement taxonomy relationships according to the Phase 7 schema.

---

# 17. SEARCH

Implement PostgreSQL full-text search using:

    contents.search_vector

and the Phase 7 weighting model.

Implement:

    /search

and:

    /api/search/suggestions

Autocomplete must obey the specified minimum query length and caching requirements.

Do not introduce Elasticsearch unless explicitly instructed later.

PostgreSQL is the search foundation defined by Phase 7.

---

# 18. PUBLIC WEBSITE

Build the public website using:

- Flask 3.x
- Jinja2
- server-side rendering
- semantic HTML
- vanilla JavaScript
- custom CSS

Do not introduce:

- React
- Vue
- Angular
- Next.js
- Tailwind
- SPA architecture

The public routes must conform to Section 12 of Phase 7.

---

# 19. FRONTEND PERFORMANCE

Respect the Phase 7 frontend invariants.

Use:

- global event delegation
- progressive reveal
- YouTube facades
- non-destructive TreeWalker highlighting
- IntersectionObserver
- CSS design tokens
- dark/light mode
- reduced-motion support

Do not introduce unnecessary JavaScript frameworks or dependencies.

Do not create dozens of redundant event listeners when event delegation is appropriate.

---

# 20. DTO BOUNDARY

ORM models must not be passed directly into JSON responses or treated as the public API contract.

Implement the Phase 7 DTO/serialization boundary.

At minimum support concepts equivalent to:

    serialize_content_card
    serialize_content_detail
    compact_dict

Keep serialization separate from ORM definitions.

---

# 21. CACHING

Implement the Phase 7 caching architecture and TTLs.

Respect:

- layout cache
- homepage/feed cache
- filter cache
- content-page cache
- unified-search cache
- autocomplete cache

Implement normalized filter keys.

Implement cascading invalidation.

Redis should be supported as the distributed cache backend when configured.

Provide an appropriate development fallback when Redis is unavailable, consistent with the Phase 7 configuration contract.

---

# 22. RECOMMENDATIONS

Implement the deterministic recommendation architecture defined by Phase 7.

Do not replace it with opaque machine-learning embeddings unless explicitly instructed later.

Implement:

- shared topics
- shared brands
- same category
- same section
- recency decay
- popularity scaling
- user interests
- user entity interests
- personalized discovery
- recommendation impressions
- recommendation clicks

Keep recommendation behavior auditable and explainable.

---

# 23. ANALYTICS

Implement the Phase 7 closed-loop analytics architecture.

Support:

- demand vs supply
- opportunity gap
- 7-day momentum
- 14-day momentum
- traffic decay
- recommendation CTR
- strategy mismatch detection
- hook/title failure detection
- content mismatch detection

Do not introduce commercial/product analytics removed by Phase 7.

---

# 24. ADMIN CONTROL PLANE

Implement the six Phase 7 administrative areas:

1. Ingestion Health & Task Monitoring
2. Content Library & Batch Operations
3. Editorial Inspection & Extraction Quality
4. Deduplication Workbench
5. Taxonomy & Entity Merge Workbench
6. Community Safety & Discussion Moderation

Admin functionality must be protected by the Phase 7 authorization rules.

---

# 25. BACKGROUND TASKS

Implement isolated background processing consistent with Phase 7.

The architecture must support:

- TaskTracker
- background daemon workers where specified
- application context handling
- scoped database sessions
- rollback on failure
- progress tracking
- atomic task-state JSON writes
- corrupted-state recovery

Do not block normal HTTP requests while performing long-running ingestion/extraction work.

Do not create a monolithic worker module.

---

# 26. EXTERNAL APIs

Implement resilient provider clients for:

- NewsAPI
- YouTube Data API
- Diffbot
- HuggingFace

Respect the timeout, retry, and fallback policies defined in Phase 7.

External provider failures must not crash the Flask application.

Use clear provider-specific service boundaries.

Do not scatter API calls throughout routes and templates.

---

# 27. AUTHENTICATION AND SECURITY

Implement:

- secure password hashing
- password strength validation
- email verification
- password reset
- Google OAuth
- CSRF protection
- admin authorization
- rate limiting
- input sanitization
- HTML sanitization
- secure session handling

Follow the Phase 7 security contract.

Never store plaintext passwords.

Never trust user-provided HTML.

Never bypass CSRF protection for convenience.

---

# 28. SEO

Implement the Phase 7 SEO requirements:

- semantic headings
- canonical URLs
- OpenGraph
- Twitter cards
- XML sitemap index
- paginated sitemaps
- appropriate noindex handling for filtered duplicate surfaces
- structured metadata

Pages should be useful and indexable without client-side JavaScript.

---

# 29. ACCESSIBILITY

Implement:

- keyboard navigation
- skip-to-content
- modal focus trapping
- Escape handling
- accessible labels
- semantic controls
- WCAG AA contrast
- reduced motion
- appropriate ARIA semantics

Accessibility is part of the implementation contract, not a later optional enhancement.

---

# 30. PROJECT STRUCTURE

Create a modular project structure.

Avoid:

- God files
- giant route files
- giant models files
- giant utility modules
- business logic embedded directly inside templates
- database queries directly scattered through templates/routes

Use clear boundaries between:

- application setup
- configuration
- models
- repositories/query services
- domain services
- ingestion
- external providers
- background tasks
- recommendations
- analytics
- caching
- authentication
- administration
- serialization/DTOs
- templates
- static assets
- tests

Choose the exact directory structure based on the existing project and Phase 7 requirements, but keep the architecture modular.

---

# 31. DEPENDENCY DISCIPLINE

Do not add dependencies merely because they are convenient.

Before adding a package:

1. determine whether the standard library or an existing dependency is sufficient;
2. determine whether the package conflicts with the Phase 7 philosophy;
3. determine whether it is actually required;
4. document why it is needed.

Do not add React, Tailwind, Elasticsearch, or another frontend/backend framework unless explicitly authorized in a later instruction.

---

# 32. CONFIGURATION

Implement the environment-variable contract from Phase 7.

At minimum support:

    DATABASE_URL
    SECRET_KEY
    DIFFBOT_TOKEN
    YOUTUBE_API_KEY
    NEWS_API_KEY
    HUGGINGFACE_API_KEY
    REDIS_URL
    MAIL_SERVER

Never hard-code secrets.

Provide safe development configuration examples without exposing real credentials.

---

# 33. TESTING REQUIREMENTS

Create meaningful automated tests.

At minimum cover:

### Database
- model constraints
- relationships
- migrations
- indexes where practical
- data preservation migrations

### Ingestion
- NewsAPI parsing
- YouTube parsing
- deduplication
- URL canonicalization
- title normalization
- Diffbot extraction handling
- quality gates

### Search
- full-text search
- ranking
- autocomplete
- invalid short queries

### Recommendations
- relevance scoring
- personalization
- seen-content exclusion

### Authentication
- registration
- verification
- login
- password reset
- OAuth boundary
- authorization

### Security
- CSRF
- rate limiting
- sanitization
- admin access control

### Caching
- cache keys
- TTL behavior
- invalidation

### Public pages
- routes
- SSR responses
- canonical metadata

---

# 34. MIGRATION VALIDATION PROCEDURE

Before considering the database migration complete:

1. Create/use a safe copy of the current database.
2. Record the current schema state.
3. Record relevant row counts.
4. Apply the Alembic migrations.
5. Check for migration errors.
6. Check resulting schema.
7. Check row counts.
8. Check important foreign-key relationships.
9. Check important unique constraints.
10. Check indexes.
11. Verify preserved data.
12. Run application tests against the migrated database.

Do not declare the migration successful merely because Alembic reaches the final revision.

Application-level verification is required.

---

# 35. PHASED IMPLEMENTATION ORDER

Build in logical phases rather than attempting to create the entire application in one uncontrolled operation.

Recommended order:

## Phase A — Discovery
- read Phase 7
- inspect Nexora
- inspect migrations
- inspect database
- produce architecture/difference analysis

## Phase B — Foundation
- Python environment
- Flask application factory
- configuration
- extensions
- SQLAlchemy
- Alembic
- base infrastructure
- logging
- error handling

## Phase C — Database
- Phase 7 models
- compatibility mapping
- Alembic migrations
- data migration
- migration tests

## Phase D — Core Domain
- Content
- Article
- Video
- Source
- Author
- taxonomy
- locations
- events
- interactions

## Phase E — Ingestion
- NewsAPI
- YouTube
- Diffbot
- normalization
- deduplication
- quality gates
- background tasks

## Phase F — Public Experience
- layouts
- components/macros
- home
- sections
- categories
- topics
- article
- video
- search
- library

## Phase G — Authentication & Community
- accounts
- verification
- OAuth
- reactions
- saves
- comments
- shares
- newsletter

## Phase H — Recommendation & Analytics
- user interests
- recommendation engine
- impressions/clicks
- momentum
- demand/supply
- decay
- feedback

## Phase I — Administration
- ingestion operations
- content management
- inspection
- deduplication
- taxonomy
- moderation

## Phase J — Performance & Hardening
- caching
- invalidation
- query optimization
- N+1 auditing
- security
- accessibility
- SEO
- external API resilience

## Phase K — Verification
- tests
- migration verification
- route verification
- schema verification
- performance verification
- final Phase 7 compliance audit

---

# 36. DO NOT PRETEND FEATURES ARE COMPLETE

Never claim that a feature is implemented merely because:

- a route exists
- a model exists
- a placeholder template exists
- a function has been stubbed
- a TODO comment exists

A feature is complete only when the required backend, database, frontend, security and integration behavior exists and has been verified where applicable.

If something cannot yet be completed, state exactly what remains.

---

# 37. DO NOT OVERWRITE WORK WITHOUT INSPECTION

Before modifying an existing file in the NEW `Nexura/` project:

- inspect it first
- understand its role
- preserve correct work
- modify only what is necessary

If the new project is initially empty, create the architecture cleanly.

Do not assume every file from `Nexora` should be copied.

---

# 38. NO LEGACY CONCEPT LEAKAGE

After implementation, search the NEW project for references to excluded concepts.

Check:

- Python imports
- model names
- routes
- templates
- JavaScript
- CSS
- configuration
- migrations
- admin pages
- services
- tests

The new project must not accidentally depend on the legacy commercial/forum architecture.

---

# 39. FINAL PHASE 7 COMPLIANCE AUDIT

Before declaring the rebuild complete, perform a systematic audit against every section of:

    PHASE_7_MASTER_TRUTH.md

Verify:

- domain model
- database schema
- relationships
- foreign keys
- indexes
- ingestion
- extraction
- quality gates
- deduplication
- search
- routes
- presentation
- authentication
- library
- recommendations
- analytics
- administration
- moderation
- syndication
- background tasks
- DTOs
- caching
- frontend architecture
- performance invariants
- security
- SEO
- accessibility
- reliability
- external APIs
- configuration
- exclusions
- technology stack

Produce a final compliance report containing:

    IMPLEMENTED
    PARTIALLY IMPLEMENTED
    NOT IMPLEMENTED
    DEVIATION / DECISION

Do not silently mark unresolved requirements as complete.

---

# 40. MOST IMPORTANT RULES

The following rules override convenience:

1. `PHASE_7_MASTER_TRUTH.md` is the target architecture.
2. `Nexora/` is READ-ONLY.
3. Build the new application inside `Nexura/`.
4. Do not destroy existing database data merely to simplify implementation.
5. Inspect the actual existing schema before designing migrations.
6. Preserve compatible existing data.
7. Use Alembic migrations for schema evolution.
8. Test migrations against a database copy before production application.
9. Never reintroduce explicitly excluded commercial/forum functionality.
10. Do not introduce React, Tailwind, SPA architecture, or Elasticsearch.
11. Avoid N+1 queries.
12. Preserve the Phase 7 database contract.
13. Keep ORM models behind DTO/serialization boundaries.
14. Keep long-running work outside normal HTTP request execution.
15. Never hard-code secrets.
16. Never claim unfinished functionality is complete.
17. Do not modify `Nexora/`.
18. When uncertain, inspect the actual code/database rather than guessing.
19. When the legacy implementation conflicts with Phase 7, implement the Phase 7 architecture while preserving compatible data.
20. Do not make irreversible/destructive changes without explicit justification and migration testing.

---

# 41. START NOW

Begin with DISCOVERY.

Do NOT immediately generate hundreds of files.

First:

1. Read `PHASE_7_MASTER_TRUTH.md` completely.
2. Inspect the current `Nexura/` directory.
3. Locate and inspect `Nexora/`.
4. Inspect the legacy project structure.
5. Inspect its SQLAlchemy models.
6. Inspect Alembic configuration and migration history.
7. Determine how the current database is configured.
8. Inspect the current schema/data where access is available.
9. Compare the current implementation against Phase 7.
10. Produce the rebuild analysis.
11. Identify migration risks.
12. Identify reusable implementation components.
13. Identify components that must be rebuilt.
14. Identify explicitly excluded legacy functionality.
15. Propose the target project structure.
16. Propose the migration strategy.

Only after this discovery and analysis should implementation begin.

Do not ask the user to manually describe things that can be discovered by inspecting the repository.

If something genuinely cannot be determined from the repository, database, or Phase 7 specification, clearly identify that specific unknown.

The final result must be a clean, modular Nexura Phase 7 implementation inside the NEW project directory while leaving `Nexora/` untouched.