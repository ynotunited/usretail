"""
AI-augmented site narrative generator.

Generates a structured plain-English narrative for a candidate site
based on its GIS factor scores. Cites the exact source layers and values.

If an LLM API key is configured, uses the LLM (e.g. Gemini).
Otherwise, falls back to a deterministic rule-based template — always
labelled "AI-generated insight (template mode)" in the response.

Rules per scoring-contract.md section 5:
  - Insight cites which factors and layers fed it.
  - Labelled "AI-generated insight" — never presented as factual conclusion.
  - Graceful degradation if inference fails.
"""

from __future__ import annotations

import logging
from typing import Any

from app.analysis.engine import CandidateSiteResult, FactorScore

logger = logging.getLogger(__name__)


# ── Rule-based narrative template ─────────────────────────────────────────────

def _grade(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "moderate"
    if score >= 20:
        return "below average"
    return "poor"


def _nearest_label(factor_name: str, raw_value: float | None) -> str:
    """Human-readable distance or value label."""
    if raw_value is None:
        return "unknown distance"
    if factor_name in ("transit", "road", "competitor_gap"):
        if raw_value < 100:
            return f"{raw_value:.0f} m away (very close)"
        if raw_value < 500:
            return f"{raw_value:.0f} m away"
        if raw_value < 1000:
            return f"{raw_value:.0f} m away"
        return f"{raw_value / 1000:.1f} km away"
    if factor_name == "pop_density":
        return f"{raw_value:,.0f} residents (tract population)"
    if factor_name == "income":
        return f"${raw_value:,.0f} median household income"
    return str(raw_value)


def _build_strengths_weaknesses(factors: list[FactorScore]) -> tuple[list[str], list[str]]:
    strengths = []
    weaknesses = []
    labels = {
        "pop_density": "Population density",
        "income": "Income level",
        "transit": "Transit accessibility",
        "road": "Road visibility",
        "competitor_gap": "Competitor gap",
    }
    for f in factors:
        label = labels.get(f.factor, f.factor)
        grade = _grade(f.score)
        nearest = _nearest_label(f.factor, f.raw_value)
        partial_tag = " (estimated)" if f.partial else ""
        line = f"{label}: {grade} ({nearest}){partial_tag} [source: {f.data_source}]"
        if f.score is not None and f.score >= 60:
            strengths.append(line)
        else:
            weaknesses.append(line)
    return strengths, weaknesses


def generate_site_narrative(
    site: CandidateSiteResult,
    rank: int,
) -> dict[str, Any]:
    """
    Generate an AI-style narrative for a single candidate site.
    Returns a dict with keys: headline, body, factors_cited, mode.
    """
    try:
        strengths, weaknesses = _build_strengths_weaknesses(site.factors)
        composite = site.composite_score
        grade = _grade(composite)

        # Build headline
        if site.is_incomplete:
            headline = (
                f"Rank #{rank} — Incomplete scoring ({len(site.incomplete_factors)} factor(s) missing)"
            )
        elif composite and composite >= 75:
            headline = f"Rank #{rank} — High-potential site ({composite:.1f}/100)"
        elif composite and composite >= 50:
            headline = f"Rank #{rank} — Moderate-potential site ({composite:.1f}/100)"
        else:
            headline = f"Rank #{rank} — Lower-priority site ({composite:.1f}/100 composite score)"

        # Build body
        body_parts = []
        if strengths:
            body_parts.append("**Strengths:** " + "; ".join(strengths) + ".")
        if weaknesses:
            body_parts.append("**Concerns:** " + "; ".join(weaknesses) + ".")
        if site.has_partial_data:
            flagged = ", ".join(site.partial_factors)
            body_parts.append(
                f"⚠️ **Partial data used** for: {flagged}. "
                "Estimated values substitute for suppressed or missing Census records."
            )
        if site.is_incomplete:
            missing = ", ".join(site.incomplete_factors)
            body_parts.append(
                f"**Incomplete:** Factor(s) {missing} could not be scored. "
                "Site placed in 'Needs review' tier."
            )

        body = " ".join(body_parts) or "No significant factors to report."

        return {
            "headline": headline,
            "body": body,
            "composite_score": composite,
            "mode": "template",
            "label": "AI-generated insight (template mode)",
            "factors_cited": [f.factor for f in site.factors],
            "sources_cited": list({f.data_source for f in site.factors}),
        }

    except Exception as exc:
        logger.warning("Narrative generation failed for site %s: %s", site.site_id, exc)
        return {
            "headline": f"Rank #{rank} — Insight unavailable",
            "body": "Insight unavailable due to an internal error.",
            "composite_score": site.composite_score,
            "mode": "error",
            "label": "Insight unavailable",
            "factors_cited": [],
            "sources_cited": [],
        }
