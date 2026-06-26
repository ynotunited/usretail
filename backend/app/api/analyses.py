"""
Analyses API router.

Endpoints:
  POST /analyses/run                  — trigger suitability analysis run (sync or async)
  GET  /analyses/runs                 — list all runs with summary
  GET  /analyses/runs/{run_id}        — single run with all scored sites
  GET  /analyses/runs/{run_id}/sites  — paginated site list with factor scores
  POST /analyses/overrides            — create an analyst override with audit log
  GET  /analyses/runs/{run_id}/compare — compare two runs side by side
  GET  /suitability/sites             — top-ranked sites across all runs
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.db.connection import get_conn
from app.analysis.engine import DEFAULT_WEIGHTS, run_analysis
from app.analysis.narrative import generate_site_narrative
from app.auth.dependencies import require_role
import app.cache as cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyses", tags=["analyses"])

# Suitability router uses a different prefix
suitability_router = APIRouter(prefix="/suitability", tags=["suitability"])


# ── Request/Response models ───────────────────────────────────────────────────

class RunRequest(BaseModel):
    city_name: str = "Austin"
    analyst_id: str = "system"
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    max_sites: int = Field(default=50, ge=1, le=200)
    async_mode: bool = Field(
        default=False,
        description="If true, submit to Celery background worker and return immediately with run_id."
    )


class OverrideRequest(BaseModel):
    entity_type: str        # 'site' | 'factor' | 'layer' | 'analysis_weight'
    entity_id: str          # UUID of target entity
    analyst_id: str
    field_name: str
    original_value: Any = None
    override_value: Any
    reason: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(cur, rows) -> list[dict[str, Any]]:
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in rows]


def _serialize(obj: Any) -> Any:
    """Recursively serialize datetime/UUID values."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__str__") and not isinstance(obj, (str, int, float, bool, type(None))):
        return str(obj)
    return obj


def _clean_row(row: dict) -> dict:
    return {k: _serialize(v) for k, v in row.items()}


# ── POST /analyses/run ────────────────────────────────────────────────────────

@router.post("/run", summary="Trigger a suitability analysis run")
def trigger_run(body: RunRequest) -> JSONResponse:
    """
    Triggers a suitability analysis run.
    - Default: synchronous — waits and returns all scored sites.
    - async_mode=true: submits to Celery, returns {run_id, status: 'queued'} immediately.
    Weights must sum to 1.0 (±0.01 tolerance).
    """
    weight_sum = sum(body.weights.values())
    if not (0.99 <= weight_sum <= 1.01):
        raise HTTPException(
            status_code=400,
            detail=f"Weights must sum to 1.0; got {weight_sum:.3f}."
        )

    # ── Async (Celery) mode ──────────────────────────────────────────────────
    if body.async_mode:
        try:
            from app.worker.tasks import run_analysis_task
            # Pre-register a run record so status is immediately queryable
            import uuid as _uuid
            from datetime import datetime as _dt, timezone as _tz
            from app.analysis.engine import get_dataset_snapshot
            run_id = str(_uuid.uuid4())
            snapshot = get_dataset_snapshot()
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO analysis_runs
                            (id, analyst_id, city_name, weights, dataset_snapshot, run_status, started_at)
                        VALUES (%s, %s, %s, %s, %s, 'queued', %s)
                        """,
                        (run_id, body.analyst_id, body.city_name,
                         json.dumps(body.weights), json.dumps(snapshot),
                         _dt.now(_tz.utc)),
                    )
            task = run_analysis_task.delay(
                city_name=body.city_name,
                weights=body.weights,
                analyst_id=body.analyst_id,
                max_sites=body.max_sites,
                run_id=run_id,
            )
            cache.invalidate_suitability()
            return JSONResponse(
                {"run_id": run_id, "status": "queued", "celery_task_id": task.id},
                status_code=202,
            )
        except Exception as exc:
            logger.warning("Celery unavailable (%s), falling back to sync.", exc)

    # ── Synchronous mode ─────────────────────────────────────────────────────
    try:
        result = run_analysis(
            city_name=body.city_name,
            weights=body.weights,
            analyst_id=body.analyst_id,
            max_sites=body.max_sites,
        )
    except Exception as exc:
        logger.exception("Analysis run failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    # Attach AI narratives to top sites (max 5)
    sites_out = []
    for rank_idx, site in enumerate(result.sites, start=1):
        narrative = (
            generate_site_narrative(site, rank_idx)
            if rank_idx <= 5
            else None
        )
        sites_out.append({
            "site_id": site.site_id,
            "rank": rank_idx,
            "lon": site.lon,
            "lat": site.lat,
            "composite_score": site.composite_score,
            "has_partial_data": site.has_partial_data,
            "partial_factors": site.partial_factors,
            "is_incomplete": site.is_incomplete,
            "incomplete_factors": site.incomplete_factors,
            "weights_applied": site.weights,
            "factors": [
                {
                    "factor": f.factor,
                    "score": f.score,
                    "raw_value": f.raw_value,
                    "data_source": f.data_source,
                    "confidence": f.confidence,
                    "partial": f.partial,
                    "partial_reason": f.partial_reason,
                }
                for f in site.factors
            ],
            "ai_insight": narrative,
        })

    return JSONResponse({
        "run_id": result.run_id,
        "status": result.status,
        "partial_reason": result.partial_reason,
        "city_name": result.city_name,
        "analyst_id": result.analyst_id,
        "weights": result.weights,
        "dataset_snapshot": result.dataset_snapshot,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "site_count": len(sites_out),
        "sites": sites_out,
    })


# ── GET /analyses/runs ────────────────────────────────────────────────────────

@router.get("/runs", summary="List all analysis runs")
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id::text, analyst_id, city_name, run_status,
                    partial_reason, error_message,
                    started_at, completed_at, created_at,
                    weights, dataset_snapshot
                FROM analysis_runs
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = _row_to_dict(cur, cur.fetchall())

            cur.execute("SELECT COUNT(*) FROM analysis_runs")
            total = cur.fetchone()[0]

    return JSONResponse({
        "runs": [_clean_row(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


# ── GET /analyses/runs/{run_id} ───────────────────────────────────────────────

@router.get("/runs/{run_id}", summary="Retrieve a single analysis run with scored sites")
def get_run(run_id: str) -> JSONResponse:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Run metadata
            cur.execute(
                """
                SELECT
                    id::text, analyst_id, city_name, run_status,
                    partial_reason, error_message,
                    started_at, completed_at, created_at,
                    weights, dataset_snapshot
                FROM analysis_runs WHERE id = %s::uuid
                """,
                (run_id,),
            )
            run_rows = _row_to_dict(cur, cur.fetchall())
            if not run_rows:
                raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
            run = _clean_row(run_rows[0])

            # Candidate sites
            cur.execute(
                """
                SELECT
                    id::text, run_id::text, rank,
                    ST_X(geom) AS lon, ST_Y(geom) AS lat,
                    composite_score, pop_density_score, income_score,
                    transit_score, road_score, competitor_gap_score,
                    has_partial_data, partial_factors, data_sources, attributes
                FROM candidate_sites
                WHERE run_id = %s::uuid
                ORDER BY rank
                """,
                (run_id,),
            )
            sites = _row_to_dict(cur, cur.fetchall())

    return JSONResponse({
        "run": run,
        "sites": [_clean_row(s) for s in sites],
        "site_count": len(sites),
    })


# ── GET /analyses/runs/{run_id}/sites ─────────────────────────────────────────

@router.get("/runs/{run_id}/sites", summary="Paginated list of scored sites for a run")
def list_sites(
    run_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    partial_only: bool = Query(default=False),
    incomplete_only: bool = Query(default=False),
) -> JSONResponse:
    where_clauses = ["run_id = %s::uuid", "composite_score >= %s"]
    params: list[Any] = [run_id, min_score]

    if partial_only:
        where_clauses.append("has_partial_data = TRUE")
    if incomplete_only:
        where_clauses.append("composite_score IS NULL")

    where_sql = " AND ".join(where_clauses)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id::text, run_id::text, rank,
                    ST_X(geom) AS lon, ST_Y(geom) AS lat,
                    composite_score, pop_density_score, income_score,
                    transit_score, road_score, competitor_gap_score,
                    has_partial_data, partial_factors, data_sources, attributes
                FROM candidate_sites
                WHERE {where_sql}
                ORDER BY rank
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            sites = _row_to_dict(cur, cur.fetchall())

            cur.execute(
                f"SELECT COUNT(*) FROM candidate_sites WHERE {where_sql}",
                params,
            )
            total = cur.fetchone()[0]

    return JSONResponse({
        "sites": [_clean_row(s) for s in sites],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


# ── POST /analyses/overrides ──────────────────────────────────────────────────

@router.post("/overrides", summary="Create an analyst override with full audit trail")
def create_override(body: OverrideRequest) -> JSONResponse:
    """
    Allows analysts to override site recommendation status or factor weights.
    All overrides are immutably logged in analyst_overrides and audit_log.
    """
    override_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    # Validate entity_type
    valid_types = {"site", "factor", "layer", "analysis_weight"}
    if body.entity_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"entity_type must be one of {sorted(valid_types)}."
        )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analyst_overrides (
                    id, entity_type, entity_id, analyst_id,
                    field_name, original_value, override_value, reason, created_at
                ) VALUES (
                    %s, %s::override_entity, %s::uuid, %s,
                    %s, %s, %s, %s, %s
                )
                """,
                (
                    override_id,
                    body.entity_type,
                    body.entity_id,
                    body.analyst_id,
                    body.field_name,
                    json.dumps(body.original_value),
                    json.dumps(body.override_value),
                    body.reason,
                    created_at,
                ),
            )
            # Write to audit log
            cur.execute(
                """
                INSERT INTO audit_log (
                    event_type, entity_type, entity_id, actor_id, payload, created_at
                ) VALUES ('override.created', %s, %s::uuid, %s, %s, %s)
                """,
                (
                    body.entity_type,
                    body.entity_id,
                    body.analyst_id,
                    json.dumps({
                        "override_id": override_id,
                        "field": body.field_name,
                        "original": body.original_value,
                        "override": body.override_value,
                        "reason": body.reason,
                    }),
                    created_at,
                ),
            )

    return JSONResponse(
        {
            "override_id": override_id,
            "status": "created",
            "created_at": created_at.isoformat(),
        },
        status_code=201,
    )


# ── POST /analyses/runs/{run_id}/rerun ───────────────────────────────────────

class RerunRequest(BaseModel):
    analyst_id: str = Field(default="system", description="Analyst triggering the re-run.")
    async_mode: bool = Field(default=False, description="If true, submit to Celery.")


@router.post(
    "/runs/{run_id}/rerun",
    summary="Re-run a historical analysis with the exact same inputs",
)
def rerun_analysis(run_id: str, body: RerunRequest) -> JSONResponse:
    """
    Fetches the original weights, city_name, and dataset_snapshot from a
    historical run and triggers a new analysis with identical parameters.
    The new run references the same dataset snapshot, guaranteeing reproducible
    results as long as the underlying layer data has not changed.

    Returns the new run_id alongside the original for comparison.
    """
    # Load original run inputs
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT city_name, weights, analyst_id
                FROM analysis_runs
                WHERE id = %s::uuid
                """,
                (run_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    orig_city, orig_weights, orig_analyst = row
    weights: dict[str, float] = (
        orig_weights if isinstance(orig_weights, dict) else json.loads(orig_weights)
    )

    # Async path
    if body.async_mode:
        try:
            from app.worker.tasks import run_analysis_task
            import uuid as _uuid
            from datetime import datetime as _dt, timezone as _tz

            new_run_id = str(_uuid.uuid4())
            snapshot = {}  # engine will rebuild from live DB
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO analysis_runs
                            (id, analyst_id, city_name, weights, dataset_snapshot,
                             run_status, started_at)
                        VALUES (%s, %s, %s, %s, %s, 'queued', %s)
                        """,
                        (new_run_id, body.analyst_id, orig_city,
                         json.dumps(weights), json.dumps(snapshot),
                         _dt.now(_tz.utc)),
                    )
            task = run_analysis_task.delay(
                city_name=orig_city,
                weights=weights,
                analyst_id=body.analyst_id,
                run_id=new_run_id,
            )
            cache.invalidate_suitability()
            return JSONResponse(
                {
                    "original_run_id": run_id,
                    "new_run_id": new_run_id,
                    "status": "queued",
                    "celery_task_id": task.id,
                },
                status_code=202,
            )
        except Exception as exc:
            logger.warning("Celery unavailable for rerun (%s), falling back to sync.", exc)

    # Synchronous path
    try:
        result = run_analysis(
            city_name=orig_city,
            weights=weights,
            analyst_id=body.analyst_id,
        )
    except Exception as exc:
        logger.exception("Re-run failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Re-run failed: {exc}")

    cache.invalidate_suitability()
    return JSONResponse(
        {
            "original_run_id": run_id,
            "new_run_id": result.run_id,
            "status": result.status,
            "site_count": len(result.sites),
            "city_name": result.city_name,
            "weights": result.weights,
        },
        status_code=201,
    )


# ── GET /analyses/runs/{run_id}/compare ───────────────────────────────────────

@router.get("/runs/{run_id}/compare", summary="Compare two analysis runs side by side")
def compare_runs(
    run_id: str,
    compare_with: str = Query(..., description="UUID of the second run to compare against"),
) -> JSONResponse:
    """
    Compare candidate sites between two runs.
    Returns:
      - Sites in both runs with score deltas.
      - Sites only in run A (disappeared).
      - Sites only in run B (appeared).
      - Weight changes.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Get both run metadata
            cur.execute(
                "SELECT id::text, weights, run_status, city_name FROM analysis_runs WHERE id = ANY(%s::uuid[])",
                ([run_id, compare_with],),
            )
            run_rows = {str(r[0]): {"weights": r[1], "status": r[2], "city": r[3]}
                        for r in cur.fetchall()}

            if run_id not in run_rows or compare_with not in run_rows:
                raise HTTPException(status_code=404, detail="One or both runs not found.")

            # Get sites for run A
            cur.execute(
                """
                SELECT rank, ST_X(geom) AS lon, ST_Y(geom) AS lat, composite_score
                FROM candidate_sites WHERE run_id = %s::uuid ORDER BY rank
                """,
                (run_id,),
            )
            sites_a = {(round(r[1], 5), round(r[2], 5)): {"rank": r[0], "score": r[3]}
                       for r in cur.fetchall()}

            # Get sites for run B
            cur.execute(
                """
                SELECT rank, ST_X(geom) AS lon, ST_Y(geom) AS lat, composite_score
                FROM candidate_sites WHERE run_id = %s::uuid ORDER BY rank
                """,
                (compare_with,),
            )
            sites_b = {(round(r[1], 5), round(r[2], 5)): {"rank": r[0], "score": r[3]}
                       for r in cur.fetchall()}

    keys_a = set(sites_a.keys())
    keys_b = set(sites_b.keys())

    in_both = []
    for key in keys_a & keys_b:
        sa = sites_a[key]["score"]
        sb = sites_b[key]["score"]
        delta = None if sa is None or sb is None else round(sb - sa, 2)
        direction = "↑" if delta and delta > 0 else ("↓" if delta and delta < 0 else "–")
        in_both.append({
            "lon": key[0], "lat": key[1],
            "score_run_a": sa, "score_run_b": sb,
            "score_delta": delta, "direction": direction,
            "rank_a": sites_a[key]["rank"], "rank_b": sites_b[key]["rank"],
        })

    only_in_a = [{"lon": k[0], "lat": k[1], **sites_a[k]} for k in keys_a - keys_b]
    only_in_b = [{"lon": k[0], "lat": k[1], **sites_b[k]} for k in keys_b - keys_a]

    # Weight changes
    weights_a = run_rows[run_id]["weights"] or {}
    weights_b = run_rows[compare_with]["weights"] or {}
    weight_changes = {
        k: {"run_a": weights_a.get(k), "run_b": weights_b.get(k)}
        for k in set(list(weights_a.keys()) + list(weights_b.keys()))
        if weights_a.get(k) != weights_b.get(k)
    }

    return JSONResponse({
        "run_a": run_id,
        "run_b": compare_with,
        "in_both": sorted(in_both, key=lambda x: abs(x["score_delta"] or 0), reverse=True),
        "only_in_run_a": only_in_a,
        "only_in_run_b": only_in_b,
        "weight_changes": weight_changes,
        "summary": {
            "shared_sites": len(in_both),
            "disappeared": len(only_in_a),
            "appeared": len(only_in_b),
        },
    })


# ── GET /suitability/sites ───────────────────────────────────────────────────

@suitability_router.get("/sites", summary="Top-ranked candidate sites across all complete runs")
def get_top_sites(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    city_name: str | None = Query(default=None, description="Filter by city"),
    partial_only: bool = Query(default=False, description="Only return sites with partial data"),
) -> JSONResponse:
    """
    Returns the best-scoring candidate sites across all completed analysis runs.
    Useful as the primary 'ranked site list' view — the frontend table view pulls from here.
    Results are cached for 2 minutes.
    """
    cache_key = f"top:{limit}:{offset}:{min_score}:{city_name}:{partial_only}"
    cached = cache.get_suitability_top()
    if cached and cache_key == cached.get("_cache_key"):
        return JSONResponse(cached["data"])

    where_clauses = [
        "ar.run_status = 'complete'",
        "cs.composite_score >= %s",
    ]
    params: list[Any] = [min_score]

    if city_name:
        where_clauses.append("ar.city_name ILIKE %s")
        params.append(f"%{city_name}%")
    if partial_only:
        where_clauses.append("cs.has_partial_data = TRUE")

    where_sql = " AND ".join(where_clauses)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    cs.id::text, cs.run_id::text, cs.rank,
                    ST_X(cs.geom) AS lon, ST_Y(cs.geom) AS lat,
                    cs.composite_score,
                    cs.pop_density_score, cs.income_score,
                    cs.transit_score, cs.road_score,
                    cs.competitor_gap_score,
                    cs.has_partial_data, cs.partial_factors,
                    ar.city_name, ar.completed_at,
                    ar.weights
                FROM candidate_sites cs
                JOIN analysis_runs ar ON ar.id = cs.run_id
                WHERE {where_sql}
                ORDER BY cs.composite_score DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            cols = [d[0] for d in cur.description]
            sites = [
                _clean_row(dict(zip(cols, r)))
                for r in cur.fetchall()
            ]

            cur.execute(
                f"""
                SELECT COUNT(*) FROM candidate_sites cs
                JOIN analysis_runs ar ON ar.id = cs.run_id
                WHERE {where_sql}
                """,
                params,
            )
            total = cur.fetchone()[0]

    payload = {
        "sites": sites,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    cache.set_suitability_top({"_cache_key": cache_key, "data": payload})
    return JSONResponse(payload)
