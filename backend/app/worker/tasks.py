"""
Celery tasks for RetailIQ background processing.

Each task mirrors the synchronous endpoint logic but:
  1. Runs in a separate process (Celery worker)
  2. Updates run_status in Postgres so the API can poll progress
  3. Records task_id for status tracking via GET /analyses/runs/{run_id}

Task IDs are stored in analysis_runs.metadata['celery_task_id'] so
analysts can correlate Celery task status with run records.
"""

from __future__ import annotations

import json
import logging

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.worker.celery_app import celery_app
from app.db.connection import init_pool

logger = logging.getLogger(__name__)


class _DBTask(Task):
    """Base task that initialises the DB connection pool once per worker process."""
    _pool_ready = False

    def __call__(self, *args, **kwargs):
        if not self.__class__._pool_ready:
            init_pool()
            self.__class__._pool_ready = True
        return super().__call__(*args, **kwargs)


# ── Task: run_analysis_task ────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=_DBTask,
    name="retailiq.run_analysis",
    max_retries=0,
)
def run_analysis_task(
    self: Task,
    city_name: str,
    weights: dict,
    analyst_id: str,
    max_sites: int = 50,
    run_id: str | None = None,
) -> dict:
    """
    Async wrapper around engine.run_analysis().
    Stores the Celery task_id in the analysis_run metadata if run_id given.
    """
    from app.analysis.engine import run_analysis
    from app.db.connection import get_conn

    # Attach task ID to run metadata
    if run_id:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE analysis_runs
                        SET dataset_snapshot = dataset_snapshot || jsonb_build_object('celery_task_id', %s)
                        WHERE id = %s::uuid
                        """,
                        (self.request.id, run_id),
                    )
        except Exception:
            pass  # non-critical

    try:
        result = run_analysis(
            city_name=city_name,
            weights=weights,
            analyst_id=analyst_id,
            max_sites=max_sites,
        )
        return {
            "run_id": result.run_id,
            "status": result.status,
            "site_count": len(result.sites),
        }
    except SoftTimeLimitExceeded:
        logger.error("Analysis task timed out (run_id=%s).", run_id)
        raise
    except Exception as exc:
        logger.exception("Analysis task failed (run_id=%s): %s", run_id, exc)
        raise self.retry(exc=exc, countdown=0, max_retries=0)


# ── Task: geocode_dataset_task ─────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=_DBTask,
    name="retailiq.geocode_dataset",
    max_retries=1,
)
def geocode_dataset_task(self: Task, layer_id: str, actor_id: str = "system") -> dict:
    """Batch geocode all address-only features in a layer."""
    from app.geocoding.geocoder import geocode_layer

    try:
        stats = geocode_layer(layer_id)
        return {"layer_id": layer_id, **stats}
    except Exception as exc:
        logger.exception("Geocoding task failed for layer %s: %s", layer_id, exc)
        raise self.retry(exc=exc, countdown=30)


# ── Task: generate_report_task ────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=_DBTask,
    name="retailiq.generate_report",
    max_retries=0,
)
def generate_report_task(self: Task, run_id: str, analyst_notes: str = "") -> dict:
    """Background report generation — stores result in analysis_runs.metadata."""
    from app.api.reports import _build_report_data
    from app.db.connection import get_conn

    try:
        report = _build_report_data(run_id=run_id, analyst_notes=analyst_notes)

        # Store report summary back in run metadata
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE analysis_runs
                    SET dataset_snapshot = dataset_snapshot || jsonb_build_object(
                        'report_generated_at', %s,
                        'report_top_site_count', %s
                    )
                    WHERE id = %s::uuid
                    """,
                    (
                        report.get("generated_at"),
                        len(report.get("top_sites", [])),
                        run_id,
                    ),
                )
        return {"run_id": run_id, "status": "report_ready"}
    except Exception as exc:
        logger.exception("Report generation failed for run %s: %s", run_id, exc)
        raise
