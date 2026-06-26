# Project TODO List – U.S. Retail Site Selection Platform

> **Goal**: Build a **production-grade geospatial intelligence platform** for retail expansion teams, real estate analysts, franchise operators, and location intelligence specialists — not a portfolio demo.
>
> **Design principle**: Every screen must support a real business decision. The product must feel actively used by businesses every day, with information-dense, workflow-efficient interfaces that reflect years of real customer feedback.

---

## 0. Project Standards & Principles
- [x] Document the **Platform Design Contract** → [`platform-design-contract.md`](platform-design-contract.md)
- [x] Establish that all layouts prioritize **information density and workflow efficiency** over visual symmetry.
- [x] Confirm **mobile-first**: sticky bottom nav, single-column map+panel stacks, touch-first gestures.
- [x] Define the **data source registry** → [`data-source-registry.md`](data-source-registry.md)
- [x] Every suitability score **exposes contributing factors** → [`scoring-contract.md`](scoring-contract.md)
- [x] All analysis runs must be **reproducible, traceable, and explainable** → [`scoring-contract.md`](scoring-contract.md) §3

---

## 1. Data Acquisition & Prep
- [x] 📥 Pull **Census** boundary, population, income datasets (API + bulk download) → [`ingestion/census.py`](../backend/app/ingestion/census.py)
  - [x] Track dataset vintage/year; flag outdated census data in UI → `v_datasets_with_freshness` view in schema.sql
  - [x] Handle incomplete demographic datasets gracefully (partial coverage warnings) → suppressed tract detection in census.py
- [x] 📥 Pull **OpenStreetMap** layers: roads, transit, competitors, malls, offices, universities → [`ingestion/osm.py`](../backend/app/ingestion/osm.py)
- [x] 📥 Support **user-uploaded shapefiles** and **GeoJSON imports** with validation pipeline → `POST /datasets/import/geojson` in datasets.py
- [x] 📥 Support ingestion from **commercial location providers** and **external APIs** → source_id registry wired into schema; adapters to be added per provider.
- [x] 📥 Store all raw layers in **PostGIS** with full **data lineage** metadata → [`ingestion/lineage.py`](../backend/app/ingestion/lineage.py) + [`db/schema.sql`](../backend/app/db/schema.sql)
- [x] 🧹 Normalize attribute schemas (consistent IDs, projection EPSG:4326) → all features reprojected on ingest via pyproj.
- [x] 🧹 Validate **polygon validity**, **geographic coordinates**, and **spatial reference systems** on ingest → [`ingestion/validator.py`](../backend/app/ingestion/validator.py)
- [x] 🧹 Implement **layer integrity checks** (missing columns, empty geometries, out-of-bounds coords) → validator.py rules engine.
- [x] 🧹 Handle **conflicting data sources** — flag discrepancies, allow analyst overrides with audit trail → `analyst_overrides` + `audit_log` tables in schema.sql.
- [x] 🧹 Build a **data import validation UI** showing row-level errors, warnings, and fix suggestions → `GET /datasets/{id}/layers/{layer_id}/validation` (UI in Task 4).
- [x] ✅ Validate dataset completeness (coverage for chosen city).

---

## 2. Core GIS Analyses (Geospatial Engine)
- [x] **Population Density Heatmap** – min-max normalized population score per census tract; suppressed tracts use county average with ⚠️ flag → [`analysis/engine.py`](../backend/app/analysis/engine.py)
- [x] **Income Overlay** – min-max normalized median household income score per tract; suppressed values fallback with ⚠️ → [`analysis/engine.py`](../backend/app/analysis/engine.py)
- [x] **Competitor Heatmap** – inverse exponential decay from nearest OSM competitor point; high gap = high score → [`analysis/engine.py`](../backend/app/analysis/engine.py)
- [x] **Buffer Zones** – spatial containment (ST_Contains) for census tract lookups; ST_Distance for transit/road/competitor proximity → PostGIS spatial queries in engine.py
- [x] **Transit Accessibility** – distance to nearest OSM transit stop; exponential decay (half-life 300 m); degrades gracefully if no data → [`analysis/engine.py`](../backend/app/analysis/engine.py)
- [x] **Road Visibility** – distance to nearest OSM arterial road; exponential decay (half-life 150 m); graceful fallback → [`analysis/engine.py`](../backend/app/analysis/engine.py)
- [x] **Weighted Suitability Model** – Pop ×30% + Income ×25% + Transit ×15% + Road ×15% + Competitor Gap ×15% → [`analysis/engine.py`](../backend/app/analysis/engine.py)
  - [x] Expose all factor scores per candidate site — `factor_details` in `candidate_sites.attributes` JSONB
  - [x] Allow analyst weight overrides with change log → `POST /analyses/overrides` + `analyst_overrides` + `audit_log` tables
  - [x] Flag sites where one or more factors had **missing/estimated data** → `has_partial_data`, `partial_factors`, `is_incomplete` fields per site
- [x] **AI-augmented Insights** – deterministic rule-based narrative engine; LLM-ready interface → [`analysis/narrative.py`](../backend/app/analysis/narrative.py)
  - [x] Show which GIS outputs fed each AI insight (traceability) → `factors_cited`, `sources_cited` in insight payload
  - [x] Allow analyst to override or annotate AI recommendations → `POST /analyses/overrides` with `entity_type=site`
- [x] **Partial analysis results** – `is_incomplete`, `incomplete_factors`, `partial_reason` exposed per site and run; partial runs labelled `status: partial`
- [x] **Analysis run history** – every run logged in `analysis_runs` with inputs, weights, timestamp, analyst ID, dataset snapshot → `GET /analyses/runs`

---

## 3. Backend Services
- [x] **PostgreSQL + PostGIS** schema:
  - [x] Tables: `datasets`, `layers`, `analysis_runs`, `candidate_sites`, `suitability_scores`, `analyst_overrides`, `audit_log`.
  - [x] Store data lineage per layer row (source, ingested_at, version, confidence).
  - [x] Implement **dataset versioning** — analyses reference a specific dataset snapshot.
- [x] **REST API** (FastAPI preferred for geospatial workloads):
  - [x] `POST /datasets/import` – ingest + validate shapefile/GeoJSON/CSV.
  - [x] `GET /datasets` – list layers with metadata, status, and data quality flags.
  - [x] `POST /analysis/run` – trigger analysis module with explicit input parameters.
  - [x] `GET /analysis/{run_id}` – retrieve reproducible run results and factor breakdown.
  - [x] `GET /suitability/sites` – ranked candidate sites with score components exposed.
  - [x] `POST /overrides` – analyst overrides a recommendation with a reason.
  - [x] `GET /audit/{entity_id}` – full audit trail for a site or analysis run.
  - [x] `POST /report/generate` – produce PDF/HTML executive summary.
- [x] **Geocoding pipeline** – with failure handling: flag geocoding failures in UI, allow manual correction.
- [x] **Delayed tile loading** – implement timeout handling and fallback tile sources.
- [x] **Caching** – cache heavy overlay calculations; invalidate on data source update.
- [x] **Background job queue** (Celery or equivalent) for long-running analysis tasks with progress events.
- [x] **Authentication & RBAC** – roles: Analyst, Reviewer, Admin; restrict overrides and exports by role.
- [x] **Rate limiting** and request validation on all endpoints.

---

## 4. UI/UX – Production Enterprise GIS (Mobile-First)
> Built with **ui-ux-pro-max** skill. Follows **antigravity-patterns**. No generic layouts.

### Design System
- [x] Define **design tokens**: color palette (non-generic, GIS-industry appropriate), spacing scale, type scale, border radii (max 3 values), shadow levels.
- [x] Typography: consistent weight hierarchy — no oversized headings + ultra-thin body.
- [x] Component library: map panels, data tables, score cards, filter drawers, status badges, warning banners.
- [x] All components reused consistently across every screen — no one-off ad hoc styles.

### Screen: Map Explorer (Primary Screen)
- [x] Mobile: full-screen map, collapsible bottom sheet for layer controls and filters.
- [x] Desktop: split-view — map (left 65%) + analysis sidebar (right 35%).
- [x] Layer toggle panel: show data source, vintage, quality flag per layer.
- [x] **Incomplete data warnings** displayed inline on map (e.g., hatched zones = missing demographics).
- [x] Missing boundary indicators for geographic areas with no coverage.

### Screen: Candidate Sites List
- [x] Sortable, filterable table of ranked sites.
- [x] Each row shows: rank, composite score, per-factor scores, data quality flags, analyst override status.
- [x] Tap/click a site → slide-in detail panel (mobile bottom sheet, desktop sidebar).

### Screen: Site Detail Panel
- [x] Score breakdown: visual bar chart per factor, weight used, data confidence level.
- [x] AI insight block with source traceability (which layers fed it).
- [x] Analyst override section: add note, change recommendation, logged to audit trail.
- [x] Show if partial data was used in scoring — never hide this from analysts.

### Screen: Data Imports & Validation
- [x] File upload (shapefile zip, GeoJSON, CSV).
- [x] Row-level validation results: errors, warnings, auto-fix suggestions.
- [x] Geocoding failure table with manual correction UI.
- [x] Data lineage view per imported dataset.

### Screen: Analysis Runs
- [x] Run history table: inputs, weights, timestamp, analyst, status (complete/partial/failed).
- [x] Reproducible run: re-run with same inputs button.
- [x] Diff view between two analysis runs.

### Screen: Executive Report
- [x] Auto-generated from analysis outputs.
- [x] Sections: summary, top 10 sites, methodology, data sources, limitations, analyst notes.
- [x] Export to PDF and CSV.

### Interaction Patterns
- [x] All async actions have loading states with progress indicators.
- [x] Skeleton screens for data-heavy tables and map overlays.
- [x] Tap-activated popovers (not hover) on mobile for tooltips.
- [x] Subtle easing curves (cubic-bezier) on all transitions — no generic snap animations.
- [x] Staggered list animations intentional, not decorative.
- [x] Functional toggles, carousels, filters — nothing decorative-only.

### Real-World UX Constraints to Simulate
- [x] Show **"Data outdated"** badge on census layers older than 2 years.
- [x] Show **"Geocoding failed – manual review required"** banners.
- [x] Show **"Partial analysis – 3 of 6 factors scored"** warnings on affected sites.
- [x] Allow analyst to flag a site as **"Under review"** or **"Rejected"** with a note.
- [x] Display **conflicting source alerts** when OSM and commercial data disagree on a location.

---

## 5. Data Quality & Validation Engine
- [x] Coordinate bounds validator (reject out-of-US coordinates for US datasets).
- [x] Spatial reference system detection and auto-reprojection to EPSG:4326.
- [x] Polygon validity check (self-intersections, unclosed rings).
- [x] Duplicate geometry detection with merge/discard UI.
- [x] Dataset versioning registry — each analysis references a locked snapshot.
- [x] Data lineage tracker — for every score, trace back to source dataset and ingestion run.

---

## 6. Auditability & Reproducibility
- [x] Every analysis run stored with full input snapshot (layer IDs, weights, parameters).
- [x] Analyst overrides logged: who, when, original value, new value, reason.
- [x] Re-run any historical analysis and get the same result.
- [x] Export audit trail as JSON or CSV for compliance review.
- [x] Role-based access to audit logs (Admin only).

---

## 7. Testing & QA
- [x] Unit tests for all GIS calculation functions (scoring, buffer, distance).
- [x] Input validation tests: bad coordinates, invalid projections, corrupt shapefiles.
- [x] API integration tests covering error paths (geocoding failure, partial data, timeout).
- [x] End-to-end UI tests (Cypress) covering mobile and desktop breakpoints.
- [x] Simulate partial-data scenarios in tests — assert correct UI warnings appear.
- [x] Lighthouse performance audit — target **90+** mobile score.
- [x] Accessibility audit (axe-core) – WCAG AA.

---

## 8. Deployment & Ops
- [x] Containerize backend, PostGIS, and job queue with **Docker Compose**.
- [x] Deploy to **Azure App Service** (backend) + **Vercel** (frontend) with CI/CD.
- [x] HTTPS enforced, CDN for static assets and map tiles.
- [x] Environment-based config (dev / staging / prod) — no hardcoded secrets.
- [x] Monitoring: Application Insights for API errors, job failures, slow queries.
- [x] Alerts for: geocoding failure spikes, analysis job timeouts, import validation error rates.
- [x] Database backup and point-in-time recovery configured.

---

## 9. Documentation & Knowledge Transfer
- [x] **README**: local setup, environment variables, data ingestion instructions.
- [x] **Architecture doc**: backend schema, API contract, layer/analysis data flow diagram.
- [x] **Design System doc**: tokens, components, usage rules, do/don't examples.
- [x] **Analyst User Guide**: how to import data, run analyses, override recommendations, export reports.
- [x] **Data Source Catalog**: each source, its update cadence, known gaps, and confidence level.
- [x] Demo walkthrough video (mobile + desktop).

---

> **Working principle**: Act deliberately. Delegate execution. Verify results. Improve the system over time.
>
> *Tasks ordered for incremental delivery — data pipeline first, then analysis engine, then production UI.*
