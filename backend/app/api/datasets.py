"""
Datasets API router.

Endpoints:
  GET  /datasets                 — list all datasets with metadata and freshness
  GET  /datasets/{dataset_id}    — single dataset detail with layer list
  GET  /datasets/{dataset_id}/layers/{layer_id}/validation
                                 — layer validation results
  POST /datasets/import/geojson  — import a raw GeoJSON FeatureCollection
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, status, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.connection import get_conn
from app.ingestion import lineage
from app.ingestion.validator import validate_features, persist_validation_results
from app.auth.dependencies import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/datasets", tags=["datasets"])


# ── Helper: convert db rows to dicts ─────────────────────────────────────────

def _row_to_dict(cur, rows) -> list[dict[str, Any]]:
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in rows]


# ── GET /datasets ─────────────────────────────────────────────────────────────

@router.get("", summary="List all datasets with freshness and quality flags")
def list_datasets() -> JSONResponse:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    d.id,
                    d.source_id,
                    d.name,
                    d.description,
                    d.layer_type,
                    d.feature_count,
                    d.vintage_year,
                    d.ingested_at,
                    d.confidence,
                    d.srs_original,
                    d.metadata,
                    d.is_active,
                    d.is_archived,
                    d.freshness_status,
                    d.age_years,
                    COUNT(l.id) AS layer_count
                FROM v_datasets_with_freshness d
                LEFT JOIN layers l ON l.dataset_id = d.id
                GROUP BY
                    d.id, d.source_id, d.name, d.description, d.layer_type,
                    d.feature_count, d.vintage_year, d.ingested_at, d.confidence,
                    d.srs_original, d.metadata, d.is_active, d.is_archived,
                    d.freshness_status, d.age_years
                ORDER BY d.ingested_at DESC
                """
            )
            rows = _row_to_dict(cur, cur.fetchall())

    # Serialize datetimes and UUIDs
    for row in rows:
        row["id"] = str(row["id"])
        row["ingested_at"] = row["ingested_at"].isoformat() if row["ingested_at"] else None

    return JSONResponse({"datasets": rows, "total": len(rows)})


# ── GET /datasets/{dataset_id} ────────────────────────────────────────────────

@router.get("/{dataset_id}", summary="Single dataset detail with layers")
def get_dataset(dataset_id: str) -> JSONResponse:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Dataset row
            cur.execute(
                "SELECT * FROM v_datasets_with_freshness WHERE id = %s::uuid",
                (dataset_id,)
            )
            rows = _row_to_dict(cur, cur.fetchall())
            if not rows:
                raise HTTPException(status_code=404, detail="Dataset not found.")
            dataset = rows[0]
            dataset["id"] = str(dataset["id"])
            dataset["ingested_at"] = dataset["ingested_at"].isoformat()

            # Layers
            cur.execute(
                """
                SELECT
                    l.id, l.name, l.layer_type, l.import_status,
                    l.import_error, l.confidence, l.vintage_year,
                    l.feature_count, l.ingested_at,
                    v.error_count, v.warning_count
                FROM v_layers_with_validation v
                JOIN layers l ON l.id = v.id
                WHERE l.dataset_id = %s::uuid
                ORDER BY l.ingested_at DESC
                """,
                (dataset_id,),
            )
            layers = _row_to_dict(cur, cur.fetchall())
            for layer in layers:
                layer["id"] = str(layer["id"])
                layer["ingested_at"] = layer["ingested_at"].isoformat()

    dataset["layers"] = layers
    return JSONResponse(dataset)


# ── GET /datasets/{dataset_id}/layers/{layer_id}/validation ──────────────────

@router.get(
    "/{dataset_id}/layers/{layer_id}/validation",
    summary="Row-level validation results for a layer",
)
def get_validation_results(dataset_id: str, layer_id: str) -> JSONResponse:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, row_index, severity, rule_name, message, raw_value, created_at
                FROM layer_validation_results
                WHERE layer_id = %s::uuid
                ORDER BY severity DESC, row_index NULLS LAST
                """,
                (layer_id,),
            )
            issues = _row_to_dict(cur, cur.fetchall())
            for issue in issues:
                issue["id"] = str(issue["id"])
                issue["created_at"] = issue["created_at"].isoformat()

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    infos = [i for i in issues if i["severity"] == "info"]

    return JSONResponse({
        "layer_id": layer_id,
        "total_issues": len(issues),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len(infos),
        "issues": issues,
    })


# ── POST /datasets/import/geojson ─────────────────────────────────────────────

@router.post(
    "/import/geojson",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Import a GeoJSON FeatureCollection with validation",
)
async def import_geojson(
    request: Request,
    source_id: str = "geojson-import",
    name: str = "Imported GeoJSON",
    description: str = "",
    layer_type: str = "point",
    confidence: str = "unknown",
    vintage_year: int | None = None,
    file: UploadFile = File(...),
) -> JSONResponse:
    """
    Accept a GeoJSON FeatureCollection upload.
    Validates geometry and attributes, then inserts into PostGIS.
    Returns validation summary and import status.
    """
    content = await file.read()
    try:
        geojson = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {exc}",
        )

    if geojson.get("type") != "FeatureCollection":
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a GeoJSON FeatureCollection.",
        )

    features = geojson.get("features", [])

    # Register dataset + layer
    dataset_id = lineage.register_dataset(
        source_id=source_id,
        name=name,
        description=description or f"Imported via API: {file.filename}",
        layer_type=layer_type,
        confidence=confidence,
        vintage_year=vintage_year,
        metadata={"original_filename": file.filename, "feature_count": len(features)},
    )
    layer_id = lineage.register_layer(
        dataset_id=dataset_id,
        name=f"{name} – Layer",
        layer_type=layer_type,
        confidence=confidence,
        vintage_year=vintage_year,
    )
    lineage.update_layer_status(layer_id, "validating")

    # Validate
    result = validate_features(layer_id=layer_id, features=features)
    persist_validation_results(result)

    if result.has_errors:
        lineage.update_layer_status(
            layer_id, "invalid",
            error=f"{len(result.errors)} validation errors."
        )
        return JSONResponse(
            status_code=422,
            content={
                "status": "invalid",
                "dataset_id": str(dataset_id),
                "layer_id": str(layer_id),
                "errors": len(result.errors),
                "warnings": len(result.warnings),
                "message": "Import rejected due to validation errors. Review issues via GET /datasets/{id}/layers/{layer_id}/validation",
            },
        )

    # Insert valid features
    inserted = _insert_geojson_features(features, layer_id, source_id, confidence, vintage_year)
    lineage.update_layer_feature_count(layer_id, inserted)
    lineage.update_layer_status(layer_id, "imported")

    return JSONResponse(
        status_code=202,
        content={
            "status": "imported",
            "dataset_id": str(dataset_id),
            "layer_id": str(layer_id),
            "features_submitted": len(features),
            "features_inserted": inserted,
            "warnings": len(result.warnings),
        },
    )


def _insert_geojson_features(
    features: list[dict],
    layer_id: str,
    source_id: str,
    confidence: str,
    vintage_year: int | None,
) -> int:
    rows = []
    for feat in features:
        rows.append((
            str(uuid.uuid4()),
            layer_id,
            json.dumps(feat.get("geometry")),
            json.dumps(feat.get("properties", {})),
            source_id,
            confidence,
            vintage_year,
        ))
    if not rows:
        return 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO layer_features
                    (id, layer_id, geom, attributes, source_id, confidence, vintage_year)
                VALUES (
                    %s, %s,
                    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),
                    %s, %s, %s::data_confidence, %s
                )
                """,
                rows,
            )
    return len(rows)


# ── POST /datasets/{id}/geocode ───────────────────────────────────────────────

class _GeocodeTrigger(BaseModel):
    layer_id: str
    async_mode: bool = False
    actor_id: str = "system"


@router.post(
    "/{dataset_id}/geocode",
    summary="Trigger geocoding for address-only features in a layer",
)
def trigger_geocoding(
    dataset_id: str,
    body: _GeocodeTrigger,
    _user: dict = Depends(require_role("analyst")),
) -> JSONResponse:
    """
    Geocodes features in the given layer that have address fields but no coordinates.
    When async_mode=true, submits to Celery and returns immediately.
    When async_mode=false (default), runs synchronously (suitable for small layers).
    """
    # Validate layer belongs to this dataset
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM layers WHERE id = %s::uuid AND dataset_id = %s::uuid",
                (body.layer_id, dataset_id),
            )
            if not cur.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail=f"Layer '{body.layer_id}' not found under dataset '{dataset_id}'."
                )

    if body.async_mode:
        try:
            from app.worker.tasks import geocode_dataset_task
            task = geocode_dataset_task.delay(layer_id=body.layer_id, actor_id=body.actor_id)
            return JSONResponse(
                {"status": "queued", "task_id": task.id, "layer_id": body.layer_id},
                status_code=202,
            )
        except Exception as exc:
            logger.warning("Celery unavailable, falling back to sync geocoding: %s", exc)

    # Synchronous geocoding (or Celery fallback)
    from app.geocoding.geocoder import geocode_layer
    stats = geocode_layer(layer_id=body.layer_id)
    return JSONResponse({"status": "complete", "layer_id": body.layer_id, **stats})


# ── GET /datasets/{id}/geocoding-failures ────────────────────────────────────

@router.get(
    "/{dataset_id}/geocoding-failures",
    summary="List features that failed geocoding and need manual correction",
)
def list_geocoding_failures(
    dataset_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    lf.id::text, l.id::text AS layer_id, l.name AS layer_name,
                    lf.attributes->>'geocoding_error' AS geocoding_error,
                    lf.attributes->>'address' AS address,
                    lf.attributes->>'geocoded_at' AS geocoded_at,
                    lf.created_at
                FROM layer_features lf
                JOIN layers l ON l.id = lf.layer_id
                WHERE l.dataset_id = %s::uuid
                  AND lf.attributes->>'geocoding_status' = 'failed'
                ORDER BY lf.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (dataset_id, limit, offset),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            for r in rows:
                r["created_at"] = r["created_at"].isoformat() if r["created_at"] else None

            cur.execute(
                """
                SELECT COUNT(*) FROM layer_features lf
                JOIN layers l ON l.id = lf.layer_id
                WHERE l.dataset_id = %s::uuid
                  AND lf.attributes->>'geocoding_status' = 'failed'
                """,
                (dataset_id,),
            )
            total = cur.fetchone()[0]

    return JSONResponse({
        "dataset_id": dataset_id,
        "failures": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


# ── PATCH /datasets/{id}/features/{feature_id}/coordinates ────────────────────

class _CoordinatePatch(BaseModel):
    lat: float
    lon: float
    corrected_by: str = "analyst"


@router.patch(
    "/{dataset_id}/features/{feature_id}/coordinates",
    summary="Manually correct coordinates for a geocoding-failed feature",
)
def patch_coordinates(
    dataset_id: str,
    feature_id: str,
    body: _CoordinatePatch,
    _user: dict = Depends(require_role("analyst")),
) -> JSONResponse:
    """
    Allows an analyst to manually set the coordinates for a feature
    that failed geocoding. The correction is recorded in attributes
    (corrected_by + corrected_at) and the geom column is updated.
    """
    from app.geocoding.geocoder import patch_feature_coordinates

    # Validate bounds (US-wide)
    if not (-180 <= body.lon <= -60 and 15 <= body.lat <= 72):
        raise HTTPException(
            status_code=400,
            detail=f"Coordinates ({body.lat}, {body.lon}) are outside the US boundary."
        )

    updated = patch_feature_coordinates(
        feature_id=feature_id,
        lat=body.lat,
        lon=body.lon,
        corrected_by=body.corrected_by,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Feature '{feature_id}' not found.")

    return JSONResponse({
        "status": "corrected",
        "feature_id": feature_id,
        "lat": body.lat,
        "lon": body.lon,
        "corrected_by": body.corrected_by,
    })
