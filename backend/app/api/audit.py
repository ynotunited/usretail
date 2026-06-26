"""
Audit trail API router.

Endpoints:
  GET /audit                  — paginated audit log with filters
  GET /audit/{entity_id}      — full ordered trail for a specific entity

Access control:
  GET /audit               → admin role required
  GET /audit/{entity_id}   → reviewer minimum (can see their own entity trails)

CSV export is available via ?format=csv on both endpoints.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse

from app.db.connection import get_conn
from app.auth.dependencies import require_role, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"])


def _row_to_dict(cur, rows) -> list[dict[str, Any]]:
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in rows]


def _clean(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "__str__") and not isinstance(v, (str, int, float, bool, type(None))):
        return str(v)
    return v


def _clean_row(row: dict) -> dict:
    return {k: _clean(v) for k, v in row.items()}


# ── GET /audit ─────────────────────────────────────────────────────────────────

@router.get("", summary="Paginated audit log (admin only)")
def list_audit(
    event_type: str | None = Query(default=None, description="Filter by event type"),
    actor_id: str | None = Query(default=None, description="Filter by actor"),
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    since: str | None = Query(default=None, description="ISO datetime lower bound"),
    until: str | None = Query(default=None, description="ISO datetime upper bound"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    format: str = Query(default="json", description="'json' or 'csv'"),
    _user: dict = Depends(require_role("admin")),
) -> Any:
    where_clauses = ["1=1"]
    params: list[Any] = []

    if event_type:
        where_clauses.append("event_type = %s")
        params.append(event_type)
    if actor_id:
        where_clauses.append("actor_id = %s")
        params.append(actor_id)
    if entity_type:
        where_clauses.append("entity_type = %s")
        params.append(entity_type)
    if since:
        where_clauses.append("created_at >= %s")
        params.append(since)
    if until:
        where_clauses.append("created_at <= %s")
        params.append(until)

    where_sql = " AND ".join(where_clauses)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, event_type, entity_type, entity_id::text,
                       actor_id, payload, ip_address::text, created_at
                FROM audit_log
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = [_clean_row(r) for r in _row_to_dict(cur, cur.fetchall())]

            cur.execute(f"SELECT COUNT(*) FROM audit_log WHERE {where_sql}", params)
            total = cur.fetchone()[0]

    if format == "csv":
        return _to_csv_response(rows, filename="audit_log.csv")

    return JSONResponse({"events": rows, "total": total, "limit": limit, "offset": offset})


# ── GET /audit/{entity_id} ────────────────────────────────────────────────────

@router.get("/{entity_id}", summary="Full audit trail for a specific entity")
def get_entity_audit(
    entity_id: str,
    format: str = Query(default="json"),
    _user: dict = Depends(require_role("reviewer")),
) -> Any:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, entity_type, entity_id::text,
                       actor_id, payload, ip_address::text, created_at
                FROM audit_log
                WHERE entity_id = %s::uuid
                ORDER BY created_at ASC
                """,
                (entity_id,),
            )
            rows = [_clean_row(r) for r in _row_to_dict(cur, cur.fetchall())]

            # Also pull analyst overrides for this entity
            cur.execute(
                """
                SELECT id::text, entity_type, analyst_id, field_name,
                       original_value, override_value, reason, created_at
                FROM analyst_overrides
                WHERE entity_id = %s::uuid
                ORDER BY created_at ASC
                """,
                (entity_id,),
            )
            overrides = [_clean_row(r) for r in _row_to_dict(cur, cur.fetchall())]

    if format == "csv":
        return _to_csv_response(rows, filename=f"audit_{entity_id[:8]}.csv")

    return JSONResponse({
        "entity_id": entity_id,
        "event_count": len(rows),
        "override_count": len(overrides),
        "events": rows,
        "overrides": overrides,
    })


# ── CSV helper ─────────────────────────────────────────────────────────────────

def _to_csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    if not rows:
        output = io.StringIO()
        output.write("no data\n")
        output.seek(0)
        return StreamingResponse(
            iter([output.read()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── GET /audit/export ─────────────────────────────────────────────────────────

@router.get("/export", summary="Full audit trail export (admin only)")
def export_audit(
    format: str = Query(default="json", description="'json' or 'csv'"),
    since: str | None = Query(default=None, description="ISO datetime lower bound"),
    until: str | None = Query(default=None, description="ISO datetime upper bound"),
    entity_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    _user: dict = Depends(require_role("admin")),
) -> Any:
    """
    Export the complete audit trail for compliance review.
    Includes audit_log events AND analyst_overrides in a single payload.
    Admin role required.
    """
    where_clauses = ["1=1"]
    params: list[Any] = []
    if since:
        where_clauses.append("created_at >= %s")
        params.append(since)
    if until:
        where_clauses.append("created_at <= %s")
        params.append(until)
    if entity_type:
        where_clauses.append("entity_type = %s")
        params.append(entity_type)
    if actor_id:
        where_clauses.append("actor_id = %s")
        params.append(actor_id)
    where_sql = " AND ".join(where_clauses)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, event_type, entity_type, entity_id::text,
                       actor_id, payload, ip_address::text, created_at
                FROM audit_log
                WHERE {where_sql}
                ORDER BY created_at ASC
                """,
                params,
            )
            audit_rows = [_clean_row(r) for r in _row_to_dict(cur, cur.fetchall())]

            cur.execute(
                """
                SELECT id::text, entity_type, entity_id::text, analyst_id, field_name,
                       original_value, override_value, reason, created_at
                FROM analyst_overrides
                ORDER BY created_at ASC
                """,
            )
            override_rows = [_clean_row(r) for r in _row_to_dict(cur, cur.fetchall())]

    if format == "csv":
        # Combine both tables into one flat CSV for compliance
        combined = [{"_source": "audit_log", **r} for r in audit_rows]
        combined += [{"_source": "analyst_overrides", **r} for r in override_rows]
        return _to_csv_response(combined, filename="full_audit_export.csv")

    import json as _json
    payload = _json.dumps(
        {
            "exported_at": datetime.now().isoformat(),
            "audit_event_count": len(audit_rows),
            "override_count": len(override_rows),
            "audit_events": audit_rows,
            "analyst_overrides": override_rows,
        },
        default=str,
    )
    return StreamingResponse(
        iter([payload]),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="full_audit_export.json"'},
    )


# ── GET /audit/overrides ──────────────────────────────────────────────────────

@router.get("/overrides", summary="List all analyst overrides (admin only)")
def list_overrides(
    entity_type: str | None = Query(default=None),
    analyst_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user: dict = Depends(require_role("admin")),
) -> Any:
    """
    Returns all analyst overrides paginated, filtered by entity type and actor.
    Supports compliance review of every manual change made to the system.
    Admin role required.
    """
    where_clauses = ["1=1"]
    params: list[Any] = []
    if entity_type:
        where_clauses.append("entity_type = %s::override_entity")
        params.append(entity_type)
    if analyst_id:
        where_clauses.append("analyst_id = %s")
        params.append(analyst_id)
    where_sql = " AND ".join(where_clauses)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text, entity_type, entity_id::text, analyst_id, field_name,
                       original_value, override_value, reason, created_at
                FROM analyst_overrides
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = [_clean_row(r) for r in _row_to_dict(cur, cur.fetchall())]
            cur.execute(
                f"SELECT COUNT(*) FROM analyst_overrides WHERE {where_sql}",
                params,
            )
            total = cur.fetchone()[0]

    return JSONResponse({"overrides": rows, "total": total, "limit": limit, "offset": offset})

