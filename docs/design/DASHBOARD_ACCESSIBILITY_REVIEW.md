# Dashboard Accessibility Review — WCAG 2.1 AA

**Date**: session 23 (post-baseline critique)
**Standard**: WCAG 2.1 Level AA
**Scope**: Same 4 pages as the baseline critique
(`/admin/sessions`, `/admin/sessions/[id]`, `/admin/analytics`,
`/admin/feedback`) + global layout + token system.
**Method**: code-level audit + computed contrast ratios against
Tailwind palette and `globals.css` `oklch()` tokens. Live browser
test (zoom 200%, screen-reader) deferred — automated scan and
keyboard-only walk-through still need to follow this code pass.

## Summary

**Issues found**: 18 | **Critical 🔴**: 4 | **Major 🟡**: 9 | **Minor 🟢**: 5

**Top blockers**:
1. Several status-tinted texts on light backgrounds fail 4.5:1
   (notably `text-emerald-600` on white at ~3.4:1 — used for the
   "Live" link in analytics)
2. No visible focus indicator on dashboard `<a>` links
   (`no-underline` removes default cue, no `:focus-visible` ring)
3. Sortable table headers missing `aria-sort` + `scope="col"` —
   screen-reader users can't tell which column is sorted
4. Status badges (EMERGENCY / RESULT / SAME_DAY) signal via color
   alone — color-blind users get no redundancy

---

## Findings

### Perceivable

| # | Issue | WCAG | Severity | Recommendation |
|---|---|---|---|---|
| 1 | `text-emerald-600` (#059669) on `bg-background` (white) — analytics "Live" link CTA. Computed ratio ~3.4:1, fails AA 4.5:1 for normal text. | 1.4.3 Contrast | 🔴 Critical | Map to a token-driven `text-success` set to a darker green (e.g. `oklch(0.45 0.18 156)` ≈ green-800). Document in design tokens; ban `emerald-*` raw class. |
| 2 | `text-amber-700` (#b45309) on white. Used for "medium confidence" label in analytics. Ratio ~4.4:1 — borderline fail (under 4.5:1 by 0.1, considered fail). | 1.4.3 Contrast | 🔴 Critical | Use `text-amber-800` (#92400e, ~6.1:1) for normal text on light bg. Reserve `amber-700` for backgrounds + large text only. |
| 3 | `text-primary` (`oklch(0.62 0.19 260)` ≈ #3b7df9) on `bg-background` (white). Used as link color across pages (sortable headers, "view →" links). Ratio ~4.0:1. **Fails AA for normal text** (passes large text 3:1). | 1.4.3 Contrast | 🔴 Critical | Darken `--primary` to `oklch(0.55 0.20 260)` (~5.2:1 vs white) OR layer a darker `--primary-text` token used in `text-primary` only (keep current `--primary` for `bg-primary` solid buttons where the foreground is white). |
| 4 | Status badges signal envelope type / feedback rating via background+text color alone (`bg-red-50/text-red-700` for EMERGENCY, etc.). Color-blind users (8% of male users) get no signal. | 1.4.1 Use of Color | 🔴 Critical | Add a leading icon to each status: `<AlertCircle>` for EMERGENCY, `<CheckCircle>` for RESULT, `<Clock>` for SAME_DAY, `<HelpCircle>` for QUESTION, `<XCircle>` for ERROR. Color + shape redundancy. Same fix on feedback rating badges (👍 / 👎 icon). |
| 5 | `text-[10px]` for ICD-10 chips on session detail page. Below WCAG comfortable-reading minimum and unreadable at low vision settings. | 1.4.4 Resize Text (related) | 🟡 Major | Bump to `text-xs` (12px) at minimum. ICD codes are mono — kept readable + scannable. |
| 6 | `text-[13px]` (~13px) on filter pills, table cells, link CTAs. Just under Tailwind `text-sm` (14px). Not a direct WCAG fail but creeps under common minimum-readable thresholds. | 1.4.4 Resize Text (related) | 🟢 Minor | Standardise to `text-sm` (14px) in next type-ramp pass. Drop the magic 13px value. |
| 7 | Inline `<svg>` Sparkline (analytics) has no `<title>` / `aria-label` — screen reader announces nothing. | 1.1.1 Non-text Content | 🟡 Major | Add `<title>` child + `role="img"` and `aria-label` describing the trend ("7-day top-1 accuracy: 87% trend up"). |
| 8 | `<pre>` JSON dump on session detail has no semantic indication that it's structured data; screen reader reads it character by character including punctuation. | 1.3.1 Info and Relationships | 🟡 Major | Wrap in `role="region"` + `aria-label="raw session JSON"`. Long-term: replace with a structured `<DescriptionList>` for the common fields, keep raw JSON behind a "Show raw" toggle. |

### Operable

| # | Issue | WCAG | Severity | Recommendation |
|---|---|---|---|---|
| 9 | `<a className="no-underline ...">` removes the default underline (link-recognition cue) AND nothing else replaces it. No `:focus-visible` ring on any link in the audited pages. **Keyboard users cannot see where focus is.** | 2.4.7 Focus Visible | 🔴 Critical | Add a global rule: `a:focus-visible, button:focus-visible { @apply outline-none ring-2 ring-ring ring-offset-2 ring-offset-background; }`. Tailwind `ring-ring` already maps to `--ring` token. One line in `globals.css` fixes every page at once. |
| 10 | Sortable column headers: `<a href>` with sort icon. Server-rendered URL flip — works for keyboard, but no `aria-sort` attribute on the `<th>`. Screen reader announces the link, never the sort state. | 4.1.2 Name, Role, Value (also 1.3.1) | 🟡 Major | Set `aria-sort="ascending"` / `"descending"` / `"none"` on each `<th>` based on the current params. Add `scope="col"` to every column header (covers SR table-navigation mode). |
| 11 | Filter pills (`/sessions?feedback=down`) styled as buttons but rendered as `<a>`. Functional with keyboard (server URL change), but the role announcement doesn't match the visual: SR says "link" not "button". Acceptable per spec — but should be consistent across pages. | 4.1.2 Name, Role, Value | 🟢 Minor | Decision: keep as `<a>` (URL state preserves filter on share / refresh — the right call). Document the convention in the design system: "Filter pills are always links, not buttons." |
| 12 | Touch targets on filter pills (`py-2 px-4`): ~36px tall. Under iOS HIG 44pt and Android 48dp. Fine on desktop, fails on mobile / tablet operator usage. | 2.5.5 Target Size | 🟡 Major | Bump to `py-2.5` (10px vertical = ~40px) AND ensure `min-h-11` (44px) on touch-coarse media query. Or wrap in `<a className="block py-2.5 px-4 min-h-[44px]">`. |
| 13 | Sessions page renders 5 cross-links in a row (`feedback` / `status` / `analytics` / `tuning` / `export csv`) with `gap-2.5`. Tab order is left-to-right; reasonable. But there's no skip link from the header to the table content — keyboard user has to tab through the language switcher + theme toggle + 5 page links + 3 filter pills + every column header before reaching a row. | 2.4.1 Bypass Blocks | 🟡 Major | Add a "skip to main content" link as the first focusable element (visually hidden until focused — `sr-only focus:not-sr-only`). Pair with `<main id="main">` on each admin page. |
| 14 | The "↑/↓" sort indicator is rendered as a Unicode arrow inside the link text. Some screen readers announce as "up arrow" — fine; some skip; some read as "u plus 2191". Inconsistent across NVDA/JAWS/VoiceOver. | 1.3.1 Info and Relationships | 🟢 Minor | Replace with a lucide `<ArrowUp>` / `<ArrowDown>` icon that has `aria-hidden="true"`, and put the textual cue in `aria-sort` (already covered by #10). |

### Understandable

| # | Issue | WCAG | Severity | Recommendation |
|---|---|---|---|---|
| 15 | Empty state on sessions list = "Sessions yok" (or English equivalent), wrapped in a single `<td colSpan>`. No icon, no description of why empty, no recovery action ("filtre uygula", "destek seç"). | 3.3.1 Error Identification (related — pattern of unhelpful empty states) | 🟡 Major | Build `<EmptyState>` primitive with icon + heading + description + optional CTA. Common pattern across multiple pages. |
| 16 | Error state (`common.error: <message>`) on Supabase outage = single muted line. No retry button, no escalation hint. | 3.3.1 Error Identification | 🟡 Major | Build `<ErrorState>` primitive with icon + heading + message + retry CTA + (admin only) link to `/admin/status`. |

### Robust

| # | Issue | WCAG | Severity | Recommendation |
|---|---|---|---|---|
| 17 | `<header>` is a `<header className="sticky top-0...">` with locale + theme + privacy link. Right-aligned, no `role="banner"` (implicit on `<header>` direct child of `<body>` — actually OK per spec). But `<main>` element is **missing** — every page renders content directly in a `<div className="p-6">`. | 4.1.2 Name, Role, Value (landmark) | 🟡 Major | Wrap each admin page's content in `<main>`. Pair with the skip-link from #13. SR users can jump to `main` via the "Landmarks" command. |
| 18 | Theme toggle button (`<ThemeToggle>`) — without seeing source — likely needs `aria-pressed="true|false"` or `aria-label="Switch to dark theme"` so SR announces the current state. (Same for LocaleSwitcher.) | 4.1.2 Name, Role, Value | 🟢 Minor | Audit the two component sources; ensure both expose state via ARIA. Out-of-scope for the page-level audit — flagged for the design-system pass. |

---

## Color Contrast Check

Computed against light theme `--background: oklch(1 0 0)` (white,
`#ffffff`) and dark theme `--background: oklch(0.20 0 0)` (~`#333333`)
unless otherwise noted. Token equivalents from `globals.css`.

### Light theme

| Element | Foreground | Background | Ratio | Required | Pass |
|---|---|---|---|---|---|
| Body text | `text-foreground` ≈ `#444` | white | **~9.6:1** | 4.5:1 | ✅ |
| Muted text | `text-muted-foreground` ≈ `#757575` | white | **~4.6:1** | 4.5:1 | ✅ (barely) |
| Primary link | `text-primary` ≈ `#3b7df9` | white | **~4.0:1** | 4.5:1 | ❌ |
| Live link CTA | `text-emerald-600` `#059669` | white | **~3.4:1** | 4.5:1 | ❌ |
| Confidence "high" | `text-green-700` `#15803d` | white | **~5.0:1** | 4.5:1 | ✅ |
| Confidence "medium" | `text-amber-700` `#b45309` | white | **~4.4:1** | 4.5:1 | ❌ (borderline) |
| Confidence "low" | `text-red-700` `#b91c1c` | white | **~5.9:1** | 4.5:1 | ✅ |
| EMERGENCY badge | `text-red-700` `#b91c1c` | `bg-red-50` `#fef2f2` | **~6.5:1** | 4.5:1 | ✅ |
| RESULT badge | `text-green-800` `#166534` | `bg-green-50` `#f0fdf4` | **~7.1:1** | 4.5:1 | ✅ |
| SAME_DAY badge | `text-amber-800` `#92400e` | `bg-amber-50` `#fffbeb` | **~6.5:1** | 4.5:1 | ✅ |
| Feedback up badge | `text-green-800` | `bg-green-100` `#dcfce7` | **~6.7:1** | 4.5:1 | ✅ |
| Feedback down badge | `text-red-800` | `bg-red-100` `#fee2e2` | **~6.0:1** | 4.5:1 | ✅ |

### Dark theme

| Element | Foreground | Background | Ratio | Required | Pass |
|---|---|---|---|---|---|
| Body text | `text-foreground` ≈ `#ebebeb` | `#333` | **~10.8:1** | 4.5:1 | ✅ |
| Muted text | `text-muted-foreground` ≈ `#a8a8a8` | `#333` | **~5.5:1** | 4.5:1 | ✅ |
| Primary link | `text-primary` ≈ `#3b7df9` | `#333` | **~4.5:1** | 4.5:1 | ✅ (barely) |
| Live link CTA | `text-emerald-400` `#34d399` | `#333` | **~7.1:1** | 4.5:1 | ✅ (note: only used in dark via `dark:`) |
| EMERGENCY badge | `text-red-300` `#fca5a5` | `bg-red-950/50` ≈ `#3a1a17` | **~5.6:1** | 4.5:1 | ✅ |
| RESULT badge | `text-green-300` | `bg-green-950/50` | **~5.5:1** | 4.5:1 | ✅ |

**Verdict**: Dark theme is largely fine. Light theme has 3 critical
failures (rows marked ❌) all caused by raw Tailwind palette colors
on white. **Mapping to semantic tokens with darker shades fixes
all three in one design-system pass.**

### Non-text contrast (UI components)

| Element | Foreground | Background | Ratio | Required (3:1) | Pass |
|---|---|---|---|---|---|
| `border` token | `oklch(0.93 0.006 264)` ≈ `#ebebec` | white | **~1.2:1** | 3:1 | ❌ |
| Card border | `oklch(0.93 ...)` | `bg-card` (white) | **~1.2:1** | 3:1 | ❌ |
| Active filter pill bg | `bg-primary` `#3b7df9` | (page bg white) | **~4.0:1** | 3:1 | ✅ |
| Theme toggle | (no border) | (no bg distinction) | — | 3:1 | depends on impl |

**Verdict**: Card borders fail 1.4.11 (non-text contrast). On a
white-on-white card-on-page setup the card edge is invisible to low-
vision users. **Bump `--border` to ~`oklch(0.85 0.006 264)`** (still
soft visually, ~3.1:1 against white) OR add a subtle shadow to give
the card definition.

---

## Keyboard Navigation

| Element | Tab order | Enter/Space | Escape | Notes |
|---|---|---|---|---|
| Header privacy link | 1st | Navigate to `/privacy` | n/a | OK |
| Locale switcher | 2nd | Toggles tr/en | n/a | Verify component handles Space too |
| Theme toggle | 3rd | Toggles light/dark | n/a | Verify component sets `aria-pressed` |
| Page H1 | (not focusable) | n/a | n/a | OK — `<h1>` should NOT be in tab order |
| Cross-page links (5 in sessions header) | 4th-8th | Navigate | n/a | Tab spam — see #13 skip link recommendation |
| Filter pills | 9th-11th | Navigate (URL change) | n/a | OK — Enter triggers anchor follow; **focus ring not visible** (see #9) |
| Sortable `<th>` link | 12th-16th | Navigate (sort flip) | n/a | OK — works; aria-sort missing (#10); focus ring missing (#9) |
| Row "view →" link | per-row | Navigate to detail | n/a | OK; **focus ring not visible** |

**Critical gap**: focus ring invisible across the entire audited
surface. Single CSS fix in `globals.css` resolves it
(see fix #9 above).

---

## Screen Reader

| Element | Announced as (likely) | Issue |
|---|---|---|
| Sortable column header | "Time, link" | Should announce sort state — needs `aria-sort` (#10) |
| Status badge | "EMERGENCY" | OK textually but no role context; `<span>` is ambient text. Consider `role="status"` on badges that announce on update; static badges are fine. |
| Sparkline SVG | (silent — no title) | Skipped entirely — needs `<title>` (#7) |
| Empty state | "Sessions yok" | Single line; lacks heading, lacks landmark — see `<EmptyState>` primitive (#15) |
| Pre JSON | Long string of characters including punctuation read individually | Wrap in `region` with label (#8); long-term replace with `<dl>` |
| Theme toggle | Depends on impl | Verify `aria-pressed` (#18) |
| Sort arrow Unicode | "up arrow" / silence / "u plus 2191" | Inconsistent — replace with icon + `aria-hidden` (#14) |

---

## Priority fixes

### Critical (block launch / WCAG fail)

1. **Add `:focus-visible` ring globally** (#9). One CSS rule. Fixes
   keyboard accessibility across every page in one go.
2. **Replace 3 failing text colors with darker semantic tokens** (#1, #2, #3):
   - `text-emerald-600` → `text-success` (oklch ~0.45 0.18 156, ~5.5:1)
   - `text-amber-700` → `text-warning` (use `amber-800`, ~6.1:1)
   - Darken `--primary` for text-only use OR layer `--primary-text`
3. **Status badges: color + icon redundancy** (#4). Lucide icon
   leading the text. Centralise in `<Badge variant="...">`.

### Major (significant UX impact)

4. **`aria-sort` + `scope="col"` on every sortable `<th>`** (#10)
5. **Bump `text-[10px]` → `text-xs` (ICD chips)** (#5)
6. **Skip link + `<main>` landmark on every admin page** (#13, #17)
7. **Sparkline `<title>` + `role="img"`** (#7)
8. **Touch target `min-h-11` on filter pills** (#12)
9. **EmptyState + ErrorState primitives** (#15, #16)
10. **Card border token bump for 1.4.11 non-text contrast** (extra
    finding from contrast table)

### Minor (polish)

11. Replace Unicode sort arrow with icon (#14)
12. Verify theme/locale toggle `aria-pressed` (#18)
13. Drop `text-[13px]` magic number → `text-sm` (#6)
14. Decide & document filter-pill role (link, not button) (#11)
15. Wrap JSON pre with region+label (#8)

---

## What's NOT covered (deferred to live-test pass)

- Real screen-reader output (NVDA on Windows, VoiceOver on macOS,
  TalkBack on Android) — code-level inference here is best-effort
- Zoom 200% reflow check (1.4.10) — needs browser
- Reduced-motion preference (`prefers-reduced-motion`) — Sparkline
  would benefit; verify after build-out
- Forms accessibility (3.3.1, 3.3.2, 4.1.3) — current audited pages
  are mostly read-only; new operator surfaces from Track A
  (review-state PATCH, lead-link PATCH) will introduce forms that
  need their own pass when the UI lands

## Suggested handoff to design-system pass

The 5 fixes that map best to **`design:design-system`** primitives:

1. `<Badge variant="success|warning|destructive|info|neutral">` —
   replaces inline status badges with icon+color redundancy baked in
2. `<EmptyState icon title description action>` — replaces ad-hoc
   `<td colSpan>` empty rows
3. `<ErrorState icon title message retry>` — replaces single-line
   error divs
4. `<DataTable>` wrapper with built-in `aria-sort` / `scope="col"` /
   sticky header — replaces the manual `<table>` markup
5. Token additions to `globals.css`:
   - `--success` / `--success-foreground`
   - `--warning` / `--warning-foreground`
   - `--info` / `--info-foreground`
   - Darker `--border` for non-text contrast
   - Optional darker `--primary-text` if `--primary` is kept blue

These should be the deliverable of the next skill pass.
