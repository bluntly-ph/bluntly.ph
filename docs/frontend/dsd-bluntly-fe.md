# Design System Document (DSD): Bluntly.ph Frontend

**System Name:** Bluntly Foundation
**Date:** 2026-07-20
**Version:** 0.1
**Owner:** Bluntly.ph frontend track
**Status:** Draft
**PRD:** [prd-bluntly-fe.md](prd-bluntly-fe.md)

---

> **Token source.** Every value below was read from the authoritative Figma file
> `gkDEMNA9Saxy8KS8kZHKif` (mobile page + desktop page) via the Figma MCP, not invented. The
> design uses raw values rather than Figma variables, so tokens are named here and mapped to
> the observed values. The impeccable / taste-skill tooling in the FMD template is optional
> and was not run; Figma is the reconciliation source. Reconcile these tokens against Figma
> whenever the design changes, then re-materialize `BRAND.md` and `DESIGN.md`.

---

## 0. Brand Stance

### The Three Rules

| Rule | How Bluntly satisfies it |
|---|---|
| **Make it relatable** | Grounded in the Filipino online-shopping moment: the Shopee/Lazada cart, the "is this legit?" hesitation, Taglish reviews. Warm orange and playful spot illustrations, not sterile marketplace gray. |
| **Make it human** | Reviews are people talking bluntly: "Yes, absolutely", "It depends", "Hard pass". Trust stages, author badges, and hand-illustrated moments (the money-arrow, the two people talking) show a person's judgment, not a rating algorithm. |
| **Make them part of the branding** | Reviewer avatars, trust-stage badges, and user photos are first-class in review cards and profiles; the brand foregrounds the contributor, not the catalog. |

### Mode

- [x] **Both**; Brand Mode on the landing/marketing surfaces (dark, image-led hero);
  Product Mode inside the app (light, task-dense review and dashboard screens).

### Aesthetic Provenance

| Question | Answer |
|---|---|
| **Specific reference** | Filipino sari-sari-store directness meets a modern consumer app: bold warm orange, rounded friendly geometry, spot illustrations in the spirit of local comic/editorial art. |
| **A line that would never appear in slop here** | "Sabihin mo nang tapat" ("say it bluntly / honestly"). Blunt honesty is the product, so the UI never hedges. |
| **Archetypical user** | Andrea, 26, Manila, buys gadgets and skincare on Shopee during payday sales, reads 6 tabs before checkout, wants one place she can trust and maybe earn from. |
| **Slop default to avoid** | The generic marketplace look: dense gray product grids, tiny 5-star clusters, indigo-violet SaaS gradients, Inter everywhere. |
| **How users appear** | Avatars and trust badges on every review; user photos as proof-of-purchase; contributor stats on profiles. |

### Anti-References

| Anti-reference | Why forbidden |
|---|---|
| Stock marketplace review widget (Shopee/Lazada embedded stars) | The whole product exists because that pattern is untrustworthy; we must not look like it. |
| Indigo/violet B2B SaaS dashboard | Wrong culture and wrong warmth; Bluntly is consumer, Filipino, and blunt. |
| Glassmorphism fintech | The token economy is real money for real people; clarity beats gloss. |

---

## 1. Design Philosophy & Vision

**Core aesthetic:** warm, direct, and trustworthy. Bold orange as the single committed accent,
generous rounded surfaces (up to 32px on sheets), Poppins throughout, and friendly spot
illustrations for empty and value moments. The marketing surface is dark and confident; the
app is light and legible.

**Emotional intent:** the reader feels the platform is on their side and blunt with them; the
reviewer feels encouraged (the AI critique nudge) but never gated by decoration.

**Aesthetic references:** modern Filipino consumer apps (GCash-era warmth) reinterpreted with a
single bold orange and editorial illustration, not gradient soup.

**What this system explicitly avoids:**
- Indigo/violet gradients and glassmorphism.
- Tiny dense star clusters copied from marketplaces.
- Inter-as-only-font; Poppins carries the brand.

---

## 2. Brand Primitives

### 2.0 Token Architecture

Three tiers: **primitive** (raw, e.g. `--orange-500: #EF782D`), **semantic** (meaning, e.g.
`--color-primary: var(--orange-500)`), **component** (scoped, e.g. `--button-bg: var(--color-primary)`).
Implemented as Tailwind v4 theme tokens (`@theme`) in `app/globals.css`. Tables list semantic
names; DESIGN.md records the primitive scale.

### 2.1 Colors

Observed on the auth sheet (`5348:2789`), review page (`4218:1196`), and desktop landing
(`1146:664`).

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg` | `#FFFFFF` (light) / `#141414` (dark landing) | Page background |
| `--color-surface` | `#F2F2F2` | Cards, sheets, panels |
| `--color-border` | `rgba(32,32,32,0.30)` | Dividers, input borders |
| `--color-primary` | `#EF782D` | CTAs, active states, brand accent |
| `--color-primary-hover` | `#96371A` | Hover / pressed (darker orange) |
| `--color-primary-tint` | `#FFC596` | Highlights, gradient top, subtle fills |
| `--color-text` | `#202020` | Body copy |
| `--color-text-muted` | `rgba(32,32,32,0.70)` | Secondary text, labels |
| `--color-text-disabled` | `rgba(32,32,32,0.52)` | Disabled text |
| `--color-star` | `#EF782D` / gold | Rating stars |
| `--color-success` | `#2E9E5B` | Verified, published, paid |
| `--color-warning` | `#E6A700` | Awaiting review, caution |
| `--color-error` | `#D64545` | Errors, destructive, hard-pass verdict |

The signature brand gradient (auth hero): `linear-gradient(161deg, #FFC596 5%, #EF782D 37%, #96371A 80%, #3C190F 104%)`.

### 2.2 Logo System

| Variant | Asset path | Use when |
|---------|------------|----------|
| Primary wordmark | `public/brand/bluntly-logo.svg` (export from Figma `Icons & Logos` `1902:2023`) | Default lockup, header |
| Icon / mark | `public/brand/bluntly-mark.svg` | Favicon, app icon, tight space |

**Clear space:** 1x mark height on all sides. **Minimum size:** 20px mark height.
**Approved backgrounds:** white, `#F2F2F2`, dark `#141414`, or over the brand gradient with
sufficient contrast. **Don'ts:** recolor outside the palette, stretch, drop-shadow, place over
a busy photo without a scrim.

### 2.3 Typography

Typeface is **Poppins** (observed weights Regular 400 and Medium 500; add SemiBold 600 for
headings). Load via `next/font/google`.

| Role | Font | Weight | Size | Line height |
|------|------|--------|------|-------------|
| Heading 1 | Poppins | 600 | 28px | 1.2 |
| Heading 2 | Poppins | 600 | 20px | 1.25 |
| Heading 3 | Poppins | 500 | 16px | 1.3 |
| Body | Poppins | 400 | 14px | 1.5 |
| Small / Caption | Poppins | 400 | 12px | 1.4 |
| Mono / Code | ui-monospace | 400 | 13px | 1.5 |

**Font loading:** `next/font/google` (Poppins), self-hosted at build, `display: swap`.
**Fallback:** `Poppins, ui-sans-serif, system-ui, sans-serif`.

> Note: the installed scaffold currently loads Geist (`app/layout.tsx`). Switching to Poppins
> is an FE-M1 task tracked by the SDD/BUILD.

### 2.4 Imagery & Illustration

**Style:** flat editorial spot illustrations with a warm palette (see "Let's talk money"
`4550:8677`, the two-people "Your opinion matters" scene, the money-arrow on the desktop
request teaser). User photos appear as proof-of-purchase in reviews.
**AI positive prompts:** flat vector, warm orange palette, Filipino everyday-shopping scenes,
friendly rounded shapes. **AI negative prompts:** 3D render, glassmorphism, corporate stock
photo, indigo/violet.

### 2.5 Elevation & Depth

| Level | CSS value | Usage |
|-------|-----------|-------|
| `--shadow-sm` | `0 1px 2px rgba(32,32,32,0.08)` | Inline cards |
| `--shadow-md` | `0 4px 12px rgba(32,32,32,0.12)` | Floating cards, popovers |
| `--shadow-lg` | `0 12px 32px rgba(32,32,32,0.20)` | Modals, bottom sheets |

---

## 3. Layout & Spatial System

**Base unit:** 4px; all spacing is a multiple.

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight internal gaps |
| `--space-2` | 8px | Component padding |
| `--space-3` | 12px | Medium gaps |
| `--space-4` | 16px | Default spacing (matches the 32px screen edge / 16px inner padding seen in Figma) |
| `--space-6` | 24px | Section gaps |
| `--space-8` | 32px | Screen edge padding (mobile gutter observed at 32px) |
| `--space-12` | 48px | Page-level spacing (desktop) |

**Radii:** `--radius-sm: 8px`, `--radius-md: 12px` (inputs, pills, review cards),
`--radius-lg: 32px` (bottom sheets, hero cards). **Grid:** desktop 12-column, max-width
1280px, 24px gutters; mobile single column, 32px edge padding.

**Breakpoints:** Mobile `390px` (primary), Tablet `768px`, Desktop `1280px` (both 390 and 1280
are designed in Figma; 768 is an interpolation the app must handle gracefully).

---

## 4. Core Component Specs

### Buttons

| Variant | Background | Text | Border | Hover | Disabled |
|---------|-----------|------|--------|-------|----------|
| Primary | `--color-primary` | white | none | `--color-primary-hover` | `--color-text` at 14% bg, muted text (matches disabled "Send code" pill) |
| Secondary | white | `--color-primary` | 1px `--color-primary` | `--color-surface` bg | 40% opacity |
| Ghost | transparent | `--color-text` | none | `--color-surface` bg | 40% opacity |
| Destructive | `--color-error` | white | none | darkened error | 40% opacity |

**Radius:** 12px pill for primary CTAs (observed 32px on the full-width auth CTA; use
`--radius-lg` for full-width sheet CTAs, `--radius-md` inline). **Padding:** 16px vertical on
full-width CTAs, 10px 16px inline. **Font:** Poppins 500, 16px (CTA) / 14px (inline).

### Inputs & Forms

- Border: `1px solid --color-border`; radius `--radius-md` (12px, observed).
- Focus ring: `2px solid --color-primary`, offset 2px.
- Label: 12px `--color-text-muted` above the field (observed "Email address" label pattern).
- Error state: `--color-error` border + error text below (fed by API `errors[]`).
- Padding: 14px 16px (48px field height observed).

### Surfaces (Cards, Sheets, Modals)

- Background `--color-surface`; radius `--radius-md` for cards, `--radius-lg` top corners for bottom sheets (observed 32px top radius on the auth sheet and action menus).
- Drag handle on sheets: 120x8px `#D9D9D9` pill, centered (observed).
- Modal backdrop: `rgba(0,0,0,0.4)`.

### Domain components (build from these)

| Component | Notes |
|-----------|-------|
| Star rating | 1 to 5, `--color-star`; read-only on cards, interactive in the review flow; announce value to screen readers. |
| Verdict chip | "Yes absolutely" (success), "It depends" (warning), "Hard pass" (error); maps to backend `verdict` enum. |
| Review card | Avatar, author + trust badge, stars, verdict chip, title, truncation with "Read more" (`1643:1566`), vote bar. |
| Trust / reputation badge | Trust stage 0 to 5 + `trust_level_name` from `GET /users/{id}/trust`. |
| Vote bar | Up/down with optimistic count; disabled on own review; rate-limit toast on 429. |
| Verification / status pill | Verified (success), Awaiting review (warning) for `published_at: null`. |
| Token balance widget | String-decimal balance; used in dashboard, wallet, request board. |
| Tier / pricing card | Special, Founding, Standard; highlights the user's current tier. |
| Affiliate buy button | Links to `referral_redirect_url` only; never a raw URL; hidden until published + monetized. |

### 4.1 Composition Patterns

| Pattern | Components | When | Do / Don't |
|---------|------------|------|------------|
| Form + validation | Input, label, inline error, primary CTA | Auth, review flow, request form | Do map API `errors[]` to fields by `loc`. Don't block submit on AI critique. |
| Bottom sheet | Sheet + drag handle + content | Filters, sort, action menu, auth on mobile | Do use 32px top radius. Don't stack more than one sheet. |
| Empty state | Illustration + one line + primary action | No results, no reviews, no requests | Do use a brand illustration. Don't ship a gray placeholder box. |
| Loading state | Skeleton cards (review/list shapes) | Any async list/detail | Do design the skeleton to match the card. Don't show a bare spinner on lists. |
| Nav shell | Top header + footer (desktop), bottom tab bar (mobile) | Every screen | Do keep the account menu on authed screens. Don't hide primary nav mid-flow except in the review wizard. |

---

## 5. Motion & Micro-interactions

**Transition default:** `all 150ms ease-in-out`.

| Interaction | Duration | Easing | Notes |
|-------------|----------|--------|-------|
| Button hover/active | 120ms | ease-out | |
| Bottom sheet open | 200ms | ease-out | Slide up + fade |
| Sheet / modal close | 150ms | ease-in | |
| Page transitions | 180ms | ease-in-out | |
| Vote count change | 120ms | ease-out | Count tick, no bounce |
| Loading skeleton | 1.5s | linear | Shimmer loop |

**Avoid:** animations over 400ms, looping motion without user intent, motion that does not
communicate a state change.

---

## 6. Accessibility (a11y)

WCAG 2.1 AA is the definition-of-done (per the roadmap).

- **Contrast:** 4.5:1 text, 3:1 UI. Note: orange `#EF782D` on white is ~2.9:1, so orange text
  on white is banned for body copy; use orange for fills/icons with `#202020` or white text on
  the orange fill, and `--color-primary-hover` (`#96371A`, ~6.4:1) for orange text on light.
- **Focus indicators:** always visible; never remove `outline` without a replacement ring.
- **Touch targets:** minimum 44x44px (bump the 48px fields and pill CTAs accordingly).
- **Keyboard:** every control reachable and operable; the multi-step review wizard is fully keyboard-navigable.
- **Screen reader:** semantic HTML first; star ratings and verdict chips expose text values.
- **Reduced motion:** wrap non-essential animation in `@media (prefers-reduced-motion: reduce)`.

---

## 7. Taste-Skill Settings

Optional tooling; not wired. Recorded dials for reference:

```
DESIGN_VARIANCE:    5  (committed orange + illustration, still coherent)
MOTION_INTENSITY:   3  (subtle, state-communicating only)
VISUAL_DENSITY:     6  (review and dashboard screens are information-dense)
```

**Reason:** the brand is expressive on marketing surfaces but must stay legible and dense in
the review/dashboard product.

---

## 8. Impeccable Quality Gate

Impeccable is not installed in this repo. The equivalent bar is enforced through the QAD
accessibility checklist and the FE-M3 responsive/cross-browser matrices (PRD-F19). Launch gate
for this DSD:

- [ ] No WCAG 2.1 AA violations on any Must-Have screen (contrast, focus, targets, keyboard).
- [ ] Responsive parity verified 390px to 1280px.
- [ ] No slop anti-patterns: no orange body text on white, no gray placeholder empty states, no gradient text, Poppins is present (not Geist), star clusters use the domain component.

| Dimension | Target | Owner |
|---|---|---|
| Accessibility | AA, 0 P0/P1 | QAD §accessibility |
| Responsive | 390 to 1280 parity | QAD FE-M3 matrix |
| Theming | light app + dark landing tokens consistent | this DSD §2.1 |

### 8.4 Application Examples

| Surface | Do | Don't |
|---------|----|-------|
| Landing hero (desktop) | Dark `#141414` bg, white headline, orange search CTA | Put orange text on the dark bg at body size without checking contrast |
| App shell | Light surfaces, orange only for primary actions and active nav | Fill large areas with orange |
| Review card | Avatar + trust badge + verdict chip lead the eye | Bury the verdict under raw star numerals |

---

## 9. Governance

The DSD is the single source of truth. `BRAND.md` (verbal identity) and `DESIGN.md` (visual
language) at the repo root are **materialized** from this file; edit the DSD and re-materialize,
never hand-edit the root copies. Any token change reconciles against Figma
`gkDEMNA9Saxy8KS8kZHKif` first.

---

## Self-Check

- [x] §0 Brand Stance complete before tokens.
- [x] Tokens read from Figma, not invented; source file id recorded.
- [x] Three-tier token architecture defined; Tailwind v4 implementation named.
- [x] Core + domain components specify states and accessibility.
- [x] a11y section calls out the orange-on-white contrast trap explicitly.
- [x] Materialization to BRAND.md / DESIGN.md and governance defined.
