"""
Validation & Dataset Versioning API.

Endpoints:
  GET  /validation/{layer_id}                      — paginated validation results
  POST /validation/{layer_id}/duplicates/resolve   — merge or discard duplicate features
  GET  /datasets/{dataset_id}/lineage              — full dataset lineage trace
  GET  /datasets/{dataset_id}/versions             — list version snapshots
  POST /datasets/{dataset_id}/versions             — create a new locked snapshot
  GET  /datasets/{dataset_id}/versions/{version_id}— single version detail
  GET  /sites/{site_id}/score-lineage              — per-factor score provenance
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.db.connection import get_conn
from app.ingestion import lineage as lineage_mod

logger = logging.getLogger(__name__)

router = APIRouter(tags=["validation"])


# ─── Pydantic models ──────────────────────────────────────────────────────────

class DuplicateResolveRequest(BaseModel):
    action: Literal["discard", "merge"] = Field(
        ..., description="'discard' removes the duplicate rows; 'merge' merges attributes."
    )
    feature_ids: list[str] = Field(
        ..., min_length=1, description="layer_features.id UUIDs of the duplicate rows to resolve."
    )
    analyst_id: str = Field(default="system", description="Actor performing the resolution.")
    reason: str = Field(default="", description="Justification for the resolution action.")


class CreateVersionRequest(BaseModel):
    version_tag: str = Field(..., min_length=1, max_length=64, description="Human-readable version label, e.g. 'v1' or '2024-Q4'.")
    created_by: str = Field(default="system")
    notes: str | None = None


# ─── Validation results ────────────────────────────────────────────────────────

@router.get(
    "/validation/{layer_id}",
    summary="Get validation results for a layer",
)
def get_validation_results(
    layer_id: str,
    severity: str | None = Query(None, description="Filter by 'error', 'warning', or 'info'."),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> JSONResponse:
    """
    Return paginated validation issues for a layer, optionally filtered by severity.
    Also returns a summary: total errors, warnings, and infos.
    """
    try:
        uuid.UUID(layer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid layer_id UUID.")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Summary counts
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE severity = 'error')   AS errors,
                    COUNT(*) FILTER (WHERE severity = 'warning') AS warnings,
                    COUNT(*) FILTER (WHERE severity = 'info')    AS infos
                FROM layer_validation_results
                WHERE layer_id = %s
                """,
                (layer_id,),
            )
            counts = cur.fetchone()
            summary = {"errors": counts[0], "warnings": counts[1], "infos": counts[2]}

            # Paginated rows
            sev_filter = "AND severity = %s::validation_severity" if severity else ""
            params: list = [layer_id]
            if severity:
                params.append(severity)
            params += [limit, offset]
            cur.execute(
                f"""
                SELECT id, row_index, severity, rule_name, message, raw_value, created_at
                FROM layer_validation_results
                WHERE layer_id = %s {sev_filter}
                ORDER BY severity DESC, row_index ASC NULLS LAST
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = cur.fetchall()

    issues = [
        {
            "id": str(r[0]),
            "row_index": r[1],
            "severity": r[2],
            "rule_name": r[3],
            "message": r[4],
            "raw_value": r[5],
            "created_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]
    return JSONResponse({"summary": summary, "issues": issues, "offset": offset, "limit": limit})


# ─── Duplicate resolution ──────────────────────────────────────────────────────

@router.post(
    "/validation/{layer_id}/duplicates/resolve",
    summary="Resolve duplicate features in a layer",
)
def resolve_duplicates(layer_id: str, body: DuplicateResolveRequest) -> JSONResponse:
    """
    Merge or discard a set of duplicate feature rows identified by their IDs.
    - discard: soft-deletes the duplicate rows (sets a `is_duplicate` flag in attributes).
    - merge: copies attributes from all duplicates into the first row, then discards the rest.
    All actions are written to the audit log.
    """
    try:
        uuid.UUID(layer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid layer_id UUID.")

    if not body.feature_ids:
        raise HTTPException(status_code=400, detail="feature_ids must not be empty.")

    resolved_ids: list[str] = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            if body.action == "discard":
                # Soft-delete: mark features as duplicates in attributes JSONB
                for fid in body.feature_ids:
                    cur.execute(
                        """
                        UPDATE layer_features
                        SET attributes = attributes || '{"_is_duplicate": true}'::jsonb
                        WHERE id = %s AND layer_id = %s
                        RETURNING id
                        """,
                        (fid, layer_id),
                    )
                    row = cur.fetchone()
                    if row:
                        resolved_ids.append(str(row[0]))

            elif body.action == "merge":
                # Merge: keep first feature, merge attributes from others, discard rest
                if len(body.feature_ids) < 2:
                    raise HTTPException(
                        status_code=400,
                        detail="merge requires at least 2 feature_ids."
                    )
                keep_id = body.feature_ids[0]
                discard_ids = body.feature_ids[1:]

                # Collect attributes from all to-be-discarded features
                placeholders = ",".join(["%s"] * len(discard_ids))
                cur.execute(
                    f"SELECT attributes FROM layer_features WHERE id IN ({placeholders})",
                    discard_ids,
                )
                merged_attrs: dict = {}
                for (attrs,) in cur.fetchall():
                    if isinstance(attrs, dict):
                        merged_attrs.update(attrs)

                # Update keeper with merged attrs + metadata
                merged_attrs["_merged_from"] = discard_ids
                cur.execute(
                    """
                    UPDATE layer_features
                    SET attributes = attributes || %s::jsonb
                    WHERE id = %s AND layer_id = %s
                    """,
                    (json.dumps(merged_attrs), keep_id, layer_id),
                )
                # Discard the rest
                cur.execute(
                    f"""
                    UPDATE layer_features
                    SET attributes = attributes || '{{"_is_duplicate": true}}'::jsonb
                    WHERE id IN ({placeholders}) AND layer_id = %s
                    """,
                    [*discard_ids, layer_id],
                )
                resolved_ids = body.feature_ids

            # Write audit entry
            event_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO audit_log (event_type, entity_type, entity_id, actor_id, payload)
                VALUES (%s, 'layer', %s::uuid, %s, %s)
                """,
                (
                    f"validation.duplicates.{body.action}",
                    layer_id,
                    body.analyst_id,
                    json.dumps({
                        "action": body.action,
                        "feature_ids": body.feature_ids,
                        "reason": body.reason,
                    }),
                ),
            )

    return JSONResponse(
        {
            "action": body.action,
            "resolved_count": len(resolved_ids),
            "resolved_ids": resolved_ids,
        },
        status_code=200,
    )


# ─── Dataset lineage ─────────────────────────────────────────────────────────

@router.get(
    "/datasets/{dataset_id}/lineage",
    summary="Full data lineage for a dataset",
)
def dataset_lineage(dataset_id: str) -> JSONResponse:
    """
    Returns dataset metadata, all layers with their provenance and validation
    summary, and all version snapshots. Provides full traceability for audits.
    """
    try:
        uuid.UUID(dataset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset_id UUID.")

    result = lineage_mod.get_dataset_lineage(dataset_id)
    if not result:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return JSONResponse(result)


# ─── Dataset versioning ───────────────────────────────────────────────────────

@router.get(
    "/datasets/{dataset_id}/versions",
    summary="List all version snapshots for a dataset",
)
def list_versions(dataset_id: str) -> JSONResponse:
    try:
        uuid.UUID(dataset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset_id UUID.")
    versions = lineage_mod.list_dataset_versions(dataset_id)
    return JSONResponse({"dataset_id": dataset_id, "versions": versions})


@router.post(
    "/datasets/{dataset_id}/versions",
    summary="Create a locked version snapshot of a dataset",
)
def create_version(dataset_id: str, body: CreateVersionRequest) -> JSONResponse:
    """
    Snapshots the current state of all active layers and locks them as a named
    version. Future analysis runs can reference this version_id to guarantee
    reproducibility even if the underlying layers are later updated.
    """
    try:
        uuid.UUID(dataset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset_id UUID.")
    try:
        version_id = lineage_mod.create_dataset_version(
            dataset_id=dataset_id,
            version_tag=body.version_tag,
            created_by=body.created_by,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Version creation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Version creation failed: {exc}")

    return JSONResponse(
        {"version_id": version_id, "dataset_id": dataset_id, "version_tag": body.version_tag},
        status_code=201,
    )


@router.get(
    "/datasets/{dataset_id}/versions/{version_id}",
    summary="Get a specific version snapshot",
)
def get_version(dataset_id: str, version_id: str) -> JSONResponse:
    try:
        uuid.UUID(dataset_id)
        uuid.UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID.")
    version = lineage_mod.get_version(version_id)
    if not version or version["dataset_id"] != dataset_id:
        raise HTTPException(status_code=404, detail="Version not found.")
    return JSONResponse(version)


# ─── Score lineage ────────────────────────────────────────────────────────────

@router.get(
    "/sites/{site_id}/score-lineage",
    summary="Trace factor scores for a candidate site back to source layers",
)
def score_lineage(site_id: str) -> JSONResponse:
    """
    For every factor score (population density, income, transit, road, competitor gap),
    returns the source layer_id, ingested_at timestamp, confidence level, and whether
    partial/estimated data was used. Supports full auditability of scoring decisions.
    """
    try:
        uuid.UUID(site_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid site_id UUID.")
    result = lineage_mod.get_score_lineage(site_id)
    if not result:
        raise HTTPException(status_code=404, detail="Site not found.")
    return JSONResponse(result)
