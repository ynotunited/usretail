# RetailIQ Design System

The RetailIQ UI is built with a premium, mobile-first, high-density philosophy. We prioritize information density over visual symmetry while maintaining an engaging "glassmorphism" aesthetic.

## 1. Core Tokens (`index.css`)

- **Primary Accent**: `--accent-blue` (`#3B82F6`) - Used for primary actions, active tabs, and highlights.
- **Status Colors**:
  - Success/High Confidence: `--accent-emerald` (`#10B981`)
  - Warning/Medium Confidence: `#FCD34D`
  - Error/Rejection: `--accent-rose` (`#F43F5E`)
- **Backgrounds**: `--bg-primary` (`#0F1115`), `--bg-secondary` (`#1A1D24`)
- **Borders**: `--border-light` (`rgba(255,255,255,0.08)`)

## 2. Component Guidelines

### Buttons
- **Primary**: `.btn-primary` (Blue gradient, glowing hover effect)
- **Secondary**: `.btn-secondary` (Dark glass background, subtle border)

### Cards & Panels
- **Glass Panels**: `.glass-panel` (Translucent background, blur effect, subtle border)
- *Do*: Use glass panels to overlay information on top of the Mapbox canvas.
- *Don't*: Stack multiple glass panels on top of one another without spatial separation.

### Typography
- Use `Inter` for standard UI text and metrics.
- Keep data tables dense (`--font-xs`, `--font-sm`).
- Use `--font-2xl` for top-level aggregate metrics.

## 3. Map Integration
- Always bind the Mapbox canvas behind the UI layers using `position: absolute; z-index: 0`.
- UI panels should float above the map, utilizing `backdrop-filter: blur(12px)`.
