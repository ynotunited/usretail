"""
Data lineage tracking helpers.

Every dataset and layer row carries provenance metadata:
- source_id   : matches an entry in data-source-registry.md
- ingested_at : UTC timestamp of this specific ingest run
- vintage_year: publication year of the underlying data
- confidence  : High / Medium / Low / Unknown per source registry
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.connection import get_conn

logger = logging.getLogger(__name__)


def register_dataset(
    *,
    source_id: str,
    name: str,
    description: str,
    layer_type: str,
    confidence: str,
    vintage_year: int | None,
    srs_original: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Insert a new dataset record and return its UUID.
    Called once per ingest run before inserting individual layers.
    """
    dataset_id = str(uuid.uuid4())
    meta = metadata or {}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO datasets (
                    id, source_id, name, description, layer_type,
                    vintage_year, ingested_at, confidence,
                    srs_original, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s::layer_type,
                    %s, %s, %s::data_confidence,
                    %s, %s
                )
                """,
                (
                    dataset_id,
                    source_id,
                    name,
                    description,
                    layer_type,
                    vintage_year,
                    datetime.now(timezone.utc),
                    confidence,
                    srs_original, json.dumps(meta)
                ),
            )
            _write_audit(cur, "dataset.registered", "dataset", dataset_id, {"source_id": source_id})

    logger.info("Dataset registered: %s (%s)", name, dataset_id)
    return dataset_id


def register_layer(
    *,
    dataset_id: str,
    name: str,
    layer_type: str,
    confidence: str,
    vintage_year: int | None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Insert a new layer record and return its UUID."""
    layer_id = str(uuid.uuid4())
    meta = metadata or {}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO layers (
                    id, dataset_id, name, layer_type, import_status,
                    confidence, vintage_year, ingested_at, metadata
                ) VALUES (
                    %s, %s, %s, %s::layer_type, 'pending',
                    %s::data_confidence, %s, %s, %s
                )
                """,
                (
                    layer_id,
                    dataset_id,
                    name,
                    layer_type,
                    confidence,
                     vintage_year,
                     datetime.now(timezone.utc),
                     json.dumps(meta),
                ),
            )
    logger.debug("Layer registered: %s (%s) under dataset %s", name, layer_id, dataset_id)
    return layer_id


def update_layer_status(layer_id: str, status: str, error: str | None = None) -> None:
    """Update the import_status (and optional error) of a layer."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE layers SET import_status = %s::import_status, import_error = %s WHERE id = %s",
                (status, error, layer_id),
            )


def update_layer_feature_count(layer_id: str, count: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE layers SET feature_count = %s WHERE id = %s",
                (count, layer_id),
            )


def _write_audit(
    cur: Any,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
    actor_id: str = "system",
) -> None:
    """Internal helper — write to audit_log within an open cursor/transaction."""
    cur.execute(
        """
        INSERT INTO audit_log (event_type, entity_type, entity_id, actor_id, payload)
        VALUES (%s, %s, %s::uuid, %s, %s)
        """,
        (event_type, entity_type, entity_id, actor_id, json.dumps(payload)),
    )


# =============================================================================
# DATASET VERSIONING
# =============================================================================

def create_dataset_version(
    dataset_id: str,
    version_tag: str,
    created_by: str = "system",
    notes: str | None = None,
) -> str:
    """
    Snapshot the current state of all active layers for a dataset and lock it
    as a named version. Returns the new version UUID.

    The snapshot captures: layer_id → {ingested_at, feature_count, confidence}
    so that any future analysis run can reference an exact historical state.
    """
    version_id = str(uuid.uuid4())

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Collect current layer state
            cur.execute(
                """
                SELECT id, feature_count, confidence, ingested_at
                FROM layers
                WHERE dataset_id = %s
                ORDER BY ingested_at ASC
                """,
                (dataset_id,),
            )
            rows = cur.fetchall()
            if not rows:
                raise ValueError(f"Dataset {dataset_id} has no layers to snapshot.")

            snapshot: dict[str, Any] = {}
            for row in rows:
                layer_id, feature_count, confidence, ingested_at = row
                snapshot[str(layer_id)] = {
                    "ingested_at": ingested_at.isoformat() if ingested_at else None,
                    "feature_count": feature_count,
                    "confidence": confidence,
                }

            cur.execute(
                """
                INSERT INTO dataset_versions
                    (id, dataset_id, version_tag, layer_snapshot, created_by, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (version_id, dataset_id, version_tag,
                 json.dumps(snapshot), created_by, notes),
            )
            _write_audit(
                cur, "dataset.version_created", "dataset", dataset_id,
                {"version_id": version_id, "version_tag": version_tag},
                actor_id=created_by,
            )

    logger.info("Dataset version created: %s → %s (%s)", dataset_id, version_tag, version_id)
    return version_id


def get_version(version_id: str) -> dict[str, Any] | None:
    """Return a single version snapshot record or None if not found."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, dataset_id, version_tag, layer_snapshot,
                       created_by, locked_at, notes
                FROM dataset_versions
                WHERE id = %s
                """,
                (version_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    v_id, d_id, tag, snapshot, creator, locked_at, notes = row
    return {
        "id": str(v_id),
        "dataset_id": str(d_id),
        "version_tag": tag,
        "layer_snapshot": snapshot,
        "created_by": creator,
        "locked_at": locked_at.isoformat() if locked_at else None,
        "notes": notes,
    }


def list_dataset_versions(dataset_id: str) -> list[dict[str, Any]]:
    """Return all version snapshots for a dataset, most-recent first."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, dataset_id, version_tag, layer_snapshot,
                       created_by, locked_at, notes
                FROM dataset_versions
                WHERE dataset_id = %s
                ORDER BY locked_at DESC
                """,
                (dataset_id,),
            )
            rows = cur.fetchall()
    result = []
    for row in rows:
        v_id, d_id, tag, snapshot, creator, locked_at, notes = row
        result.append({
            "id": str(v_id),
            "dataset_id": str(d_id),
            "version_tag": tag,
            "layer_snapshot": snapshot,
            "created_by": creator,
            "locked_at": locked_at.isoformat() if locked_at else None,
            "notes": notes,
        })
    return result


# =============================================================================
# DATA LINEAGE TRACING
# =============================================================================

def get_dataset_lineage(dataset_id: str) -> dict[str, Any]:
    """
    Return full lineage for a dataset: dataset metadata, all layers with
    their provenance, validation summary, and all version snapshots.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Dataset-level info
            cur.execute(
                """
                SELECT id, source_id, name, description, layer_type,
                       vintage_year, ingested_at, confidence, srs_original,
                       metadata, is_active, is_archived
                FROM datasets WHERE id = %s
                """,
                (dataset_id,),
            )
            ds_row = cur.fetchone()
            if not ds_row:
                return {}

            ds_cols = ["id", "source_id", "name", "description", "layer_type",
                       "vintage_year", "ingested_at", "confidence", "srs_original",
                       "metadata", "is_active", "is_archived"]
            ds = dict(zip(ds_cols, ds_row))
            ds["id"] = str(ds["id"])
            if ds["ingested_at"]:
                ds["ingested_at"] = ds["ingested_at"].isoformat()

            # Layers with validation summary
            cur.execute(
                """
                SELECT l.id, l.name, l.layer_type, l.import_status, l.confidence,
                       l.vintage_year, l.ingested_at, l.feature_count, l.metadata,
                       l.import_error,
                       COUNT(vr.id) FILTER (WHERE vr.severity = 'error') AS error_count,
                       COUNT(vr.id) FILTER (WHERE vr.severity = 'warning') AS warning_count
                FROM layers l
                LEFT JOIN layer_validation_results vr ON vr.layer_id = l.id
                WHERE l.dataset_id = %s
                GROUP BY l.id
                ORDER BY l.ingested_at ASC
                """,
                (dataset_id,),
            )
            layer_rows = cur.fetchall()

    layers = []
    for row in layer_rows:
        (l_id, l_name, l_ltype, l_status, l_conf, l_vintage, l_ingested,
         l_count, l_meta, l_err, errs, warns) = row
        layers.append({
            "id": str(l_id),
            "name": l_name,
            "layer_type": l_ltype,
            "import_status": l_status,
            "confidence": l_conf,
            "vintage_year": l_vintage,
            "ingested_at": l_ingested.isoformat() if l_ingested else None,
            "feature_count": l_count,
            "metadata": l_meta,
            "import_error": l_err,
            "validation_errors": errs or 0,
            "validation_warnings": warns or 0,
        })

    versions = list_dataset_versions(dataset_id)

    return {
        "dataset": ds,
        "layers": layers,
        "versions": versions,
    }


def get_score_lineage(site_id: str) -> dict[str, Any]:
    """
    Trace every factor score for a candidate site back to its source layer,
    ingestion run, and confidence level.

    Returns a dict mapping factor_name → {layer_id, source_id, ingested_at, confidence}.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cs.composite_score, cs.pop_density_score, cs.income_score,
                       cs.transit_score, cs.road_score, cs.competitor_gap_score,
                       cs.data_sources, cs.partial_factors, cs.has_partial_data,
                       ar.dataset_snapshot, ar.id AS run_id
                FROM candidate_sites cs
                JOIN analysis_runs ar ON ar.id = cs.run_id
                WHERE cs.id = %s
                """,
                (site_id,),
            )
            row = cur.fetchone()
    if not row:
        return {}

    (comp, pop, inc, trans, road, gap,
     data_sources, partial_factors, has_partial,
     dataset_snapshot, run_id) = row

    scores = {
        "population_density": pop,
        "income": inc,
        "transit": trans,
        "road_visibility": road,
        "competitor_gap": gap,
    }

    # data_sources JSONB: {factor: layer_id}
    sources = data_sources if isinstance(data_sources, dict) else {}
    snapshot = dataset_snapshot if isinstance(dataset_snapshot, dict) else {}

    lineage: dict[str, Any] = {}
    for factor, score in scores.items():
        layer_id = sources.get(factor)
        snap_info = snapshot.get(str(layer_id), {}) if layer_id else {}
        lineage[factor] = {
            "score": float(score) if score is not None else None,
            "layer_id": layer_id,
            "ingested_at": snap_info.get("ingested_at"),
            "confidence": snap_info.get("confidence"),
            "is_partial": factor in (partial_factors or []),
        }

    return {
        "site_id": site_id,
        "run_id": str(run_id),
        "composite_score": float(comp) if comp is not None else None,
        "has_partial_data": has_partial,
        "factor_lineage": lineage,
    }

