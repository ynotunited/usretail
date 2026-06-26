# RetailIQ – Retail Site Selection Platform

RetailIQ is an enterprise-grade GIS application designed to evaluate and recommend optimal retail site locations. It ingests spatial data (demographics, competitor locations, road networks, public transit) and ranks candidate sites using a weighted spatial suitability algorithm.

## System Architecture
- **Backend**: FastAPI (Python), Celery (Background Workers), Redis (Task Queue), PostgreSQL + PostGIS (Spatial Database).
- **Frontend**: React (TypeScript), Vite, Mapbox GL JS (Spatial Visualization).

---

## Local Development Setup

### Prerequisites
- Docker and Docker Compose
- Node.js (v20+)
- Python 3.12 (optional, if running backend locally outside Docker)

### 1. Environment Configuration
Copy the sample environment files and configure them:
```bash
cp backend/.env.example backend/.env
# Optional: Set your Mapbox access token if you are running the frontend locally
```

### 2. Start the Backend Infrastructure
We use Docker Compose to orchestrate the database, redis, backend API, and celery workers.
```bash
docker-compose up -d
```
The backend API will be available at `http://localhost:8000`. You can view the interactive API documentation at `http://localhost:8000/docs`.

### 3. Start the Frontend
In a new terminal window, navigate to the frontend directory:
```bash
cd frontend
npm install
npm run dev
```
The frontend will be available at `http://localhost:5173`.

---

## Data Ingestion

RetailIQ relies on robust data layers. To seed your local database or import new datasets:

1. **Via UI**: Navigate to the **Data Hub** tab in the application. You can drag and drop GeoJSON, zipped Shapefiles, or CSVs with lat/lon coordinates. The system automatically validates topologies and checks for duplicate geometries.
2. **Via API**: You can submit background jobs to the Celery queue using the `/datasets/import` endpoint.

---

## Documentation Index
Detailed documentation can be found in the `docs/` directory:
- [Architecture Guide](docs/ARCHITECTURE.md): Database schemas, data flow, and API contracts.
- [Analyst User Guide](docs/USER_GUIDE.md): Workflows for importing data, running analyses, and making manual overrides.
- [Design System](docs/DESIGN_SYSTEM.md): UI tokens, component catalog, and CSS guidelines.
- [Data Source Catalog](docs/DATA_CATALOG.md): Confidence levels and gaps for supported datasets.
