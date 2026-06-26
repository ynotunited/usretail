# Architecture & Data Flow

## 1. High-Level Data Flow

The RetailIQ platform follows a classic ingestion, computation, and presentation pipeline.

1. **Ingestion**: Shapefiles, GeoJSON, and CSV data are uploaded. The `validation` module runs bounds checking, SRS reprojection (to EPSG:4326), and spatial duplicate fingerprinting.
2. **Snapshotting**: Validated datasets are stamped with an immutable `version_tag` via the `lineage` module, guaranteeing reproducible analysis.
3. **Analysis Engine**: A request triggers `calculate_composite` in the `engine`. The system cross-references candidate sites with intersecting polygons (e.g., Census Tracts) and calculates nearest-neighbor distances to competitors and transit via PostGIS `ST_Distance`.
4. **Scoring**: Factors are normalized to a 0-100 scale and multiplied by user-defined weights. Missing data is flagged with `has_partial_data`.
5. **Auditing**: Every run, analyst override, and manual data merge is stored in `audit_log` and `analyst_overrides` for compliance exporting.

## 2. Core Database Schema (PostGIS)

- `datasets`: Source metadata (e.g., ACS 2022).
- `dataset_versions`: Immutable snapshots for reproducible runs.
- `layer_features`: The master geometry table with GIST indexing for spatial queries.
- `analysis_runs`: Tracks `city_name`, `weights`, and snapshot references.
- `candidate_sites`: The scored outputs mapped back to a specific run.
- `audit_log` / `analyst_overrides`: Security and compliance tracking tables.

## 3. API Contract Guarantees

All endpoints under `/api/v1` adhere to standard HTTP verbs.
- `GET` endpoints support pagination (`limit`, `offset`).
- Heavy geospatial processing is deferred to Celery (accessible via `async_mode=True` payloads on POST endpoints).
- All timestamps returned in ISO 8601 UTC format.
