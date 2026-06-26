# Data Source Catalog

RetailIQ combines multiple data sources to generate a composite score. Below are the supported sources, their update cadences, and known caveats.

| Data Source | Cadence | Confidence Level | Known Gaps / Caveats |
|-------------|---------|------------------|-----------------------|
| **Census ACS 5-Year** | Annual | High | Demographics lag by ~1.5 years. High margin of error in rural block groups. |
| **OpenStreetMap (OSM)** | Daily | Medium | Road network is highly accurate, but POI (Points of Interest) data for competitors is crowd-sourced and may be incomplete. |
| **Google Places API** | Real-time | High | Extremely accurate competitor mapping, but subject to strict API rate limits. Used primarily as a verification layer over OSM. |
| **GTFS (Transit Feeds)** | Monthly | High | Only covers major metropolitan transit agencies. Rural areas will show as missing transit data. |
| **SafeGraph (Foot Traffic)** | Monthly | Medium | Requires enterprise license. Aggregates mobile device pings. Can underrepresent demographics lacking smartphones. |

## Data Conflicts
When multiple sources provide the same attribute (e.g., competitor locations from both OSM and Google), the platform flags this as a **Source Conflict**. The Analyst must manually review and override the conflict in the Reports UI.
