# Analyst User Guide

Welcome to the RetailIQ Analyst platform. This tool allows you to merge disparate data sources and rapidly generate AI-assisted suitability scores for potential retail locations.

## 1. Importing Data
Navigate to the **Data Hub**.
- You can drag and drop zip archives containing shapefiles, standalone GeoJSON files, or CSV files (must contain `lat` and `lon` columns).
- The system will immediately scan your upload for spatial validity (e.g., coordinates out of bounds, self-intersecting polygons).
- If duplicates are detected, use the **Duplicates** tab to merge or discard overlapping geometries.
- **Lineage**: Lock a dataset version before running end-of-quarter analyses so the results remain historically reproducible.

## 2. Running an Analysis
Navigate to the **Map Explorer**.
- Open the settings panel to configure the factor weights (e.g., prioritize Population Density over Transit Access).
- Click **Run Suitability Engine**.
- The map will render candidate sites as graded hex bins or points.

## 3. Executive Reporting & Overrides
Navigate to **Reports**.
- You will see the top candidate sites.
- **Partial Data**: If a site has a warning icon, it means one of the data sources was missing for that location (e.g., no transit data). The system falls back on other weights, but flag this for manual review.
- **Overrides**: Analysts can override a site's status (e.g., mark it as "Rejected" or "Under Review") or override a specific factor score. All overrides are securely logged to the system audit trail.
