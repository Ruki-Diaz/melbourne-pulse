# Melbourne Pulse — Design System & UI/UX Specification

Generated via **UI UX Pro Max** for **Melbourne Pulse** (Live Civic Data & Predictive Analytics).

---

## 1. Product Identity & Design Archetype
- **Product Domain:** Live Civic Data / Real-time Analytics & Urban Forecasting
- **Visual Archetype:** Data-Dense Bento Grid & Dark OLED Dashboard with Glassmorphic Overlays
- **Theme:** Strict Dark Mode (deep obsidian, subtle navy undertones, high contrast data highlights)
- **Primary Accent:** Electric Teal (`#00E5C7`)
- **Secondary Accent:** Electric Blue (`#2F6BFF`)
- **Tertiary Accent:** Vivid Purple / Iris (`#7C3AED`)
- **Glow Highlight:** Mint Ice (`#D6FFF7`)
- **Canvas Base:** Obsidian Abyss (`#05080D` / `#0A0E17`)

---

## 2. Color Palette & Token Architecture

### Core Palette
| Token | Hex | Role / Usage |
|---|---|---|
| `--bg-base` | `#05080D` | Root canvas background |
| `--bg-surface` | `#0A0F1A` | Secondary surface / page sections |
| `--bg-card` | `rgba(13, 20, 36, 0.7)` | Glass card background with `backdrop-blur-md` |
| `--bg-card-hover` | `rgba(19, 30, 54, 0.85)` | Interactive card hover state |
| `--border-subtle` | `rgba(255, 255, 255, 0.08)` | Standard card/divider borders |
| `--border-accent` | `rgba(0, 229, 199, 0.3)` | Highlighted card borders |
| `--accent-teal` | `#00E5C7` | Primary data accent, active live indicators, positive surge |
| `--accent-teal-glow`| `rgba(0, 229, 199, 0.2)` | Radial glows and pulse halos |
| `--accent-blue` | `#2F6BFF` | Baseline/typical indicators, secondary metrics |
| `--accent-purple` | `#7C3AED` | Forecast models, machine learning badges |
| `--accent-amber` | `#F59E0B` | Stale data warning (>3h lag), caution |
| `--accent-emerald`| `#10B981` | Free parking bays |
| `--accent-rose` | `#F43F5E` | Occupied parking bays / high congestion |
| `--text-primary` | `#F8FAFC` | Primary headlines, metric values |
| `--text-secondary`| `#94A3B8` | Labels, metadata, timestamps |
| `--text-muted` | `#64748B` | Subtle hints, footnotes, secondary legends |

---

## 3. Typography & Hierarchy
- **Heading Font:** `Space Grotesk`, sans-serif (Clean geometric modern tech)
- **Body Font:** `DM Sans` / `Inter`, sans-serif (High legibility at 12–16px)
- **Data / Metrics Font:** `JetBrains Mono` / `Fira Code`, monospace (Tabular figures, timestamps, percentages)

### Type Scale
- **Display Hero:** `text-4xl md:text-6xl font-bold tracking-tight` (Hero title)
- **Section Heading:** `text-2xl md:text-3xl font-semibold tracking-tight`
- **Card Title / Stat Header:** `text-xs uppercase tracking-widest font-semibold text-zinc-400`
- **KPI Metric Value:** `text-3xl md:text-4xl font-bold font-mono tracking-tight`
- **Body / Summary:** `text-base md:text-lg leading-relaxed text-zinc-300`
- **Micro / Tooltips / Badges:** `text-xs font-mono`

---

## 4. Component Patterns & Visual Guidelines

### A. Glassmorphism & Depth
- Cards use `backdrop-blur-md` with `border border-white/10` and subtle inner gradient highlights.
- Ambient radial gradients (`bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))]`) bring spatial depth to dark views without visual clutter.

### B. Live Data Visualization & Sparklines
- **Sensor Pulse:** Real GPS coordinates mapped into responsive SVG; live pulsating glow for active sensors (`scale` & `opacity` keyframes).
- **Color Divergence:**
  - Teal (`#00E5C7`): Busier than typical (> +10%)
  - Neutral Gray (`#94A3B8`): Typical baseline (±10%)
  - Blue (`#2F6BFF`): Quieter than typical (< -10%)
- **Sparklines:** Clean Recharts area/line charts with gradient fills, tooltip overlays, and clean badges (`+18% busier`).

### C. Map Interface (/map)
- **CARTO Dark Matter** basemap (`dark_all`) with minimal tile saturation.
- **Sensor Layer:** Custom SVG/Canvas markers styled dynamically by current load vs typical.
- **Parking Layer:** Toggleable layer displaying micro-dots:
  - Green (`#10B981`): Free
  - Red (`#F43F5E`): Occupied
  - Grey (`#64748B`): Stale (>24h silence)
- **Interactive Sheet:** Desktop side drawer / Mobile bottom sheet for deep-dive sensor analytics.

### D. Accessibility & Interaction (a11y)
- WCAG AA contrast compliance: text contrast ratio >= 4.5:1 against card backgrounds.
- Visible focus rings (`focus-visible:ring-2 focus-visible:ring-teal-400`).
- Strict `prefers-reduced-motion` fallbacks for all animations and particle hero effects.
- Full keyboard navigation and semantic HTML landmark structure (`<main>`, `<nav>`, `<section>`, `<footer>`, `<aside>`).
