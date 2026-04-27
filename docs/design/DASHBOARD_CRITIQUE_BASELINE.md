# Dashboard Critique — Baseline (session 23)

**Scope**: Operator dashboard at `dashboard/` (Next.js + Tailwind +
shadcn/ui). Audited pages: `/admin/sessions`, `/admin/sessions/[id]`,
`/admin/analytics`, `/admin/feedback` + global `layout.tsx` + token
system (`globals.css`, `tailwind.config.ts`).

**Method**: code-level audit (no Figma file present). Findings come
from reading the source; no live browser interaction yet — that's the
next pass under `design:accessibility-review` once the priority items
land.

**Goal**: produce a baseline before extending the dashboard with the
new operator surfaces from Track A (review queue, lead-link curate).
The drift surfaced here is what the upcoming `design:design-system`
pass should normalise.

---

## Overall impression

The dashboard works — every page renders, fetches data, and ships in
production — but it's **a layer of inconsistencies over a half-built
component library**. shadcn/ui is configured but only `button.tsx` +
`card.tsx` exist as primitives, so most surfaces re-implement the
same patterns inline (cards, filter pills, badges, tables) with
slightly different spacing, radius, and color conventions every time.
Token system has visible duplication (`globals.css` defines colors
twice with different formats) and most pages bypass tokens by
reaching for raw Tailwind colors (`bg-red-50`, `text-emerald-600`).

**Biggest opportunity**: Build out the missing shadcn primitives
(badge, table, tabs, tooltip, select, input) and migrate the four
audited pages to consume them. Most drift collapses automatically.

---

## Usability

| Finding | Severity | Recommendation |
|---|---|---|
| **No persistent navigation** — every page repeats hardcoded `<a>` cross-links in its header (sessions → analytics → feedback → tuning, in slightly different order each time). Operator has to scan the top of the page to see where they can go next. | 🔴 Critical | Add a left sidebar (`<aside>`) with the canonical admin sections fixed across every `/admin/*` page. Promote it to a layout under `app/admin/layout.tsx` so individual pages stop repeating the link list. |
| **Sort direction is not labeled in the table headers** — only "↑/↓" arrow next to the column name. Screen readers + new operators have to infer. | 🟡 Moderate | Add `aria-sort="ascending" / "descending"` on `<th>`; visually pair the arrow with a textual label or a recognisable icon (e.g. lucide ArrowUp/ArrowDown). |
| **Filter pills are non-semantic `<a>` tags styled as buttons** — keyboard focus state inherits the link default (often invisible against the page background), and screen readers announce them as links not toggle buttons. | 🟡 Moderate | Either keep them as links (server-rendered URL filters — the right call) and ensure visible `:focus-visible` ring; or migrate to a shadcn `<ToggleGroup>` once the primitive lands. |
| **Sessions page has 5 cross-links in the header bar** — visual noise; the operator can't tell which is the "primary" next action. | 🟡 Moderate | Surface only the 1-2 most-used adjacent actions in the page header (analytics, export). Move "tuning-report", "status", and others to the sidebar. |
| **No empty / loading / error states beyond a single muted text line** ("Sessions yok"). On a Supabase outage the user sees a one-line `common.error: <message>` div with no action affordance. | 🟡 Moderate | Add `<EmptyState>` and `<ErrorState>` shadcn-style components with an icon + title + description + retry CTA. |
| **JSON dump for session detail** — `<pre>` with full structured payload. Operator has to read raw JSON to triage a session. | 🟡 Moderate | Wrap structured fields in a `<DescriptionList>` or `<Tabs>` (Raw / Summary / Outputs). Keep raw JSON behind a "Show raw" toggle. |
| **Sessions list capped at 100 rows with no pagination** — once traffic grows the operator can't see older sessions. | 🟢 Minor | Add cursor-based pagination on `created_at` once needed. Not urgent — current scale is small. |

---

## Visual hierarchy

- **What draws the eye first**: in `/admin/sessions` the eye lands on
  the **filter pills** (red "down only" pill is the brightest), not
  on the H1 or the data. For a triage queue this is actually OK —
  the filter is the primary action — but the H1 is so muted by
  comparison it feels skippable. In `/admin/analytics` the eye hits
  the H1 first (`text-[26px] font-black`), then the "Live link" CTA
  in `text-emerald-600` — the green link competes with the H1's
  weight.

- **Reading flow**: top-to-bottom is fine on every page (header →
  filters → data table / cards). No surprises. But **horizontal
  flow** in the analytics grid is busy: 4 stat cards + 3 stat cards +
  3 LLM stats + envelope distribution + daily list + 2 distributions
  + confusion table — that's 9 sections stacked vertically with no
  visual grouping (e.g. "Volume" / "Quality" / "LLM Health").

- **Emphasis**:
  - H1 inconsistency hides the page identity (sessions
    `text-2xl font-bold`, analytics `text-[26px] font-black`,
    feedback presumably similar). When the operator opens a page
    quickly they can't tell at a glance "am I on analytics or
    feedback?"
  - Stat cards use `text-[28px] font-extrabold` for the value (analytics) AND
    `text-3xl font-extrabold` (feedback). Same intent, two sizes
    (28px vs 30px) — small but it's the kind of drift the operator
    feels subconsciously.

---

## Consistency

| Element | Issue | Recommendation |
|---|---|---|
| **Card** | THREE separate implementations in audited pages: (1) `components/ui/card.tsx` shadcn — used by analytics, (2) local `function Card` in `feedback/page.tsx` (`rounded-2xl p-5`), (3) inline `<div className="rounded-xl border bg-card shadow-sm">` in sessions. Visually similar, structurally divergent. | Consolidate to `components/ui/card.tsx`. Delete local `Card` and inline div definitions. |
| **Stat card** | TWO implementations: `function Stat` in analytics (`p-4 rounded-xl`) and `function StatCard` in feedback (`p-5 rounded-xl` + `accentClass` top border). | Promote to `components/ui/stat-card.tsx` shadcn-style. Pick one padding (`p-4` likely — feedback's 5 is generous) and document the `accent` prop in the component. |
| **Border radius** | Four values in audited code: `rounded-2xl` (feedback Card), `rounded-xl` (analytics Stat), `rounded-[10px]` (sessions filter pills), `rounded-lg` (feedback FilterTab). Token defines `--radius: 0.375rem` (6px) and Tailwind extends to lg/md/sm — the magic `rounded-[10px]` doesn't map to anything. | Standardise on the token: `rounded-md` for inputs / pills, `rounded-lg` for cards, `rounded-xl` for hero-tier surfaces. Ban arbitrary `rounded-[Npx]`. |
| **H1 typography** | Sessions `text-2xl font-bold` (24px / 700), analytics `text-[26px] font-black` (26px / 900). | Pick one. Recommend `text-2xl font-bold` (matches Tailwind preset, already on sessions). Move analytics to it. |
| **Filter pills** | Sessions reimplements pill markup inline three times. Feedback extracts a `FilterTab` component but it's local to that page. | Promote `<FilterTab>` to `components/ui/filter-tab.tsx`. Move sessions to consume it. |
| **Color tokens vs raw Tailwind** | Pages mix `text-primary` / `bg-card` (token-driven) with `text-red-700`, `text-emerald-600`, `text-amber-700`, `bg-red-50`, `bg-green-100`, etc. (raw Tailwind). Dark variants are ad-hoc per call site (`dark:bg-red-950/50` here, `dark:bg-red-900/40` there). | Add semantic tokens to globals.css: `--success`, `--warning`, `--destructive` (already present), `--info`. Map status colors via these. Remove every `bg-red-*` / `bg-green-*` / `bg-amber-*` / `bg-emerald-*` / `bg-blue-*` from page code. |
| **`globals.css` token duplication** | Both `:root` (HSL `H S L` format, lines 7–54) AND `:root` inside `@layer base` (oklch format, lines 118–172) define the SAME tokens with DIFFERENT values. Light theme is doubled; dark theme is doubled. The browser uses last-wins (oklch block) but the HSL block is still authoritative for some calc() chains. | Pick ONE format. Recommend keeping the `oklch()` block (modern, perceptually uniform) and deleting the HSL block + the `--dash-*` legacy aliases. Update `tailwind.config.ts` colors from `var(--primary)` to `oklch(var(--primary))` if shadcn/ui Tailwind plugin needs it. |
| **Unused tokens** | `globals.css` defines `--shadow-*`, `--spacing`, `--tracking-*`, `--letter-spacing` but Tailwind config doesn't extend them — they're orphaned. | Either extend Tailwind to consume them or delete. Orphan tokens are drift bait. |
| **Magic font sizes** | `text-[13px]` appears 12+ times across audited pages (between `text-xs` 12px and `text-sm` 14px). Also `text-[10px]`, `text-[26px]`, `text-[28px]`. | Define a tighter type ramp: 11/12/13/14/16/18/20/24/30/36 if needed, expose as Tailwind preset (`text-xs2` / `text-sm-tight`). Ban arbitrary `text-[Npx]`. |
| **Status color strategy** | `getConfidenceClass` (analytics) maps "high" → green, "medium" → amber, "low" → red. EMERGENCY envelope badge uses `bg-red-50/text-red-700`. Feedback rating uses `bg-green-100/text-green-800` for up, red for down. THREE different green/red shade pairs for the same "good/bad" semantic. | Consolidate to `<Badge variant="success|warning|destructive|info">` once the badge primitive lands. |
| **i18n bootstrap** | Every page calls `getLocale()` then `getText(locale, ...)`. Repeat. | Layout-level locale context (server-side) so pages read `t("...")` directly. Less per-page boilerplate. |

---

## Accessibility (code-level — needs live audit follow-up)

- **Color contrast**: tokens look reasonable on paper (foreground
  `oklch(0.32 0 0)` on background `oklch(1.0 0 0)` ≈ 9.6:1, well
  above AA), but raw colors in pages aren't verified. `text-emerald-600`
  on `bg-background` (white) is borderline (4.5:1 ish — depends on
  Tailwind's exact emerald-600 value). The accessibility-review pass
  needs to check every status-tinted text against AA + AAA targets.
- **Touch targets**: `py-2 px-4` filter pills are ~36px tall — under
  Apple HIG 44pt but acceptable on desktop. Mobile dashboard view
  hasn't been validated.
- **Text readability**: `text-[10px]` for ICD-10 chips on session
  detail is below WCAG 2.1 minimum (~12px). Promote to `text-xs`
  (12px) at least.
- **Keyboard navigation**: `no-underline` on `<a>` links removes the
  default underline cue; **without explicit `:focus-visible` styling
  the keyboard focus indicator is invisible**. Major a11y gap.
- **Sort headers**: `<th>` lacks `scope="col"`; sortable links lack
  `aria-sort`; arrow is rendered as an emoji string with no
  `aria-label`. Three separate fixes.
- **Color-only signaling**: envelope badges (RESULT / EMERGENCY /
  SAME_DAY) rely on background color alone. Add a leading icon (e.g.
  `<AlertCircle>` for EMERGENCY, `<CheckCircle>` for RESULT) so
  color-blind users get the same signal.
- **JSON `<pre>` block**: long horizontal scroll on session detail,
  no copy-button. Functional accessibility — operator should be able
  to copy a session's JSON without selecting text manually.

---

## What works well

- **Token system foundation is correct** — semantic names
  (`background`, `foreground`, `card`, `primary`, `muted-foreground`),
  light/dark variants paired, shadcn/ui contract honored. Just needs
  cleanup of the duplicate definitions and disciplined usage.
- **Server-side rendering + i18n** — everything renders on the
  server, locale is a cookie, no client hydration headaches.
  `getText(locale, "...")` flow is simple and works.
- **Tailwind config minimal** — extends only what's needed (colors
  via CSS vars, fonts, radius). Easy to migrate.
- **Breadcrumb component** — exists, reused across pages, gives the
  operator a "where am I" anchor. Keep it.
- **shadcn `<Card>` + `<Button>` are wired correctly** — the parts
  that DO use the primitives look right. Building the rest of the
  primitive set fills the gap, doesn't replace what's there.
- **Sparkline inline SVG** (analytics) — no chart library bloat,
  performant, accessible-friendly. Pattern worth keeping.
- **Theme + locale toggle work without flicker** — `theme-init`
  inline script in `<head>` runs `beforeInteractive`, sets the right
  class before paint. Good engineering.

---

## Priority recommendations

### 1. **Fill the shadcn/ui primitive gap** — biggest leverage
Add: `badge`, `table`, `tabs`, `tooltip`, `select`, `input`, `dialog`,
`stat-card`, `filter-tab`, `empty-state`, `error-state`. ~10
components. Once they exist, migrating audited pages to consume them
(commit per page) collapses most of the drift in this report
mechanically. **This unblocks the design-system pass.**

### 2. **Resolve the `globals.css` token duplication** — drift root cause
Pick the oklch block, delete the HSL block + `--dash-*` aliases.
Verify shadcn Tailwind plugin works with `oklch(var(--primary))` (or
keep HSL if not — but only one of them). Add the missing semantic
tokens (`--success`, `--info`) so pages stop reaching for raw
Tailwind palette.

### 3. **Promote `app/admin/layout.tsx` with a sidebar**
Stops every page from re-rendering the cross-link header. Sidebar
items: Sessions, Analytics, Feedback, Tenants, Tuning, Live, Status.
The new operator surfaces from Track A (Uploads review queue,
Operators, Lead links) slot in here too — without this layout the
new pages would inherit the same drift.

### 4. **Standardise the type + radius + spacing ramp**
Document in `dashboard/docs/DESIGN_TOKENS.md` (new). Ban arbitrary
`text-[Npx]` / `rounded-[Npx]` via an ESLint rule (custom or
`tailwindcss-plugin` `disallowedClasses`). Forcing future code to
pick from the ramp prevents drift recurrence.

### 5. **Accessibility quick wins** (before the full
`design:accessibility-review` pass)
- Add `:focus-visible` ring to every link/button
- Replace `text-[10px]` with `text-xs`
- `aria-sort` + `scope="col"` on sortable table headers
- Leading icons on status badges (color + shape redundancy)
- These five fixes are mechanical and address the biggest a11y gaps
  surfaced in the code audit.

### 6. (Deferred to design-system pass) — component patterns
- Status badge variants (success/warning/destructive/info) — central
- Page header pattern (H1 + subtitle + primary action + locale-aware
  meta) — now repeated three different ways across audited pages
- Empty state pattern (icon + title + description + CTA)

---

## What's NOT in scope here

- Live a11y audit (separate `design:accessibility-review` pass)
- Mobile / responsive behaviour (no live test yet)
- Performance / Lighthouse (separate `dashboard-lighthouse.yml`
  workflow handles this)
- New operator pages from Track A (review queue, lead-link curate)
  — those land *after* the design-system pass establishes the
  primitive library, so they don't bake in more drift

---

## Suggested sequence for session 23 (this same session)

1. **(this doc)** ✓ — baseline critique
2. **`design:accessibility-review`** — live a11y audit on the same
   four pages, layered onto this report
3. **`design:design-system`** — apply the priority recommendations
   above as a structured token + primitive pass
4. **`design:design-handoff`** — tasarım çıktısı tamamlandığında,
   Track A'nın yeni operator sayfaları için Figma → React spec
   (review queue, lead-link curate)

Each step's output should land in `docs/design/` so the trail stays
together and a later operator can reconstruct the design rationale.
