# Design: Bluntly.ph

> **Materialized from** [`docs/frontend/dsd-bluntly-fe.md`](docs/frontend/dsd-bluntly-fe.md).
> **Edit the DSD; re-materialize.** Do not treat this file as the source of truth. Reference
> **token names**, not raw hex, in components.

**System name:** Bluntly Foundation
**Version:** 0.1 (matches DSD)
**Last materialized:** 2026-07-20

---

## 1. Foundations; Token tiers

| Tier | Purpose | Example |
|------|---------|---------|
| Primitive | Raw value | `--orange-500: #EF782D` |
| Semantic | Meaning | `--color-primary: var(--orange-500)` |
| Component | Scoped | `--button-bg: var(--color-primary)` |

Implemented as Tailwind v4 `@theme` tokens in `app/globals.css`.

### Color (semantic)

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg` | `#FFFFFF` / dark `#141414` | Page background (app / landing) |
| `--color-surface` | `#F2F2F2` | Cards, sheets |
| `--color-border` | `rgba(32,32,32,0.30)` | Borders, dividers |
| `--color-primary` | `#EF782D` | Primary action, brand accent |
| `--color-primary-hover` | `#96371A` | Hover/pressed; orange text on light |
| `--color-primary-tint` | `#FFC596` | Highlights, gradient top |
| `--color-text` | `#202020` | Body |
| `--color-text-muted` | `rgba(32,32,32,0.70)` | Secondary |
| `--color-text-disabled` | `rgba(32,32,32,0.52)` | Disabled |
| `--color-success` | `#2E9E5B` | Verified, published, paid, "yes" verdict |
| `--color-warning` | `#E6A700` | Awaiting review, "it depends" |
| `--color-error` | `#D64545` | Error, destructive, "hard pass" |
| `--color-star` | `#EF782D` | Rating stars |

Brand gradient: `linear-gradient(161deg, #FFC596 5%, #EF782D 37%, #96371A 80%, #3C190F 104%)`.

### Type scale (Poppins)

| Role | Weight | Size | Line height |
|------|--------|------|-------------|
| H1 | 600 | 28px | 1.2 |
| H2 | 600 | 20px | 1.25 |
| H3 | 500 | 16px | 1.3 |
| Body | 400 | 14px | 1.5 |
| Caption | 400 | 12px | 1.4 |

Loaded via `next/font/google` (Poppins), fallback `ui-sans-serif, system-ui`.

### Spacing & radii

4px base. Tokens `--space-1..12` (4/8/12/16/24/32/48). Radii `--radius-sm 8`, `--radius-md 12`
(inputs, cards, pills), `--radius-lg 32` (bottom sheets, hero cards). Elevation `--shadow-sm/md/lg`.

## 2. Components

Reference token names. Every component documents states and accessibility.

- **Button**; Primary (`--color-primary` bg, white text, `--radius-md` inline / `--radius-lg` full-width), Secondary (outline), Ghost, Destructive. Disabled = 14% text-fill bg + muted text.
- **Input**; 1px `--color-border`, `--radius-md`, focus ring 2px `--color-primary`, 12px muted label above, inline error from API `errors[]`.
- **Bottom sheet**; `--color-surface`, 32px top radius, 120x8 `#D9D9D9` drag handle centered.
- **Star rating**; 1 to 5 `--color-star`; read-only on cards, interactive in the review flow; exposes text value.
- **Verdict chip**; success / warning / error mapped to backend `verdict` enum.
- **Review card**; avatar, author + trust badge, stars, verdict chip, title, "Read more" truncation, vote bar.
- **Trust badge**; stage 0 to 5 + `trust_level_name`.
- **Vote bar**; optimistic up/down; disabled on own review; 429 toast.
- **Status pill**; Verified (success) / Awaiting review (warning, for `published_at: null`).
- **Token balance widget**, **Tier/pricing card**, **Affiliate buy button** (links to `referral_redirect_url` only).

## 3. Patterns

Form + validation, bottom sheet, empty state (brand illustration + action), loading skeleton
(card-shaped), nav shell (desktop header/footer + mobile bottom tab bar). See DSD §4.1.

## 4. Motion

Default `150ms ease-in-out`. Sheet open 200ms ease-out; hover 120ms; skeleton shimmer 1.5s
linear. Nothing over 400ms; respect `prefers-reduced-motion`.

## 5. Accessibility

WCAG 2.1 AA. Contrast 4.5:1 text / 3:1 UI. **Never orange body text on white** (`#EF782D` is
~2.9:1); use `--color-primary-hover` (`#96371A`) for orange text on light, or orange as a fill
with white/`#202020` text. Focus always visible; 44x44 targets; keyboard-operable wizard;
semantic HTML.

## 6. Responsive

Mobile 390px (primary), desktop 1280px (both designed in Figma), tablet 768px interpolated.
Desktop 12-col max-width 1280px; mobile single column, 32px edge padding.
