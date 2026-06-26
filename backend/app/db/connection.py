"""
PostGIS connection pool.
Provides a context manager for acquiring/releasing connections.
"""

import logging
from contextlib import contextmanager
from typing import Any, Generator

try:
    import psycopg2
    from psycopg2 import pool as pg_pool
except ImportError:  # pragma: no cover - fallback for test environments
    psycopg2 = None  # type: ignore[assignment]
    pg_pool = None  # type: ignore[assignment]

from app.config import get_settings

logger = logging.getLogger(__name__)

_pool: Any = None


def init_pool() -> None:
    """Initialise the connection pool. Called once at application startup."""
    global _pool
    if pg_pool is None:
        logger.warning("psycopg2 is unavailable; connection pool disabled.")
        _pool = None
        return
    settings = get_settings()
    _pool = pg_pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=20,
        dsn=settings.database_url,
    )
    logger.info("PostGIS connection pool initialised (min=2, max=20).")


def close_pool() -> None:
    """Drain the pool. Called at application shutdown."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        logger.info("PostGIS connection pool closed.")


@contextmanager
def get_conn() -> Generator[Any, None, None]:
    """
    Acquire a connection from the pool, yield it, then return it.

    Usage::

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    if _pool is None:
        raise RuntimeError("Connection pool is not initialised. Call init_pool() first.")

    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
