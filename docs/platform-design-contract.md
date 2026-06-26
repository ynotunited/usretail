# Platform Design Contract
## RetailIQ GIS – U.S. Retail Site Selection Platform

> This document defines the non-negotiable design and engineering standards for the RetailIQ GIS platform.
> All contributors — designers, engineers, and AI agents — must follow these rules.
> Deviations require an explicit decision log entry.

---

## 1. What This Platform Is

RetailIQ GIS is a **production geospatial intelligence platform** used by:

- Retail Expansion Managers evaluating new store locations
- Real Estate Analysts assessing investment opportunities
- Franchise Operators targeting high-density, low-competition markets
- Location Intelligence Specialists performing multi-factor site scoring

It is **not** a portfolio demo. It is **not** a marketing landing page.
It must feel like software that a real team has been logging into every weekday for two years.

---

## 2. Interface Standards

### 2.1 No Generic Templates
- Do not use pre-built dashboard UI kits or AI-generated layout scaffolding.
- Every layout must emerge from an actual analyst workflow, not from a template library.
- If a layout looks like it belongs in a SaaS landing page screenshot, it is wrong.

### 2.2 Information Density Over Visual Symmetry
- Layouts are allowed — expected — to be asymmetric when the data demands it.
- Whitespace is earned, not decorative. Dense tables, inline metadata, and stacked panels are appropriate.
- A screen with a map, a data table, filter controls, and a status bar at the same time is correct.

### 2.3 Every Screen Supports a Business Decision
Every screen in the application must answer one of the following questions for the analyst:

| Screen Purpose | Business Decision Supported |
|---|---|
| Map Explorer | Where are the opportunity zones on the map? |
| Candidate Sites List | Which sites rank highest and why? |
| Site Detail Panel | Should I recommend this specific location? |
| Data Imports & Validation | Is this dataset reliable enough to use? |
| Analysis Runs | Has the analysis changed since the last run? |
| Executive Report | What do I present to leadership? |

If a screen cannot be mapped to a business decision, it should not exist.

### 2.4 Actively-Used Aesthetic
- The product should look like it has been used. Realistic data states, not all-green dashboards.
- Show data quality warnings, partial results, and outdated source badges as normal UI states.
- No fake testimonials, stock avatars, or placeholder copy ("John D., Senior Analyst").
- No marketing language in the UI copy. Prefer operational language.

  **Wrong**: "Unlock powerful geospatial insights"
  **Right**: "3 of 6 analysis factors scored. Missing: transit data, road network."

---

## 3. Mobile-First Rules

### 3.1 Breakpoints
| Viewport | Layout Mode |
|---|---|
| ≤ 480 px (small mobile) | Full-screen map, bottom sheet for all controls |
| 481–768 px (large mobile) | Full-screen map, collapsible bottom panel (40 vh) |
| 769–1024 px (tablet) | Map 60% left, sidebar 40% right, collapsed top nav |
| ≥ 1025 px (desktop) | Map 65% left, sidebar 35% right, full nav |

### 3.2 Touch-First Interaction
- Tap targets: minimum 44×44 px on all interactive elements.
- No hover-only states on maps or panels — use tap/long-press.
- Tooltips and popovers are triggered by tap, not hover.
- Pinch-to-zoom and drag on map are native Leaflet gestures — do not override them.

### 3.3 Navigation Pattern
- Mobile: sticky bottom navigation bar (max 5 items), tab-style.
- Desktop: left sidebar navigation (collapsible to icon-only mode).
- No hamburger menus on desktop.
- Active state is visually unambiguous at a glance.

### 3.4 Performance on Mobile
- Map tiles: lazy-loaded, with tile-load timeout handling and fallback source.
- Analysis overlays: streamed progressively — do not wait for full dataset before rendering.
- Skeleton screens for all data-driven panels; never show empty white boxes.
- Target Lighthouse mobile score: **90+**.

---

## 4. Component Rules

### 4.1 Design Tokens (to be implemented in `tokens.css`)
All visual values must reference named tokens. Ad-hoc values are not permitted.

| Token Category | Max Variants |
|---|---|
| Colors | 1 primary, 1 accent, 3 neutrals, 3 semantic (danger, warn, success) |
| Border Radius | 3 values: `sm` (4px), `md` (8px), `lg` (16px) |
| Spacing | 8-point grid: 4, 8, 12, 16, 24, 32, 48, 64 px |
| Font Weights | 3 values: regular (400), medium (500), semibold (600) |
| Shadow | 2 levels: `card` (subtle), `modal` (elevated) |

### 4.2 Hover & Interaction States
- Hover lift: max 2–4 px `translateY`. No glowing shadows.
- Transitions: cubic-bezier easing only. No linear or ease-in-out defaults.
  - Default: `cubic-bezier(0.4, 0, 0.2, 1)` (Material standard, production-proven)
- Active states: immediate feedback (< 100 ms).

### 4.3 Consistent Placement
- Component placement must be identical across equivalent screens.
- The filter panel is always in the same position. The score breakdown always uses the same layout.
- Do not redesign a component because a screen has more or less data.

### 4.4 No Decorative-Only Elements
- No sparkles, emoji in headings, or animated background gradients.
- No icons that are not linked to an action or a meaning.
- Remove all non-functional social icons.

---

## 5. Copy & Labeling Standards

- Use operational, precise language. Analysts are not customers to be marketed to.
- No em-dash overuse. One em-dash per sentence maximum.
- No vague phrases: "powerful", "seamless", "next-generation", "unlock".
- Data quality labels must be specific: "Census 2020 – 4 years old" not "Data may be outdated".
- Error messages must say what failed and what to do next.

  **Wrong**: "An error occurred."
  **Right**: "Geocoding failed for 14 addresses. Download the error report or correct manually."

---

## 6. What Requires a Decision Log Entry

Any deviation from this contract requires a recorded decision:

- Adding a screen that does not map to a business decision
- Using an ad-hoc color or spacing value not in the design token set
- Using a UI kit component as-is without adaptation
- Hiding a data quality issue from the analyst view
- Changing the suitability scoring formula without updating the scoring contract

Decision log file: `docs/decision-log.md`

---

*Last updated: 2026-06-26 | Status: ACTIVE*
