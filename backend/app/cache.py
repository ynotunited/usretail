"""
In-process TTL cache for expensive GIS computations.

Uses cachetools.TTLCache (thread-safe with RLock).
Keys are invalidated explicitly on new data imports or analysis runs.

Cache entries:
  "dataset_list"          → list_datasets response
  "analysis_run:{run_id}" → get_run response
  "sites:{run_id}"        → list_sites response
  "suitability_top"       → top-ranked sites across all runs

TTL values (configurable via env):
  CACHE_TTL_DATASETS  = 120s (2 min) — datasets change infrequently
  CACHE_TTL_RUNS      = 300s (5 min) — completed runs are immutable
  CACHE_TTL_SITES     = 300s (5 min)
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# ── Cache instances ────────────────────────────────────────────────────────────

_lock = threading.RLock()

_dataset_cache: TTLCache = TTLCache(maxsize=32, ttl=120)    # dataset list, 2 min
_run_cache: TTLCache = TTLCache(maxsize=256, ttl=300)       # run details, 5 min
_sites_cache: TTLCache = TTLCache(maxsize=256, ttl=300)     # sites per run, 5 min
_suitability_cache: TTLCache = TTLCache(maxsize=8, ttl=120) # top sites, 2 min


# ── Generic get/set ────────────────────────────────────────────────────────────

def get_cached(cache: TTLCache, key: str) -> Any | None:
    with _lock:
        return cache.get(key)


def set_cached(cache: TTLCache, key: str, value: Any) -> None:
    with _lock:
        cache[key] = value


# ── Public accessors by resource type ─────────────────────────────────────────

def get_dataset_list() -> Any | None:
    return get_cached(_dataset_cache, "dataset_list")


def set_dataset_list(value: Any) -> None:
    set_cached(_dataset_cache, "dataset_list", value)


def invalidate_datasets() -> None:
    with _lock:
        _dataset_cache.clear()
    logger.debug("Dataset cache invalidated.")


def get_run(run_id: str) -> Any | None:
    return get_cached(_run_cache, f"run:{run_id}")


def set_run(run_id: str, value: Any) -> None:
    set_cached(_run_cache, f"run:{run_id}", value)


def invalidate_run(run_id: str) -> None:
    with _lock:
        _run_cache.pop(f"run:{run_id}", None)
    logger.debug("Run cache invalidated: %s", run_id)


def get_sites(run_id: str) -> Any | None:
    return get_cached(_sites_cache, f"sites:{run_id}")


def set_sites(run_id: str, value: Any) -> None:
    set_cached(_sites_cache, f"sites:{run_id}", value)


def get_suitability_top() -> Any | None:
    return get_cached(_suitability_cache, "suitability_top")


def set_suitability_top(value: Any) -> None:
    set_cached(_suitability_cache, "suitability_top", value)


def invalidate_suitability() -> None:
    with _lock:
        _suitability_cache.clear()
    logger.debug("Suitability cache invalidated.")


def invalidate_all() -> None:
    """Full cache flush — call after major data imports."""
    with _lock:
        _dataset_cache.clear()
        _run_cache.clear()
        _sites_cache.clear()
        _suitability_cache.clear()
    logger.info("All caches flushed.")
