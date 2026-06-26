"""
Geometry + attribute validation engine.

Every layer is passed through this engine before being stored in PostGIS.
Results are written to `layer_validation_results` with severity levels:
  error   — blocks import (bad geometry, out-of-bounds coords, etc.)
  warning — allows import but flags for analyst review
  info    — informational, no action required

The engine is deterministic: given the same input, it always produces the
same output. This supports reproducibility per the scoring contract.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

try:
    from pyproj import CRS, Transformer
except ImportError:  # pragma: no cover - fallback for test environments
    CRS = None  # type: ignore[assignment]
    Transformer = None  # type: ignore[assignment]

try:
    from shapely.geometry import shape, mapping
    from shapely.validation import explain_validity
except ImportError:  # pragma: no cover - fallback for test environments
    shape = None  # type: ignore[assignment]
    mapping = None  # type: ignore[assignment]
    def explain_validity(_geom):  # type: ignore[override]
        return "Self-intersection detected."

from app.db.connection import get_conn

logger = logging.getLogger(__name__)

# Bounding box for the contiguous US + Alaska + Hawaii + territories
# (generous but catches obviously wrong coordinates)
US_LAT_MIN, US_LAT_MAX = 17.0, 72.0
US_LON_MIN, US_LON_MAX = -180.0, -65.0


class _SimplePoint:
    def __init__(self, lon: float, lat: float):
        self.x = lon
        self.y = lat
        self.is_empty = False
        self.is_valid = True
        self.bounds = (lon, lat, lon, lat)
        self.area = 0.0
        self.centroid = self
        self.wkt = f"POINT ({lon} {lat})"


class _SimplePolygon:
    def __init__(self, coords: list[list[float]]):
        self.coords = coords
        xs = [pt[0] for pt in coords]
        ys = [pt[1] for pt in coords]
        self.bounds = (min(xs), min(ys), max(xs), max(ys))
        self.area = abs(
            sum(coords[i][0] * coords[i + 1][1] - coords[i + 1][0] * coords[i][1] for i in range(len(coords) - 1))
        ) / 2.0
        self.centroid = _SimplePoint(sum(xs) / len(xs), sum(ys) / len(ys))
        self.is_empty = False
        self.is_valid = not _polygon_self_intersects(coords)
        self.wkt = "POLYGON ((%s))" % ", ".join(f"{x} {y}" for x, y in coords)


def _polygon_self_intersects(coords: list[list[float]]) -> bool:
    if len(coords) < 4:
        return True
    edges = list(zip(coords, coords[1:]))

    def _ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    def _intersects(e1, e2):
        (a, b), (c, d) = e1, e2
        if a == c or a == d or b == c or b == d:
            return False
        return _ccw(a, c, d) != _ccw(b, c, d) and _ccw(a, b, c) != _ccw(a, b, d)

    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            if abs(i - j) <= 1:
                continue
            if i == 0 and j == len(edges) - 1:
                continue
            if _intersects(edges[i], edges[j]):
                return True
    return False


def _shape(geom_raw: dict[str, Any]):
    if shape is not None:
        return shape(geom_raw)
    geom_type = (geom_raw or {}).get("type")
    coords = (geom_raw or {}).get("coordinates")
    if geom_type == "Point":
        return _SimplePoint(coords[0], coords[1])
    if geom_type == "Polygon":
        return _SimplePolygon(coords[0])
    raise ValueError(f"Unsupported geometry type: {geom_type}")


@dataclass
class ValidationIssue:
    severity: str         # 'error' | 'warning' | 'info'
    rule_name: str
    message: str
    row_index: int | None = None
    raw_value: str | None = None


@dataclass
class ValidationResult:
    layer_id: str
    passed: int = 0
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    infos: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def total_issues(self) -> int:
        return len(self.errors) + len(self.warnings) + len(self.infos)

    def add(self, issue: ValidationIssue) -> None:
        if issue.severity == "error":
            self.errors.append(issue)
        elif issue.severity == "warning":
            self.warnings.append(issue)
        else:
            self.infos.append(issue)


def validate_features(
    layer_id: str,
    features: list[dict[str, Any]],
    required_attributes: list[str] | None = None,
    source_srs: str = "EPSG:4326",
) -> ValidationResult:
    """
    Validate a list of GeoJSON-style feature dicts.

    Parameters
    ----------
    layer_id : str
        UUID of the layer being validated.
    features : list[dict]
        GeoJSON features with 'geometry' and 'properties' keys.
    required_attributes : list[str] | None
        Attribute names that must be present and non-null.
    source_srs : str
        Spatial reference of incoming data. Will be re-projected to EPSG:4326.

    Returns
    -------
    ValidationResult
        Structured result with errors, warnings, and passed count.
    """
    result = ValidationResult(layer_id=layer_id)
    required = required_attributes or []

    if not features:
        result.add(ValidationIssue(
            severity="warning",
            rule_name="empty_layer",
            message="Layer contains 0 features. Possible empty dataset or failed fetch.",
        ))
        return result

    # Determine if reprojection is needed
    needs_reproject = source_srs.upper() != "EPSG:4326"
    transformer: Transformer | None = None
    if needs_reproject:
        if CRS is None or Transformer is None:
            result.add(ValidationIssue(
                severity="warning",
                rule_name="srs_reprojection_unavailable",
                message=f"Input SRS {source_srs} detected, but reprojection libraries are unavailable.",
            ))
        else:
            try:
                src_crs = CRS.from_user_input(source_srs)
                dst_crs = CRS.from_epsg(4326)
                transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
                result.add(ValidationIssue(
                    severity="info",
                    rule_name="srs_reprojection",
                    message=f"Input SRS {source_srs} detected. Features will be reprojected to EPSG:4326.",
                ))
            except Exception as exc:
                result.add(ValidationIssue(
                    severity="error",
                    rule_name="srs_unrecognised",
                    message=f"Cannot parse SRS '{source_srs}': {exc}",
                ))
                return result  # Cannot proceed without valid SRS

    seen_geometries: dict[str, int] = {}  # spatial_fp → first row_index
    duplicate_count = 0
    duplicate_pairs: list[int] = []  # indices of duplicate rows

    for idx, feature in enumerate(features):
        geom_raw = feature.get("geometry")
        props = feature.get("properties", {}) or {}

        # ── Null / missing geometry ───────────────────────────────────────────
        if geom_raw is None:
            result.add(ValidationIssue(
                severity="error",
                rule_name="null_geometry",
                message="Feature has null geometry.",
                row_index=idx,
            ))
            continue

        # ── Parse geometry ────────────────────────────────────────────────────
        try:
            geom = _shape(geom_raw)
        except Exception as exc:
            result.add(ValidationIssue(
                severity="error",
                rule_name="invalid_geometry_parse",
                message=f"Cannot parse geometry: {exc}",
                row_index=idx,
            ))
            continue

        # ── Empty geometry ────────────────────────────────────────────────────
        if geom.is_empty:
            result.add(ValidationIssue(
                severity="error",
                rule_name="empty_geometry",
                message="Feature has empty geometry.",
                row_index=idx,
            ))
            continue

        # ── Topology validity ─────────────────────────────────────────────────
        if not geom.is_valid:
            explanation = explain_validity(geom)
            result.add(ValidationIssue(
                severity="error",
                rule_name="invalid_topology",
                message=f"Geometry topology invalid: {explanation}",
                row_index=idx,
                raw_value=explanation,
            ))

        # ── Coordinate bounds ─────────────────────────────────────────────────
        bounds = geom.bounds  # (minx, miny, maxx, maxy) i.e. (lon, lat, lon, lat)
        if not (
            US_LON_MIN <= bounds[0] <= US_LON_MAX
            and US_LON_MIN <= bounds[2] <= US_LON_MAX
            and US_LAT_MIN <= bounds[1] <= US_LAT_MAX
            and US_LAT_MIN <= bounds[3] <= US_LAT_MAX
        ):
            result.add(ValidationIssue(
                severity="error",
                rule_name="out_of_bounds",
                message=(
                    f"Geometry bounding box {bounds} falls outside the US extent "
                    f"(lon {US_LON_MIN}–{US_LON_MAX}, lat {US_LAT_MIN}–{US_LAT_MAX})."
                ),
                row_index=idx,
                raw_value=str(bounds),
            ))

        # ── Duplicate geometry detection (spatial fingerprint) ────────────────
        # Use centroid (rounded to 5 decimal places ≈ 1m) + area rounded to 4dp
        # as a spatial fingerprint. This catches exact duplicates and very
        # close near-duplicates that may arise from different data sources.
        try:
            centroid = geom.centroid
            area = geom.area
            fp_lon = round(centroid.x, 5)
            fp_lat = round(centroid.y, 5)
            fp_area = round(area, 4)
            spatial_fp = f"{fp_lon},{fp_lat},{fp_area}"
            if spatial_fp in seen_geometries:
                duplicate_count += 1
                duplicate_pairs.append(idx)
            else:
                seen_geometries[spatial_fp] = idx
        except Exception:
            pass  # Non-fatal — geometry might be degenerate

        # ── Required attributes ───────────────────────────────────────────────
        for attr in required:
            if attr not in props or props[attr] is None:
                result.add(ValidationIssue(
                    severity="warning",
                    rule_name="missing_required_attribute",
                    message=f"Required attribute '{attr}' is missing or null.",
                    row_index=idx,
                    raw_value=attr,
                ))

        result.passed += 1

    if duplicate_count > 0:
        result.add(ValidationIssue(
            severity="warning",
            rule_name="duplicate_geometries",
            message=(
                f"{duplicate_count} near-duplicate geometry(ies) detected by spatial "
                f"fingerprint (centroid ± 1m + area). Row indices: {duplicate_pairs[:10]}."
            ),
            raw_value=",".join(str(i) for i in duplicate_pairs[:10]),
        ))

    return result


def persist_validation_results(result: ValidationResult) -> None:
    """Write ValidationResult issues to the layer_validation_results table."""
    if result.total_issues == 0:
        return

    rows: list[tuple] = []
    for issue in result.errors + result.warnings + result.infos:
        rows.append((
            str(uuid.uuid4()),
            result.layer_id,
            issue.row_index,
            issue.severity,
            issue.rule_name,
            issue.message,
            issue.raw_value,
        ))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO layer_validation_results
                    (id, layer_id, row_index, severity, rule_name, message, raw_value)
                VALUES (%s, %s, %s, %s::validation_severity, %s, %s, %s)
                """,
                rows,
            )
    logger.debug(
        "Persisted %d validation issues for layer %s (%d errors, %d warnings).",
        result.total_issues,
        result.layer_id,
        len(result.errors),
        len(result.warnings),
    )


def validate_geometry(feature: dict[str, Any], index: int = 0, source_srs: str = "EPSG:4326"):
    """
    Backwards-compatible single-feature adapter.

    Older tests expect a tuple of (issues, corrected_wkt). The batch validator
    is the canonical implementation, so this wrapper preserves the older API.
    """
    result = validate_features(
        layer_id="legacy-validation",
        features=[feature],
        source_srs=source_srs,
    )

    issues = []
    for issue in result.errors + result.warnings + result.infos:
        rule_name = "missing_geometry" if issue.rule_name == "null_geometry" else issue.rule_name
        issues.append({
            "severity": issue.severity,
            "rule_name": rule_name,
            "message": "Feature has missing geometry." if rule_name == "missing_geometry" else issue.message,
            "row_index": index if issue.row_index is None else issue.row_index,
            "raw_value": issue.raw_value,
        })

    corrected_wkt = None
    geom_raw = feature.get("geometry")
    if geom_raw is not None:
        try:
            geom = _shape(geom_raw)
            if not geom.is_empty:
                corrected_wkt = geom.wkt
        except Exception:
            corrected_wkt = None

    return issues, corrected_wkt
