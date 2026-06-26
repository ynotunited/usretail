"""
Core GIS scoring engine.

Implements the weighted suitability score formula:
  Score = (Pop Density × 0.30) + (Income × 0.25) + (Transit × 0.15)
        + (Road × 0.15) + (Competitor Gap × 0.15)

All factor scores are normalized to 0–100 before weighting.
Missing/suppressed data is flagged with ⚠️ (has_partial_data = True).

PostGIS spatial queries are used for:
  - Census tract containment (ST_Contains)
  - Nearest transit stop distance (ST_Distance on geography)
  - Nearest road distance (ST_Distance on geography)
  - Nearest competitor distance (ST_Distance on geography)
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.db.connection import get_conn

logger = logging.getLogger(__name__)

# ── Default formula weights ────────────────────────────────────────────────────

DEFAULT_WEIGHTS: dict[str, float] = {
    "pop_density": 0.30,
    "income":      0.25,
    "transit":     0.15,
    "road":        0.15,
    "competitor_gap": 0.15,
}


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class FactorScore:
    """A single factor's score with transparency metadata."""
    factor: str
    score: float | None          # 0–100, or None if uncomputable
    raw_value: float | None      # raw physical value (e.g. density in persons/km²)
    data_source: str
    confidence: str              # high / medium / low / unknown
    partial: bool = False        # True if estimated/fallback used
    partial_reason: str | None = None


@dataclass
class CandidateSiteResult:
    """Scored suitability result for a single candidate point."""
    site_id: str
    lon: float
    lat: float
    composite_score: float | None
    factors: list[FactorScore]
    has_partial_data: bool
    partial_factors: list[str]
    weights: dict[str, float]
    is_incomplete: bool = False    # True if ≥1 factor is None
    incomplete_factors: list[str] = field(default_factory=list)


@dataclass
class AnalysisRunResult:
    """Summary of a complete analysis run."""
    run_id: str
    status: str
    sites: list[CandidateSiteResult]
    dataset_snapshot: dict[str, Any]
    weights: dict[str, float]
    analyst_id: str
    city_name: str
    started_at: datetime
    completed_at: datetime | None = None
    partial_reason: str | None = None


# ── Candidate site generation ─────────────────────────────────────────────────

def generate_candidate_sites(max_sites: int = 50) -> list[tuple[float, float]]:
    """
    Generate candidate retail site points from PostGIS.

    Sources:
      1. Centroids of office/commercial building footprints (OSM offices layer)
      2. Centroids of shopping centres layer
    Returns a list of (lon, lat) tuples, deduplicated, limited to max_sites.
    """
    candidates: list[tuple[float, float]] = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Get centroids of office buildings and shopping centres
            cur.execute(
                """
                SELECT DISTINCT
                    ST_X(ST_Centroid(geom)) AS lon,
                    ST_Y(ST_Centroid(geom)) AS lat
                FROM layer_features lf
                JOIN layers l ON l.id = lf.layer_id
                JOIN datasets d ON d.id = l.dataset_id
                WHERE d.source_id = 'osm'
                  AND l.name IN ('offices', 'shopping_centres')
                  AND l.import_status = 'imported'
                  AND geom IS NOT NULL
                ORDER BY lon, lat
                LIMIT %s
                """,
                (max_sites,),
            )
            rows = cur.fetchall()

    if rows:
        candidates = [(row[0], row[1]) for row in rows if row[0] and row[1]]

    # Fallback: if no OSM data found, use a grid over Austin core
    if not candidates:
        logger.warning("No OSM office/shopping features found; using fallback candidate grid.")
        # 5×5 grid over Austin downtown core area
        lat_range = [30.20, 30.30]
        lon_range = [-97.82, -97.72]
        steps = 5
        lat_step = (lat_range[1] - lat_range[0]) / steps
        lon_step = (lon_range[1] - lon_range[0]) / steps
        for i in range(steps):
            for j in range(steps):
                candidates.append((
                    lon_range[0] + j * lon_step,
                    lat_range[0] + i * lat_step,
                ))
        candidates = candidates[:max_sites]

    logger.info("Generated %d candidate sites.", len(candidates))
    return candidates


# ── Factor scoring ────────────────────────────────────────────────────────────

def _get_census_stats(cur) -> dict[str, float]:
    """
    Return county-wide min/max for population and income
    to support min-max normalization.
    """
    cur.execute(
        """
        SELECT
            MIN((lf.attributes->>'total_population')::float) AS pop_min,
            MAX((lf.attributes->>'total_population')::float) AS pop_max,
            MIN((lf.attributes->>'median_household_income')::float) AS income_min,
            MAX((lf.attributes->>'median_household_income')::float) AS income_max,
            AVG((lf.attributes->>'total_population')::float) AS pop_avg,
            AVG((lf.attributes->>'median_household_income')::float) AS income_avg
        FROM layer_features lf
        JOIN layers l ON l.id = lf.layer_id
        JOIN datasets d ON d.id = l.dataset_id
        WHERE d.source_id = 'census-acs'
          AND l.import_status = 'imported'
          AND (lf.attributes->>'total_population') IS NOT NULL
          AND (lf.attributes->>'total_population') != 'null'
        """
    )
    row = cur.fetchone()
    if row:
        return {
            "pop_min":    row[0] or 0.0,
            "pop_max":    row[1] or 10000.0,
            "income_min": row[2] or 0.0,
            "income_max": row[3] or 250000.0,
            "pop_avg":    row[4] or 4000.0,
            "income_avg": row[5] or 75000.0,
        }
    return {
        "pop_min": 0.0, "pop_max": 10000.0,
        "income_min": 0.0, "income_max": 250000.0,
        "pop_avg": 4000.0, "income_avg": 75000.0,
    }


def score_population_density(
    lon: float, lat: float, cur, stats: dict
) -> FactorScore:
    """
    Score population density for a candidate point.
    Finds the census tract containing the point and applies min-max normalization.
    """
    cur.execute(
        """
        SELECT
            (lf.attributes->>'total_population')::float AS pop,
            (lf.attributes->>'total_population_suppressed')::boolean AS suppressed,
            d.confidence
        FROM layer_features lf
        JOIN layers l ON l.id = lf.layer_id
        JOIN datasets d ON d.id = l.dataset_id
        WHERE d.source_id = 'census-acs'
          AND l.import_status = 'imported'
          AND ST_Contains(lf.geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
        LIMIT 1
        """,
        (lon, lat),
    )
    row = cur.fetchone()

    if not row or row[0] is None or row[2] is None:
        # Point falls outside all tracts (e.g. lake, boundary edge) — use county avg
        s = _normalize(stats["pop_avg"], stats["pop_min"], stats["pop_max"])
        return FactorScore(
            factor="pop_density", score=round(s, 2), raw_value=round(stats["pop_avg"], 0),
            data_source="census-acs", confidence="low",
            partial=True, partial_reason="Point falls outside all census tracts; county average used."
        )

    pop, suppressed, confidence = row[0], row[1], row[2]

    if suppressed or pop is None:
        # Use county average for suppressed tracts
        s = _normalize(stats["pop_avg"], stats["pop_min"], stats["pop_max"])
        return FactorScore(
            factor="pop_density", score=round(s, 2), raw_value=round(stats["pop_avg"], 0),
            data_source="census-acs", confidence="medium",
            partial=True, partial_reason="Tract population suppressed by Census; county average used."
        )

    # Use tract population as density proxy (min-max normalized across all county tracts)
    s = _normalize(pop, stats["pop_min"], stats["pop_max"])
    return FactorScore(
        factor="pop_density", score=round(s, 2), raw_value=round(pop, 0),
        data_source="census-acs", confidence=confidence, partial=False,
    )


def score_income(
    lon: float, lat: float, cur, stats: dict
) -> FactorScore:
    """
    Score income level for a candidate point using min-max normalization
    of median household income from the containing census tract.
    """
    cur.execute(
        """
        SELECT
            (lf.attributes->>'median_household_income')::float AS income,
            (lf.attributes->>'median_household_income_suppressed')::boolean AS suppressed,
            d.confidence
        FROM layer_features lf
        JOIN layers l ON l.id = lf.layer_id
        JOIN datasets d ON d.id = l.dataset_id
        WHERE d.source_id = 'census-acs'
          AND l.import_status = 'imported'
          AND ST_Contains(lf.geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
        LIMIT 1
        """,
        (lon, lat),
    )
    row = cur.fetchone()

    if not row or row[0] is None:
        s = _normalize(stats["income_avg"], stats["income_min"], stats["income_max"])
        return FactorScore(
            factor="income", score=round(s, 2), raw_value=round(stats["income_avg"], 0),
            data_source="census-acs", confidence="low",
            partial=True, partial_reason="Point outside all census tracts; county average income used."
        )

    income, suppressed, confidence = row[0], row[1], row[2]

    if suppressed or income is None:
        s = _normalize(stats["income_avg"], stats["income_min"], stats["income_max"])
        return FactorScore(
            factor="income", score=round(s, 2), raw_value=round(stats["income_avg"], 0),
            data_source="census-acs", confidence="medium",
            partial=True, partial_reason="Tract income suppressed by Census; county average used."
        )

    s = _normalize(income, stats["income_min"], stats["income_max"])
    return FactorScore(
        factor="income", score=round(s, 2), raw_value=round(income, 0),
        data_source="census-acs", confidence=confidence, partial=False,
    )


def score_transit(lon: float, lat: float, cur) -> FactorScore:
    """
    Score transit accessibility using inverse exponential decay from
    nearest transit stop. Score = 100 × exp(-distance_m / 300).
    """
    cur.execute(
        """
        SELECT
            ST_Distance(
                lf.geom::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            ) AS dist_m
        FROM layer_features lf
        JOIN layers l ON l.id = lf.layer_id
        JOIN datasets d ON d.id = l.dataset_id
        WHERE d.source_id = 'osm'
          AND l.name = 'transit_stops'
          AND l.import_status = 'imported'
        ORDER BY dist_m
        LIMIT 1
        """,
        (lon, lat),
    )
    row = cur.fetchone()

    if not row:
        return FactorScore(
            factor="transit", score=None, raw_value=None,
            data_source="osm", confidence="unknown",
            partial=True, partial_reason="No transit stop data available."
        )

    dist_m = row[0]
    s = 100.0 * math.exp(-dist_m / 300.0)
    return FactorScore(
        factor="transit", score=round(s, 2), raw_value=round(dist_m, 1),
        data_source="osm", confidence="high", partial=False,
    )


def score_road(lon: float, lat: float, cur) -> FactorScore:
    """
    Score road visibility using inverse exponential decay from
    nearest arterial road. Score = 100 × exp(-distance_m / 150).
    """
    cur.execute(
        """
        SELECT
            ST_Distance(
                lf.geom::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            ) AS dist_m
        FROM layer_features lf
        JOIN layers l ON l.id = lf.layer_id
        JOIN datasets d ON d.id = l.dataset_id
        WHERE d.source_id = 'osm'
          AND l.name = 'roads'
          AND l.import_status = 'imported'
        ORDER BY dist_m
        LIMIT 1
        """,
        (lon, lat),
    )
    row = cur.fetchone()

    if not row:
        return FactorScore(
            factor="road", score=None, raw_value=None,
            data_source="osm", confidence="unknown",
            partial=True, partial_reason="No road data available."
        )

    dist_m = row[0]
    s = 100.0 * math.exp(-dist_m / 150.0)
    return FactorScore(
        factor="road", score=round(s, 2), raw_value=round(dist_m, 1),
        data_source="osm", confidence="high", partial=False,
    )


def score_competitor_gap(lon: float, lat: float, cur) -> FactorScore:
    """
    Score competitor gap using inverse exponential decay: farther from competitors = higher score.
    Score = 100 × (1 - exp(-distance_m / 1000)).
    """
    cur.execute(
        """
        SELECT
            ST_Distance(
                lf.geom::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            ) AS dist_m
        FROM layer_features lf
        JOIN layers l ON l.id = lf.layer_id
        JOIN datasets d ON d.id = l.dataset_id
        WHERE d.source_id = 'osm'
          AND l.name = 'competitors'
          AND l.import_status = 'imported'
        ORDER BY dist_m
        LIMIT 1
        """,
        (lon, lat),
    )
    row = cur.fetchone()

    if not row:
        return FactorScore(
            factor="competitor_gap", score=50.0, raw_value=None,
            data_source="osm", confidence="medium",
            partial=True, partial_reason="No competitor data found; neutral score (50) applied."
        )

    dist_m = row[0]
    s = 100.0 * (1.0 - math.exp(-dist_m / 1000.0))
    return FactorScore(
        factor="competitor_gap", score=round(s, 2), raw_value=round(dist_m, 1),
        data_source="osm", confidence="medium", partial=False,
    )


# ── Weighted composite calculator ──────────────────────────────────────────────

def compute_composite(
    factors: list[FactorScore],
    weights: dict[str, float],
) -> tuple[float | None, bool, list[str]]:
    """
    Compute weighted composite score.
    Returns (composite, has_partial, incomplete_factors).
    """
    factor_map = {f.factor: f for f in factors}
    weighted_sum = 0.0
    total_weight = 0.0
    partial = False
    incomplete = []

    for factor_name, weight in weights.items():
        fs = factor_map.get(factor_name)
        if fs is None or fs.score is None:
            incomplete.append(factor_name)
            continue
        weighted_sum += fs.score * weight
        total_weight += weight
        if fs.partial:
            partial = True

    if total_weight == 0.0:
        return None, partial, incomplete

    # Rescale to 0–100 if any factor was missing
    composite = weighted_sum / total_weight * 100.0 / 100.0
    return round(composite, 2), partial, incomplete


def calculate_composite(
    factors: list[FactorScore],
    weights: dict[str, float],
) -> tuple[float | None, bool, list[str]]:
    """
    Backwards-compatible alias for legacy callers and tests.
    """
    factor_map = {f.factor: f for f in factors}
    weighted_sum = 0.0
    total_weight = 0.0
    partial_factors: list[str] = []

    for factor_name, fs in factor_map.items():
        if factor_name not in weights:
            partial_factors.append(factor_name)
            continue
        if fs.score is None:
            partial_factors.append(factor_name)
            continue
        weight = weights[factor_name]
        weighted_sum += fs.score * weight
        total_weight += weight
        if fs.partial:
            partial_factors.append(factor_name)

    for factor_name in weights:
        if factor_name not in factor_map:
            partial_factors.append(factor_name)

    if total_weight == 0.0 or any(f.score is None for f in factors):
        return None, any(f.partial for f in factors), partial_factors

    return round(weighted_sum, 2), any(f.partial for f in factors), partial_factors


# ── Full scoring for one site ─────────────────────────────────────────────────

def score_site(
    lon: float, lat: float,
    weights: dict[str, float],
    cur, stats: dict,
) -> CandidateSiteResult:
    """Compute all 5 factor scores and composite for a single candidate site."""
    site_id = str(uuid.uuid4())

    factors = [
        score_population_density(lon, lat, cur, stats),
        score_income(lon, lat, cur, stats),
        score_transit(lon, lat, cur),
        score_road(lon, lat, cur),
        score_competitor_gap(lon, lat, cur),
    ]

    composite, has_partial, incomplete = compute_composite(factors, weights)
    partial_factors = [f.factor for f in factors if f.partial]

    return CandidateSiteResult(
        site_id=site_id,
        lon=lon,
        lat=lat,
        composite_score=composite,
        factors=factors,
        has_partial_data=has_partial,
        partial_factors=partial_factors,
        weights=weights,
        is_incomplete=bool(incomplete),
        incomplete_factors=incomplete,
    )


# ── Dataset snapshot helper ───────────────────────────────────────────────────

def get_dataset_snapshot() -> dict[str, Any]:
    """Returns the currently active datasets and their ingestion timestamps."""
    snapshot: dict[str, Any] = {}
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.source_id, d.id::text, d.ingested_at
                FROM datasets d
                WHERE d.is_active = TRUE
                ORDER BY d.ingested_at DESC
                """
            )
            for row in cur.fetchall():
                source_id, dataset_id, ingested_at = row
                if source_id not in snapshot:
                    snapshot[source_id] = {
                        "dataset_id": dataset_id,
                        "ingested_at": ingested_at.isoformat() if ingested_at else None,
                    }
    return snapshot


# ── Full run orchestrator ──────────────────────────────────────────────────────

def run_analysis(
    city_name: str,
    weights: dict[str, float],
    analyst_id: str,
    max_sites: int = 50,
) -> AnalysisRunResult:
    """
    Full suitability analysis pipeline:
    1. Register run in database.
    2. Generate candidate sites.
    3. Score each site.
    4. Persist results to candidate_sites.
    5. Update run status.
    Returns the full AnalysisRunResult.
    """
    settings = get_settings()
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    # 1. Register run
    snapshot = get_dataset_snapshot()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analysis_runs (
                    id, analyst_id, city_name, weights, dataset_snapshot, run_status, started_at
                ) VALUES (%s, %s, %s, %s, %s, 'running', %s)
                """,
                (
                    run_id, analyst_id, city_name,
                    json.dumps(weights), json.dumps(snapshot),
                    started_at,
                ),
            )
    logger.info("Analysis run %s registered.", run_id)

    # 2. Generate candidates
    candidates = generate_candidate_sites(max_sites=max_sites)

    # 3. Score all sites (one connection / cursor)
    scored_sites: list[CandidateSiteResult] = []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                stats = _get_census_stats(cur)
                for lon, lat in candidates:
                    try:
                        result = score_site(lon, lat, weights, cur, stats)
                        scored_sites.append(result)
                    except Exception as exc:
                        logger.warning("Skipping candidate (%.4f, %.4f): %s", lon, lat, exc)

        # 4. Sort by composite score descending
        scored_sites.sort(
            key=lambda s: s.composite_score if s.composite_score is not None else -1,
            reverse=True,
        )
        for rank_idx, site in enumerate(scored_sites, start=1):
            _persist_site(site, run_id, rank=rank_idx)

        # 5. Update run status
        completed_at = datetime.now(timezone.utc)
        partial_count = sum(1 for s in scored_sites if s.is_incomplete)
        status = "partial" if partial_count > 0 and partial_count == len(scored_sites) else "complete"
        partial_reason = (
            f"{partial_count} of {len(scored_sites)} sites had incomplete factor data."
            if partial_count else None
        )

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE analysis_runs
                    SET run_status = %s::run_status,
                        completed_at = %s,
                        partial_reason = %s
                    WHERE id = %s
                    """,
                    (status, completed_at, partial_reason, run_id),
                )

        logger.info(
            "Analysis run %s complete: %d sites scored, status=%s.",
            run_id, len(scored_sites), status,
        )
        return AnalysisRunResult(
            run_id=run_id,
            status=status,
            sites=scored_sites,
            dataset_snapshot=snapshot,
            weights=weights,
            analyst_id=analyst_id,
            city_name=city_name,
            started_at=started_at,
            completed_at=completed_at,
            partial_reason=partial_reason,
        )

    except Exception as exc:
        logger.exception("Analysis run %s failed: %s", run_id, exc)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE analysis_runs SET run_status = 'failed', error_message = %s WHERE id = %s",
                    (str(exc), run_id),
                )
        raise


def _persist_site(site: CandidateSiteResult, run_id: str, rank: int) -> None:
    """Write a CandidateSiteResult to the candidate_sites table."""
    factor_map = {f.factor: f for f in site.factors}

    def score_or_none(name: str) -> float | None:
        f = factor_map.get(name)
        return f.score if f else None

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO candidate_sites (
                    id, run_id, rank, geom,
                    composite_score, pop_density_score, income_score,
                    transit_score, road_score, competitor_gap_score,
                    has_partial_data, partial_factors, data_sources, attributes
                ) VALUES (
                    %s, %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                """,
                (
                    site.site_id, run_id, rank,
                    site.lon, site.lat,
                    site.composite_score,
                    score_or_none("pop_density"),
                    score_or_none("income"),
                    score_or_none("transit"),
                    score_or_none("road"),
                    score_or_none("competitor_gap"),
                    site.has_partial_data,
                    site.partial_factors,
                    json.dumps({f.factor: f.data_source for f in site.factors}),
                    json.dumps({
                        "weights": site.weights,
                        "incomplete_factors": site.incomplete_factors,
                        "factor_details": [
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
                    }),
                ),
            )


# ── Utilities ──────────────────────────────────────────────────────────────────

def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalize value to 0–100 scale. Clamps output to [0, 100]."""
    if max_val == min_val:
        return 50.0
    s = (value - min_val) / (max_val - min_val) * 100.0
    return round(min(100.0, max(0.0, s)), 2)
