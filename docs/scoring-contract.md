# Scoring Contract
## RetailIQ GIS – Suitability Score Transparency & Reproducibility Rules

> This document defines the non-negotiable rules for how suitability scores are
> calculated, exposed, audited, and overridden. No score may be presented to an
> analyst without satisfying every rule in this contract.

---

## 1. The Suitability Score Formula

### 1.1 Weighted Composite Score

```
Suitability Score =
  (Population Density Score  × 0.30)
+ (Income Level Score        × 0.25)
+ (Transit Access Score      × 0.15)
+ (Road Access Score         × 0.15)
+ (Competitor Gap Score      × 0.15)
```

All individual factor scores are normalized to a **0–100 scale** before weighting.
The composite score is also expressed on a **0–100 scale**.

### 1.2 Factor Definitions

| Factor | Source Layer(s) | Normalization Method |
|---|---|---|
| **Population Density** | Census ACS – population by tract | Min-max normalization across city extent |
| **Income Level** | Census ACS – median household income by tract | Min-max normalization |
| **Transit Access** | GTFS stops + OSM transit | Inverse distance to nearest stop (0–1 km decay) |
| **Road Access** | OSM road network | Proximity to arterials (0–500 m decay) |
| **Competitor Gap** | OSM + Commercial POI competitor locations | Inverse kernel density (high gap = high score) |

---

## 2. Transparency Rules

### 2.1 Always Expose Factor Scores
Every candidate site presented to an analyst **must** display:
- Composite score (0–100)
- Individual factor score for each of the 5 factors (0–100 each)
- Weight applied to each factor (% value)
- Data source used for each factor (source ID from data source registry)
- Data confidence level per factor (High / Medium / Low)
- Any factors that used **estimated or partial data** (flagged with ⚠️)

**No score may be shown without its full factor breakdown visible one tap/click away.**

### 2.2 Partial Data Disclosure
If a factor score was computed using incomplete data:
- The factor score cell shows a ⚠️ badge.
- Tooltip/popover explains what data was missing and how the gap was handled (e.g., "Transit score estimated from OSM stops; GTFS data unavailable for this zone").
- The composite score shows a "Partial data used" label.

If a required factor cannot be scored at all:
- That factor score is shown as `—` (not 0).
- The composite score is flagged as **"Incomplete – N factor(s) unscored"**.
- The site is placed in a separate "Needs review" tier, not ranked with fully-scored sites.

### 2.3 Weight Transparency
- Default weights are shown on the analysis configuration screen before running.
- If an analyst has overridden weights, the custom weights are shown on every score card.
- A badge "Custom weights applied" appears on the score and in the run metadata.

---

## 3. Reproducibility Rules

### 3.1 Analysis Run Snapshot
Every analysis run **must** store at the time of execution:
- Unique `run_id` (UUID)
- `analyst_id` who initiated the run
- Timestamp (`run_at`, UTC)
- City / study area boundary used
- List of dataset versions used (source_id + ingested_at timestamp per layer)
- Factor weights applied (default or custom)
- Any analyst overrides active at run time
- Run status: `complete`, `partial`, `failed`

### 3.2 Reproducible Re-Run
Given a historical `run_id`, the system must be able to:
- Retrieve the exact input dataset snapshot used
- Re-execute the analysis with the same weights and parameters
- Produce the same output (within floating-point tolerance)

Layer data is **never deleted** if referenced by a completed analysis run.
Layers may be archived (read-only), but the data must be queryable for re-runs.

### 3.3 Run Comparison
The system must support comparing two runs side by side:
- Show sites present in both runs with score delta
- Show sites that appeared or disappeared between runs
- Show factor score changes with direction indicator (↑ / ↓)
- Show weight changes if applicable

---

## 4. Analyst Override Rules

### 4.1 What Can Be Overridden
Analysts may override:
- The recommendation status of a site (e.g., reject a high-scoring site due to zoning)
- The weight of any factor (within a single analysis run or as a saved configuration)
- The data source used for a specific factor (e.g., use user shapefile instead of OSM)

### 4.2 What Cannot Be Silently Changed
- The formula itself cannot be changed without a decision log entry.
- An override cannot hide the original automated score — both must be visible.
- An override cannot remove a data quality warning from a factor.

### 4.3 Override Audit Log
Every override is stored with:
- `override_id` (UUID)
- `run_id` referenced
- `site_id` or `factor_id` affected
- `analyst_id` who made the override
- `original_value` (system-generated)
- `override_value` (analyst-set)
- `reason` (free text, required)
- `created_at` (UTC timestamp)

Override log is queryable per site, per run, per analyst, and per date range.

---

## 5. AI Insight Rules

When AI-generated insights are presented alongside scores:

- The insight must cite which factors and layers fed it.
- The insight is labelled "AI-generated insight" — never presented as a factual conclusion.
- The analyst may annotate or reject the insight; that action is logged.
- AI insights are never used as a factor input to the suitability score formula.
- If the AI inference call fails, the site card is shown without the insight (graceful degradation), with a "Insight unavailable" label.

---

## 6. Score Display Contract

| UI Element | Required? | Notes |
|---|---|---|
| Composite score (0–100) | ✅ Yes | Always visible on site card |
| Factor breakdown | ✅ Yes | Visible one tap/click from site card |
| Weights applied | ✅ Yes | Shown in factor breakdown |
| Data source per factor | ✅ Yes | Shown in factor breakdown |
| Confidence level per factor | ✅ Yes | Shown in factor breakdown |
| Partial data warning | ✅ Yes | Shown inline if applicable |
| Override badge | ✅ Yes | Shown if analyst override exists |
| Run ID reference | ✅ Yes | Accessible from site detail |
| AI insight | ⚠️ Conditional | Shown only if inference succeeded |
| Analyst notes | ⚠️ Conditional | Shown only if notes exist |

---

## 7. Versioning

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-06-26 | Initial scoring contract |

Changes to the formula or factor definitions require:
1. A new version entry in this table.
2. A decision log entry in `docs/decision-log.md`.
3. Existing analysis runs retain the formula version used at run time.

---

*Last updated: 2026-06-26 | Status: ACTIVE*
