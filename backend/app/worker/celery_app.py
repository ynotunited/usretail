"""
Celery application for RetailIQ background jobs.

Broker: Redis (redis://redis:6379/0)
Result backend: Redis (redis://redis:6379/1)

Tasks:
  run_analysis_task    – wraps engine.run_analysis() for async execution
  geocode_dataset_task – batch geocodes a full layer
  generate_report_task – background report generation

Workers are started via:
  celery -A app.worker.celery_app worker --loglevel=info

Task status is tracked in both the Celery result backend (Redis)
and the analysis_runs.run_status column (Postgres) for durability.
"""

from __future__ import annotations

import logging
import os

from celery import Celery

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_RESULT_URL = os.getenv("REDIS_RESULT_URL", "redis://redis:6379/1")

celery_app = Celery(
    "retailiq",
    broker=REDIS_URL,
    backend=REDIS_RESULT_URL,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,               # only ack after task completes
    worker_prefetch_multiplier=1,      # one task at a time per worker
    result_expires=86400,              # results expire after 24 hours
    task_soft_time_limit=300,          # 5 min soft limit
    task_time_limit=360,               # 6 min hard limit
)
