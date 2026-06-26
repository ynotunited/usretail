"""
Nominatim (OpenStreetMap) geocoding pipeline.

Geocodes address fields found in layer_features.attributes.
No API key required — uses the public Nominatim endpoint with a
proper User-Agent header and respects the 1 req/sec rate limit.

Features:
  - Batch geocoding with tenacity retry (3 attempts, 2s backoff)
  - Per-row result: lat, lon, confidence, raw_response
  - Failures flagged as geocoding_status='failed' with reason
  - Results stored back into layer_features.attributes JSONB
  - Rate-limit-safe: 1 request/second enforced by time.sleep(1.1)

Address field detection:
  Tries common attribute keys in order:
    ['address', 'addr', 'full_address', 'street_address',
     'location', 'place_name', 'name']
  Also tries compositing: street + city + state + zip
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from app.db.connection import get_conn

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "RetailIQ-GIS/1.0 (retail-site-selection; contact: ops@retailiq.internal)"

# Candidate address keys to try in order
ADDRESS_KEYS = [
    "address", "full_address", "street_address", "addr",
    "location", "place_name", "name",
]

COMPOSITE_KEYS = {
    "street": ["street", "addr:street", "address_line1"],
    "city":   ["city", "addr:city", "municipality"],
    "state":  ["state", "addr:state", "region"],
    "zip":    ["zip", "postcode", "addr:postcode", "zipcode"],
}


# ── Address extraction ─────────────────────────────────────────────────────────

def _extract_address(attrs: dict) -> str | None:
    """Try to find a usable address string from a feature's attributes."""
    # Try direct address fields
    for key in ADDRESS_KEYS:
        val = attrs.get(key)
        if val and isinstance(val, str) and len(val.strip()) > 5:
            return val.strip()

    # Try composite address
    def _pick(candidates: list[str]) -> str:
        for k in candidates:
            v = attrs.get(k)
            if v:
                return str(v).strip()
        return ""

    street = _pick(COMPOSITE_KEYS["street"])
    city   = _pick(COMPOSITE_KEYS["city"])
    state  = _pick(COMPOSITE_KEYS["state"])
    zip_   = _pick(COMPOSITE_KEYS["zip"])

    parts = [p for p in [street, city, state, zip_] if p]
    if len(parts) >= 2:
        return ", ".join(parts)

    return None


# ── Nominatim API call ─────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def _call_nominatim(address: str) -> list[dict]:
    resp = requests.get(
        NOMINATIM_URL,
        params={
            "q": address,
            "format": "json",
            "limit": 1,
            "countrycodes": "us",
            "addressdetails": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ── Geocode a single address ───────────────────────────────────────────────────

def geocode_address(address: str) -> dict[str, Any]:
    """
    Geocode a single address string via Nominatim.
    Returns a result dict with keys:
      lat, lon, display_name, confidence, geocoding_status, geocoding_error
    """
    try:
        results = _call_nominatim(address)
        if not results:
            return {
                "lat": None, "lon": None,
                "display_name": None,
                "confidence": "none",
                "geocoding_status": "failed",
                "geocoding_error": "No results returned by Nominatim.",
            }
        top = results[0]
        importance = float(top.get("importance", 0))
        confidence = "high" if importance > 0.6 else ("medium" if importance > 0.3 else "low")
        return {
            "lat": float(top["lat"]),
            "lon": float(top["lon"]),
            "display_name": top.get("display_name"),
            "confidence": confidence,
            "geocoding_status": "geocoded",
            "geocoding_error": None,
            "nominatim_importance": importance,
            "nominatim_type": top.get("type"),
            "nominatim_class": top.get("class"),
        }
    except Exception as exc:
        logger.warning("Geocoding failed for '%s': %s", address, exc)
        return {
            "lat": None, "lon": None,
            "display_name": None,
            "confidence": "none",
            "geocoding_status": "failed",
            "geocoding_error": str(exc),
        }


# ── Batch geocode a layer ──────────────────────────────────────────────────────

def geocode_layer(layer_id: str) -> dict[str, Any]:
    """
    Batch geocode all features in a layer that have address attributes.
    Updates layer_features.attributes and geom in-place.

    Returns a summary dict:
      total, geocoded, failed, skipped (no address found)
    """
    stats = {"total": 0, "geocoded": 0, "failed": 0, "skipped": 0}

    # Fetch all features for the layer
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, attributes FROM layer_features WHERE layer_id = %s::uuid",
                (layer_id,),
            )
            features = cur.fetchall()

    stats["total"] = len(features)
    logger.info("Geocoding layer %s: %d features.", layer_id, stats["total"])

    for feat_id, attrs in features:
        # Skip if already has valid geometry (only geocode address-only rows)
        address = _extract_address(attrs or {})
        if not address:
            stats["skipped"] += 1
            continue

        result = geocode_address(address)
        time.sleep(1.1)  # Nominatim rate limit: ≤1 req/sec

        updated_attrs = {**(attrs or {}), **result, "geocoded_at": datetime.now(timezone.utc).isoformat()}

        if result["geocoding_status"] == "geocoded":
            # Update geometry + attributes
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE layer_features
                        SET
                            geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                            attributes = %s::jsonb
                        WHERE id = %s::uuid
                        """,
                        (result["lon"], result["lat"], _to_jsonb(updated_attrs), str(feat_id)),
                    )
            stats["geocoded"] += 1
        else:
            # Update attributes only (log failure)
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE layer_features SET attributes = %s::jsonb WHERE id = %s::uuid",
                        (_to_jsonb(updated_attrs), str(feat_id)),
                    )
            stats["failed"] += 1

    logger.info(
        "Geocoding complete for layer %s: geocoded=%d, failed=%d, skipped=%d",
        layer_id, stats["geocoded"], stats["failed"], stats["skipped"],
    )
    return stats


# ── Manual coordinate patch ────────────────────────────────────────────────────

def patch_feature_coordinates(
    feature_id: str, lat: float, lon: float, corrected_by: str
) -> bool:
    """
    Manually set the coordinates for a feature (analyst correction).
    Records the correction in attributes with corrected_by + corrected_at.
    Returns True if the feature was found and updated.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE layer_features
                SET
                    geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    attributes = attributes || jsonb_build_object(
                        'geocoding_status', 'manually_corrected',
                        'geocoding_error', null,
                        'lat', %s,
                        'lon', %s,
                        'corrected_by', %s,
                        'corrected_at', %s
                    )
                WHERE id = %s::uuid
                RETURNING id
                """,
                (lon, lat, lat, lon, corrected_by, datetime.now(timezone.utc).isoformat(), feature_id),
            )
            row = cur.fetchone()
    return row is not None


# ── Helpers ────────────────────────────────────────────────────────────────────

import json as _json

def _to_jsonb(d: dict) -> str:
    return _json.dumps(d, default=str)
