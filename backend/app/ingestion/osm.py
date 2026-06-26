"""
OpenStreetMap ingestion via Overpass API.

Pulls the following layers for the target city bounding box:
  - roads          : highway=* (primary, secondary, tertiary, trunk, motorway)
  - transit_stops  : public_transport=stop_position
  - competitors    : amenity=cafe, amenity=coffee_shop, brand=Starbucks|Dunkin'|...
  - universities   : amenity=university, amenity=college
  - shopping       : shop=mall, landuse=retail
  - offices        : office=*, building=office

Data lineage:
  source_id  : 'osm'
  confidence : 'high' for roads/transit, 'medium' for POIs

Run as a script:
    python -m app.ingestion.osm
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.db.connection import get_conn
from app.ingestion import lineage
from app.ingestion.validator import validate_features, persist_validation_results

logger = logging.getLogger(__name__)

OSM_SOURCE_ID = "osm"

# ── Layer definitions ─────────────────────────────────────────────────────────

OSM_LAYERS: list[dict[str, Any]] = [
    {
        "name": "roads",
        "description": "Primary, secondary, tertiary roads and trunks",
        "layer_type": "linestring",
        "confidence": "high",
        "query_filter": (
            '["highway"~"motorway|trunk|primary|secondary|tertiary"]'
        ),
        "osm_type": "way",
    },
    {
        "name": "transit_stops",
        "description": "Bus stops and train stations",
        "layer_type": "point",
        "confidence": "high",
        "query_filter": '["public_transport"~"stop_position|station|platform"]',
        "osm_type": "node",
    },
    {
        "name": "competitors",
        "description": "Coffee shops and cafes (potential competitor locations)",
        "layer_type": "point",
        "confidence": "medium",
        "query_filter": '["amenity"~"cafe|coffee_shop"]',
        "osm_type": "node",
    },
    {
        "name": "universities",
        "description": "Universities and colleges",
        "layer_type": "point",
        "confidence": "high",
        "query_filter": '["amenity"~"university|college"]',
        "osm_type": "node",
    },
    {
        "name": "shopping_centres",
        "description": "Shopping malls and retail land use",
        "layer_type": "point",
        "confidence": "medium",
        "query_filter": '["shop"="mall"]["name"]',
        "osm_type": "node",
    },
    {
        "name": "offices",
        "description": "Office buildings and commercial zones",
        "layer_type": "point",
        "confidence": "medium",
        "query_filter": '["building"~"office|commercial"]',
        "osm_type": "way",
    },
]


# ── Overpass query builder ────────────────────────────────────────────────────

def build_overpass_query(bbox: tuple, osm_type: str, filter_str: str) -> str:
    """
    Build an Overpass QL query for a given bounding box and filter.

    bbox: (lon_min, lat_min, lon_max, lat_max)
    Overpass expects: (lat_min, lon_min, lat_max, lon_max)
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    overpass_bbox = f"{lat_min},{lon_min},{lat_max},{lon_max}"

    return f"""
[out:json][timeout:60];
{osm_type}{filter_str}({overpass_bbox});
out body geom;
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30))
def query_overpass(url: str, query: str) -> dict[str, Any]:
    """Execute an Overpass QL query and return parsed JSON."""
    logger.debug("Overpass query: %s", query[:200])
    headers = {"User-Agent": "RetailIQSiteSelectionPlatform/1.0 (contact: support@retailiq.com)"}
    response = requests.post(url, data={"data": query}, headers=headers, timeout=90)
    response.raise_for_status()
    return response.json()


# ── GeoJSON conversion ────────────────────────────────────────────────────────

def osm_element_to_feature(element: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convert an OSM element (node or way) to a GeoJSON-style feature dict.
    Returns None if the element cannot be converted.
    """
    tags = element.get("tags", {})
    osm_id = element.get("id")

    # Node → Point
    if element.get("type") == "node":
        lat = element.get("lat")
        lon = element.get("lon")
        if lat is None or lon is None:
            return None
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "osm_id": osm_id,
                "osm_type": "node",
                **tags,
            },
        }

    # Way with geometry → LineString or Polygon
    if element.get("type") == "way":
        geom_nodes = element.get("geometry", [])
        if not geom_nodes:
            return None
        coords = [[n["lon"], n["lat"]] for n in geom_nodes if "lon" in n and "lat" in n]
        if len(coords) < 2:
            return None

        # Closed way → Polygon, open → LineString
        if coords[0] == coords[-1] and len(coords) >= 4:
            geom = {"type": "Polygon", "coordinates": [coords]}
        else:
            geom = {"type": "LineString", "coordinates": coords}

        # Use centroid point for POI layers to simplify analysis
        # (offices/shopping centres stored as their representative point)
        if geom["type"] == "Polygon":
            from shapely.geometry import shape
            centroid = shape(geom).centroid
            geom = {"type": "Point", "coordinates": [centroid.x, centroid.y]}

        return {
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "osm_id": osm_id,
                "osm_type": "way",
                **tags,
            },
        }

    return None


# ── Per-layer pipeline ────────────────────────────────────────────────────────

def ingest_layer(
    layer_def: dict[str, Any],
    dataset_id: str,
    settings,
) -> dict[str, Any]:
    """Run the full fetch → validate → insert pipeline for one OSM layer."""
    layer_name = layer_def["name"]
    logger.info("Ingesting OSM layer: %s", layer_name)

    layer_id = lineage.register_layer(
        dataset_id=dataset_id,
        name=layer_name,
        layer_type=layer_def["layer_type"],
        confidence=layer_def["confidence"],
        vintage_year=None,  # OSM is continuously updated
        metadata={"osm_filter": layer_def["query_filter"]},
    )
    lineage.update_layer_status(layer_id, "validating")

    try:
        bbox = settings.bbox_tuple
        query = build_overpass_query(bbox, layer_def["osm_type"], layer_def["query_filter"])
        raw = query_overpass(settings.overpass_url, query)
        elements = raw.get("elements", [])
        logger.info("  Overpass returned %d elements for '%s'.", len(elements), layer_name)

        features = [
            f for elem in elements
            if (f := osm_element_to_feature(elem)) is not None
        ]

        # Validate
        result = validate_features(
            layer_id=layer_id,
            features=features,
            source_srs="EPSG:4326",
        )
        persist_validation_results(result)

        if result.has_errors:
            lineage.update_layer_status(
                layer_id, "invalid",
                error=f"{len(result.errors)} validation errors in OSM layer '{layer_name}'."
            )
            return {"layer": layer_name, "status": "failed", "errors": len(result.errors)}

        # Insert
        inserted = _insert_osm_features(features, layer_id, layer_def["confidence"])
        lineage.update_layer_feature_count(layer_id, inserted)
        lineage.update_layer_status(layer_id, "imported")

        return {
            "layer": layer_name,
            "status": "complete",
            "layer_id": layer_id,
            "elements_fetched": len(elements),
            "features_inserted": inserted,
            "warnings": len(result.warnings),
        }

    except Exception as exc:
        lineage.update_layer_status(layer_id, "failed", error=str(exc))
        logger.exception("OSM layer '%s' failed: %s", layer_name, exc)
        return {"layer": layer_name, "status": "failed", "error": str(exc)}


def _insert_osm_features(
    features: list[dict[str, Any]],
    layer_id: str,
    confidence: str,
) -> int:
    """Bulk-insert OSM features into layer_features."""
    if not features:
        return 0

    rows: list[tuple] = []
    for feat in features:
        rows.append((
            str(uuid.uuid4()),
            layer_id,
            json.dumps(feat["geometry"]),
            json.dumps(feat["properties"]),
            OSM_SOURCE_ID,
            confidence,
        ))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO layer_features
                    (id, layer_id, geom, attributes, source_id, confidence)
                VALUES (
                    %s, %s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                    %s, %s, %s::data_confidence
                )
                """,
                rows,
            )
    return len(rows)


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_osm_ingestion() -> dict[str, Any]:
    """
    Full ingestion pipeline for all OSM layers.
    Returns a summary dict with per-layer results.
    """
    settings = get_settings()
    logger.info("Starting OSM ingestion for %s, %s.", settings.city_name, settings.city_state)

    dataset_id = lineage.register_dataset(
        source_id=OSM_SOURCE_ID,
        name=f"OpenStreetMap – {settings.city_name}, {settings.city_state}",
        description=(
            f"OpenStreetMap extract for {settings.city_name} bounding box. "
            f"Includes roads, transit, competitors, universities, shopping, offices."
        ),
        layer_type="point",  # mixed; individual layers may differ
        confidence="medium",
        vintage_year=None,
        srs_original="EPSG:4326",
        metadata={"bbox": settings.city_bbox},
    )

    layer_results = []
    for layer_def in OSM_LAYERS:
        result = ingest_layer(layer_def, dataset_id, settings)
        layer_results.append(result)

    failed = [r for r in layer_results if r["status"] == "failed"]
    summary = {
        "status": "partial" if failed else "complete",
        "dataset_id": dataset_id,
        "layers": layer_results,
        "layers_complete": len(layer_results) - len(failed),
        "layers_failed": len(failed),
    }
    logger.info("OSM ingestion done: %s", summary)
    return summary


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    from app.db.connection import init_pool
    init_pool()
    result = run_osm_ingestion()
    print(json.dumps(result, indent=2))
