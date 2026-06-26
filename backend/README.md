# RetailIQ GIS – Backend Setup

## Prerequisites
- Docker Desktop (with Docker Compose)
- OR: PostgreSQL 16 + PostGIS 3.4 + Python 3.12 locally

---

## Quickstart (Docker — recommended)

```bash
# 1. Start PostGIS + API server
docker-compose up -d

# 2. Verify health
curl http://localhost:8000/health

# 3. Run Census ACS ingestion (Austin, TX)
docker-compose exec backend python -m app.ingestion.census

# 4. Run OSM ingestion (roads, transit, competitors, etc.)
docker-compose exec backend python -m app.ingestion.osm

# 5. Check datasets API
curl http://localhost:8000/datasets | python -m json.tool
```

---

## Local Python Setup (without Docker)

```bash
cd backend

# Install dependencies
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Configure
copy .env.example .env
# Edit .env — update DATABASE_URL to point at your local PostGIS instance

# Apply schema
psql $DATABASE_URL -f app/db/schema.sql

# Start API server
uvicorn app.main:app --reload --port 8000
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| GET | /datasets | List all datasets with freshness flags |
| GET | /datasets/{id} | Dataset detail with layer list |
| GET | /datasets/{id}/layers/{layer_id}/validation | Row-level validation results |
| POST | /datasets/import/geojson | Import GeoJSON FeatureCollection |

Interactive docs: http://localhost:8000/docs

---

## Census API Key

A free Census API key speeds up requests and avoids rate limits:
https://api.census.gov/data/key_signup.html

Set `CENSUS_API_KEY` in `backend/.env`. Leave blank to use the keyless endpoint.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | (see .env.example) | PostGIS connection string |
| CENSUS_API_KEY | (blank) | Optional Census API key |
| CITY_NAME | Austin | Target city name |
| CITY_STATE | TX | Target state abbreviation |
| CITY_STATE_FIPS | 48 | State FIPS code |
| CITY_COUNTY_FIPS | 453 | County FIPS code |
| CITY_BBOX | -97.9383,... | lon_min,lat_min,lon_max,lat_max |
| OVERPASS_URL | overpass-api.de | OSM Overpass endpoint |
| APP_ENV | development | development \| production |
| LOG_LEVEL | INFO | Python logging level |
