"""
Reports API router.

Endpoints:
  POST /report/generate          — build executive summary (JSON + Markdown)
  GET  /report/{run_id}/csv      — export top candidate sites as CSV
  GET  /report/{run_id}/pdf      — download PDF executive summary

Report sections (per scoring-contract.md §6):
  1. Executive Summary   — city, run date, total sites scored, top-3 highlights
  2. Top 10 Sites        — rank, score, coordinates, per-factor breakdown
  3. Methodology         — formula, weights applied, data sources used
  4. Data Sources        — vintage, confidence, freshness per layer
  5. Limitations         — partial data warnings, suppressed tracts, coverage gaps
  6. Analyst Notes       — free-text from request body, overrides applied

Access: reviewer minimum.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.db.connection import get_conn
from app.auth.dependencies import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report", tags=["reports"])


class ReportRequest(BaseModel):
    run_id: str
    analyst_notes: str = ""
    top_n: int = 10


# ── POST /report/generate ──────────────────────────────────────────────────────

@router.post("/generate", summary="Generate an executive report for an analysis run")
def generate_report(
    body: ReportRequest,
    _user: dict = Depends(require_role("reviewer")),
) -> JSONResponse:
    """
    Produces a structured JSON executive report + Markdown text.
    Caller can render to HTML/PDF from the Markdown field.
    """
    try:
        report = _build_report_data(run_id=body.run_id, analyst_notes=body.analyst_notes, top_n=body.top_n)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Report generation failed for run %s: %s", body.run_id, exc)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}")

    return JSONResponse(report)


# ── GET /report/{run_id}/csv ───────────────────────────────────────────────────

@router.get("/{run_id}/csv", summary="Export top candidate sites as CSV")
def export_csv(
    run_id: str,
    limit: int = 50,
    _user: dict = Depends(require_role("reviewer")),
) -> StreamingResponse:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    rank,
                    ST_Y(geom) AS lat,
                    ST_X(geom) AS lon,
                    composite_score,
                    pop_density_score, income_score,
                    transit_score, road_score,
                    competitor_gap_score,
                    has_partial_data,
                    partial_factors
                FROM candidate_sites
                WHERE run_id = %s::uuid
                ORDER BY rank
                LIMIT %s
                """,
                (run_id, limit),
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

    if not rows:
        raise HTTPException(status_code=404, detail=f"No sites found for run '{run_id}'.")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(cols)
    for row in rows:
        writer.writerow([
            v if not isinstance(v, list) else "|".join(str(x) for x in v)
            for v in row
        ])
    output.seek(0)

    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="retailiq_sites_{run_id[:8]}.csv"'
        },
    )


# ── GET /report/{run_id}/pdf ───────────────────────────────────────────────────

@router.get("/{run_id}/pdf", summary="Download PDF executive report")
def export_pdf(
    run_id: str,
    analyst_notes: str = "",
    _user: dict = Depends(require_role("reviewer")),
) -> StreamingResponse:
    """Generates a PDF using reportlab. Returns binary PDF stream."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF generation not available (reportlab not installed).")

    try:
        report = _build_report_data(run_id=run_id, analyst_notes=analyst_notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18, spaceAfter=6)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=12, spaceAfter=4)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=14)
    note_style = ParagraphStyle("Note", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6B7280"))

    story = []

    # ── Title page ──────────────────────────────────────────────────────────
    story.append(Paragraph("RetailIQ GIS – Executive Report", title_style))
    story.append(Paragraph(f"City: {report['run']['city_name']}", body_style))
    story.append(Paragraph(f"Run ID: {run_id}", note_style))
    story.append(Paragraph(f"Generated: {report['generated_at']}", note_style))
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB")))
    story.append(Spacer(1, 0.3*cm))

    # ── Executive summary ────────────────────────────────────────────────────
    story.append(Paragraph("1. Executive Summary", h2_style))
    for line in report["executive_summary"].split("\n"):
        if line.strip():
            story.append(Paragraph(line.strip(), body_style))
    story.append(Spacer(1, 0.3*cm))

    # ── Top sites table ──────────────────────────────────────────────────────
    story.append(Paragraph(f"2. Top {len(report['top_sites'])} Candidate Sites", h2_style))
    if report["top_sites"]:
        headers = ["Rank", "Lat", "Lon", "Score", "Pop", "Income", "Transit", "Road", "Comp. Gap", "Partial"]
        data = [headers]
        for s in report["top_sites"]:
            data.append([
                str(s.get("rank", "")),
                f"{s.get('lat', 0):.4f}",
                f"{s.get('lon', 0):.4f}",
                f"{s.get('composite_score', 0):.1f}",
                f"{s.get('pop_density_score') or '–'}",
                f"{s.get('income_score') or '–'}",
                f"{s.get('transit_score') or '–'}",
                f"{s.get('road_score') or '–'}",
                f"{s.get('competitor_gap_score') or '–'}",
                "⚠" if s.get("has_partial_data") else "✓",
            ])
        tbl = Table(data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTSIZE",   (0, 0), (-1, -1), 7),
            ("GRID",       (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tbl)
    story.append(Spacer(1, 0.3*cm))

    # ── Methodology ──────────────────────────────────────────────────────────
    story.append(Paragraph("3. Methodology", h2_style))
    story.append(Paragraph(report["methodology"], body_style))
    story.append(Spacer(1, 0.3*cm))

    # ── Limitations ──────────────────────────────────────────────────────────
    story.append(Paragraph("4. Limitations", h2_style))
    story.append(Paragraph(report["limitations"], body_style))

    # ── Analyst notes ─────────────────────────────────────────────────────────
    if report.get("analyst_notes"):
        story.append(Paragraph("5. Analyst Notes", h2_style))
        story.append(Paragraph(report["analyst_notes"], body_style))

    doc.build(story)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="retailiq_report_{run_id[:8]}.pdf"'
        },
    )


# ── Report data builder (shared by JSON + PDF + Celery task) ──────────────────

def _build_report_data(
    run_id: str,
    analyst_notes: str = "",
    top_n: int = 10,
) -> dict[str, Any]:
    """Build the full report data structure from database."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Run metadata
            cur.execute(
                """
                SELECT id::text, analyst_id, city_name, run_status,
                       partial_reason, weights, dataset_snapshot,
                       started_at, completed_at
                FROM analysis_runs WHERE id = %s::uuid
                """,
                (run_id,),
            )
            run_rows = cur.fetchall()
            if not run_rows:
                raise LookupError(f"Run '{run_id}' not found.")
            run_cols = [d[0] for d in cur.description]
            run = dict(zip(run_cols, run_rows[0]))
            run["started_at"] = run["started_at"].isoformat() if run["started_at"] else None
            run["completed_at"] = run["completed_at"].isoformat() if run["completed_at"] else None
            run["id"] = str(run["id"])

            # Top sites
            cur.execute(
                """
                SELECT rank, ST_Y(geom) AS lat, ST_X(geom) AS lon,
                       composite_score, pop_density_score, income_score,
                       transit_score, road_score, competitor_gap_score,
                       has_partial_data, partial_factors
                FROM candidate_sites
                WHERE run_id = %s::uuid
                ORDER BY rank
                LIMIT %s
                """,
                (run_id, top_n),
            )
            site_cols = [d[0] for d in cur.description]
            top_sites = [dict(zip(site_cols, r)) for r in cur.fetchall()]
            for s in top_sites:
                s["lat"] = float(s["lat"]) if s["lat"] else None
                s["lon"] = float(s["lon"]) if s["lon"] else None
                for f in ["composite_score", "pop_density_score", "income_score",
                          "transit_score", "road_score", "competitor_gap_score"]:
                    s[f] = float(s[f]) if s[f] is not None else None

            # Dataset sources
            cur.execute(
                """
                SELECT source_id, name, vintage_year, confidence, freshness_status
                FROM v_datasets_with_freshness
                WHERE is_active = TRUE
                ORDER BY ingested_at DESC
                """,
            )
            ds_cols = [d[0] for d in cur.description]
            data_sources = [dict(zip(ds_cols, r)) for r in cur.fetchall()]

            # Count overrides for this run
            cur.execute(
                """
                SELECT COUNT(*) FROM analyst_overrides ao
                JOIN candidate_sites cs ON cs.id = ao.entity_id
                WHERE cs.run_id = %s::uuid
                """,
                (run_id,),
            )
            override_count = cur.fetchone()[0]

    # Partial data summary
    partial_sites = [s for s in top_sites if s.get("has_partial_data")]
    weights = run.get("weights") or {}
    if isinstance(weights, str):
        weights = json.loads(weights)

    # Build sections
    top_score = top_sites[0]["composite_score"] if top_sites else None
    exec_summary = (
        f"Analysis run for {run['city_name']} completed on {run['completed_at'] or 'N/A'}. "
        f"Status: {run['run_status']}. "
        f"{len(top_sites)} candidate sites ranked. "
        f"Top composite score: {top_score:.1f}/100. " if top_score else ""
        f"{len(partial_sites)} site(s) had partial data used in scoring. "
        f"{override_count} analyst override(s) recorded."
    )

    weight_lines = " + ".join(
        f"{k.replace('_', ' ').title()} ({v*100:.0f}%)"
        for k, v in weights.items()
    )
    methodology = (
        f"Weighted suitability formula: {weight_lines}. "
        "Population and income factors derived from U.S. Census ACS (5-year estimates). "
        "Transit accessibility and road visibility computed via PostGIS ST_Distance "
        "against OpenStreetMap transit stops and road network layers. "
        "Competitor gap calculated as inverse exponential decay from nearest OSM "
        "retail competitor (half-life 1,000 m). "
        "All factor scores normalised to 0–100 via min-max scaling across the study area. "
        "Composite score is a weighted average of all five factors."
    )

    limitations_parts = []
    if partial_sites:
        limitations_parts.append(
            f"{len(partial_sites)} site(s) had one or more factors scored using "
            "estimated/fallback values (Census suppression or missing data)."
        )
    outdated = [d for d in data_sources if d.get("freshness_status") == "outdated"]
    if outdated:
        names = ", ".join(d["source_id"] for d in outdated[:3])
        limitations_parts.append(f"Outdated data sources detected: {names}.")
    limitations_parts.append(
        "OSM data reflects the last ingestion date and may not capture very recent "
        "business openings or closures. "
        "Census ACS estimates carry margin of error — low-population tracts may be suppressed."
    )
    limitations = " ".join(limitations_parts) or "No significant limitations identified."

    return {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": run,
        "top_sites": top_sites,
        "data_sources": data_sources,
        "weights_applied": weights,
        "executive_summary": exec_summary,
        "methodology": methodology,
        "limitations": limitations,
        "analyst_notes": analyst_notes,
        "override_count": override_count,
        "partial_site_count": len(partial_sites),
        "markdown": _build_markdown(run, top_sites, weights, exec_summary, methodology, limitations, analyst_notes),
    }


def _build_markdown(run, top_sites, weights, summary, methodology, limitations, notes) -> str:
    lines = [
        f"# RetailIQ Executive Report — {run['city_name']}",
        f"> Run ID: `{run['id']}` | Status: **{run['run_status']}** | Completed: {run['completed_at'] or 'pending'}",
        "",
        "## Executive Summary",
        summary,
        "",
        "## Top Candidate Sites",
        "| Rank | Score | Lat | Lon | Pop | Income | Transit | Road | Comp. Gap | Partial |",
        "|------|-------|-----|-----|-----|--------|---------|------|-----------|---------|",
    ]
    for s in top_sites:
        lines.append(
            f"| {s['rank']} | {s['composite_score']:.1f} | {s['lat']:.4f} | {s['lon']:.4f} "
            f"| {s['pop_density_score'] or '–'} | {s['income_score'] or '–'} "
            f"| {s['transit_score'] or '–'} | {s['road_score'] or '–'} "
            f"| {s['competitor_gap_score'] or '–'} "
            f"| {'⚠️' if s['has_partial_data'] else '✓'} |"
        )
    lines += [
        "",
        "## Weights Applied",
        " | ".join(f"**{k}** {v*100:.0f}%" for k, v in weights.items()),
        "",
        "## Methodology",
        methodology,
        "",
        "## Limitations",
        limitations,
    ]
    if notes:
        lines += ["", "## Analyst Notes", notes]
    return "\n".join(lines)
