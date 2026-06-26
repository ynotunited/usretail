# Data Source Registry
## RetailIQ GIS – U.S. Retail Site Selection Platform

> All data sources used in analysis are registered here as first-class citizens.
> Each source entry defines: origin, data types, ingestion method, known gaps,
> update cadence, confidence level, and how conflicts with other sources are resolved.

---

## Source Registry

### 1. U.S. Census Bureau

| Field | Value |
|---|---|
| **Source ID** | `census-acs` |
| **Provider** | U.S. Census Bureau |
| **Dataset** | American Community Survey (ACS) 5-Year Estimates |
| **URL** | https://data.census.gov |
| **Ingestion Method** | Census API + bulk shapefile download |
| **Data Types** | Population by tract, age groups, median household income, housing units |
| **Spatial Units** | Census Tracts, ZIP Code Tabulation Areas (ZCTAs), Block Groups |
| **Projection** | EPSG:4269 (NAD83) → re-project to EPSG:4326 on ingest |
| **Update Cadence** | Annual release (5-year rolling window) |
| **Current Vintage** | ACS 2019–2023 |
| **Freshness Threshold** | Flag as outdated if vintage > 2 years from current date |
| **Known Gaps** | Low-population tracts suppressed for privacy; some rural areas incomplete |
| **Confidence Level** | High for metro areas; Medium for suburban; Low for rural |
| **Conflict Resolution** | Census is authoritative for demographic data; commercial sources supplement only |

---

### 2. OpenStreetMap (OSM)

| Field | Value |
|---|---|
| **Source ID** | `osm` |
| **Provider** | OpenStreetMap Contributors |
| **Download Tool** | Overpass API / GeoFabrik regional extracts |
| **Data Types** | Roads, transit stops, POIs (competitors, malls, offices, universities, hospitals) |
| **Spatial Units** | Points, Linestrings, Polygons |
| **Projection** | EPSG:4326 (native) |
| **Update Cadence** | Continuous (pull fresh extract per analysis project) |
| **Known Gaps** | Coverage quality varies by city; secondary roads and POIs may be incomplete or mislabeled |
| **Confidence Level** | High for major roads and transit; Medium–Low for POIs |
| **Conflict Resolution** | If OSM and commercial provider disagree on a POI location, flag for analyst review |

---

### 3. GTFS (General Transit Feed Specification)

| Field | Value |
|---|---|
| **Source ID** | `gtfs` |
| **Provider** | Local transit authority (city-specific) |
| **Ingestion Method** | GTFS zip download from transit authority developer portal |
| **Data Types** | Bus stops, train stations, transit routes, schedules |
| **Projection** | WGS84 (EPSG:4326) |
| **Update Cadence** | Per transit agency schedule update (typically quarterly) |
| **Known Gaps** | Real-time ridership not available; frequency data may lag service changes |
| **Confidence Level** | High for stop locations; Medium for route coverage completeness |
| **Conflict Resolution** | GTFS authoritative for transit. OSM transit data used as fallback if GTFS unavailable |

---

### 4. Commercial Location Providers

| Field | Value |
|---|---|
| **Source ID** | `commercial-poi` |
| **Providers** | SafeGraph, Placer.ai, Precisely (configured per project) |
| **Ingestion Method** | API or licensed flat file import |
| **Data Types** | Business points of interest, foot traffic estimates, competitor brand locations |
| **Projection** | EPSG:4326 |
| **Update Cadence** | Monthly (varies by provider) |
| **Known Gaps** | Coverage gaps in low-income or rural areas; brand attribution may lag closures/openings |
| **Confidence Level** | High for national chains; Medium for local independents |
| **Conflict Resolution** | Commercial data takes precedence over OSM for competitor locations if fresher; flag conflicts |
| **License Notes** | Do not expose raw commercial data in public-facing exports without license review |

---

### 5. User-Uploaded Shapefiles

| Field | Value |
|---|---|
| **Source ID** | `user-shapefile` |
| **Provider** | Platform users (analysts) |
| **Ingestion Method** | Upload via Data Imports UI (zip containing .shp, .dbf, .prj, .shx) |
| **Data Types** | Any spatial data: custom boundaries, competitor lists, internal site candidates |
| **Projection** | User-defined (.prj file); auto-detected and re-projected to EPSG:4326 on ingest |
| **Validation Required** | Yes — geometry validity, coordinate bounds, attribute schema |
| **Known Gaps** | No quality guarantee; analyst responsible for data accuracy |
| **Confidence Level** | As declared by uploading analyst (stored in metadata) |
| **Conflict Resolution** | User uploads do not automatically override registered sources; analyst must explicitly merge |

---

### 6. GeoJSON Imports

| Field | Value |
|---|---|
| **Source ID** | `geojson-import` |
| **Provider** | Platform users or external systems |
| **Ingestion Method** | Upload via Data Imports UI or API endpoint |
| **Data Types** | Points, polygons, line features |
| **Projection** | EPSG:4326 (GeoJSON standard) |
| **Validation Required** | Yes — valid JSON structure, geometry types, coordinate bounds |
| **Known Gaps** | No standardized attribute naming; analyst must map fields during import |
| **Confidence Level** | As declared by importing analyst |
| **Conflict Resolution** | Same as user-uploaded shapefiles |

---

### 7. External APIs

| Field | Value |
|---|---|
| **Source ID** | `external-api` |
| **Examples** | Google Places API, Yelp Fusion API, Walk Score API, EPA EJScreen |
| **Ingestion Method** | Server-side API calls with result caching |
| **Data Types** | Varies by API: POIs, walkability scores, environmental data |
| **Projection** | EPSG:4326 (typical for REST geo APIs) |
| **Rate Limits** | Enforced server-side; cached responses used to minimise API spend |
| **Known Gaps** | API availability not guaranteed; failures must degrade gracefully with cached fallback |
| **Confidence Level** | Varies by provider; document per integration |
| **Conflict Resolution** | External API data supplements registered sources; never silently overrides them |

---

## Conflict Resolution Policy

When two sources provide data for the same geographic entity:

1. **Flag the conflict** — surface it in the Data Imports UI and in the layer metadata.
2. **Apply the precedence order** below, unless an analyst override exists:

| Data Type | Primary Source | Fallback |
|---|---|---|
| Demographics (population, income) | Census ACS | Commercial provider |
| Competitor locations | Commercial POI | OSM |
| Transit stops | GTFS | OSM |
| Road network | OSM | User shapefile |
| Custom boundaries | User shapefile | OSM admin boundaries |

3. **Analyst override** — analyst may select a different source for a specific layer. Override is logged to audit trail with timestamp and reason.

---

## Data Freshness Rules

| Staleness | UI Treatment |
|---|---|
| < 1 year | No badge |
| 1–2 years | ⚠️ "Data is N months old" badge (amber) |
| > 2 years | 🔴 "Outdated data – verify before use" badge (red) |
| Unknown vintage | 🔘 "Vintage unknown" badge (grey) |

---

## Ingestion Validation Checklist

All sources — regardless of origin — must pass these checks on ingest:

- [ ] Valid geometry types for declared layer type
- [ ] No null or empty geometries
- [ ] Coordinates within expected bounding box (US: lat 18–72, lon -180 to -66)
- [ ] Spatial reference system detected or declared
- [ ] No self-intersecting polygons
- [ ] Attribute schema matches expected columns (warn on missing, error on required)
- [ ] No duplicate geometries (within tolerance)
- [ ] Row count > 0

Failures: hard errors halt import. Warnings surface in import UI for analyst review.

---

*Last updated: 2026-06-26 | Status: ACTIVE*
