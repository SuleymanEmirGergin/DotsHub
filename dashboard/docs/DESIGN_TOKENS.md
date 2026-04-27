# Dashboard design tokens

**Owner**: dashboard team. Source of truth: `app/globals.css` +
`tailwind.config.ts`. **If a value isn't documented here, don't add
it to a component.**

This document accompanies the design-system pass landed in session 23
([baseline critique](../../docs/design/DASHBOARD_CRITIQUE_BASELINE.md),
[a11y review](../../docs/design/DASHBOARD_ACCESSIBILITY_REVIEW.md)).

## 1. Colors — semantic tokens

Every color a component reads MUST come through one of these tokens.
Raw Tailwind palette (`text-emerald-600`, `bg-amber-50`, etc.) is
**banned** in component code — drift root cause flagged in the
baseline. Status semantics → semantic token → CSS var → Tailwind
class.

| Semantic | Token | Tailwind class | Use for |
|---|---|---|---|
| Surface bg | `--background` / `--card` / `--popover` | `bg-background` / `bg-card` / `bg-popover` | Page bg / cards / floating menus |
| Body text | `--foreground` | `text-foreground` | Primary text on any surface |
| Muted text | `--muted-foreground` | `text-muted-foreground` | Secondary / supporting text, captions |
| Border | `--border` | `border-border` | Card edges, table dividers, input strokes |
| Brand bg | `--primary` | `bg-primary` | Solid CTA buttons, active filter pills |
| Brand fg | `--primary-foreground` | `text-primary-foreground` | Text ON `bg-primary` |
| **Brand link** | `--primary-text` | `text-primary-text` | text-only links / sortable headers (passes 4.5:1) |
| Success | `--success` / `--success-foreground` | `bg-success` / `text-success` | RESULT envelope, feedback up |
| Warning | `--warning` / `--warning-foreground` | `bg-warning` / `text-warning` | SAME_DAY envelope, medium confidence |
| Destructive | `--destructive` / `--destructive-foreground` | `bg-destructive` / `text-destructive` | EMERGENCY envelope, feedback down, error states |
| Info | `--info` / `--info-foreground` | `bg-info` / `text-info` | QUESTION envelope, "Klinik bilgi" chip |
| Focus ring | `--ring` | `ring-ring` | `:focus-visible` indicator (already global) |

### Why `--primary-text` exists

`--primary` (the brand blue at oklch ~0.62) on white = ~4.0:1, which
**fails WCAG 1.4.3 4.5:1 for normal text**. It's still fine for
solid `bg-primary` buttons (the `--primary-foreground` white-on-blue
pairing passes). For text-only use (`<a className="text-primary">`)
use `text-primary-text` instead — it's set to a darker shade that
passes contrast. Light theme only; dark theme primary is bright
enough already.

### Status badge mapping

The `<Badge>` primitive locks the status → variant relationship:

| Domain meaning | `<Badge variant>` |
|---|---|
| RESULT envelope | `success` |
| EMERGENCY envelope | `destructive` |
| SAME_DAY envelope | `warning` |
| QUESTION envelope | `info` |
| ERROR envelope | `neutral` |
| Feedback up | `success` |
| Feedback down | `destructive` |
| "Klinik bilgi" chip | `info` |
| Confidence high | `success` |
| Confidence medium | `warning` |
| Confidence low | `destructive` |

## 2. Typography ramp

The Tailwind preset is canonical. Pages MUST pick from the ramp; the
arbitrary `text-[Npx]` syntax is **banned** (12+ violations found in
the audited pages).

| Class | Size | Use for |
|---|---|---|
| `text-xs` | 12px | Captions, ICD codes, dense table cells, badge text |
| `text-sm` | 14px | Body text in tables / lists, secondary labels |
| `text-base` | 16px | Default body — paragraph copy outside tables |
| `text-lg` | 18px | Card titles, sub-section headings |
| `text-xl` | 20px | Stat-card values, secondary page headings |
| `text-2xl` | 24px | **Page H1** (every admin page) |
| `text-3xl` | 30px | Hero stats (feedback page big number cards) |

### Bans

- ❌ `text-[10px]` — under WCAG comfortable-reading minimum (a11y #5)
- ❌ `text-[13px]` — between sm and base, no semantic role (a11y #6)
- ❌ `text-[26px]`, `text-[28px]` — replaced by `text-2xl` / `text-3xl`

### Font weights

| Class | Weight | Use for |
|---|---|---|
| `font-normal` | 400 | Body text |
| `font-medium` | 500 | Subtle emphasis |
| `font-semibold` | 600 | Stat labels, table column headers, filter pill text |
| `font-bold` | 700 | **Page H1**, primary action text |
| `font-extrabold` | 800 | Stat values (cards) |

`font-black` (900) deprecated — drops to `font-bold` for H1, kills
visual weight competition with the brand link colors.

## 3. Border radius ramp

Tailwind preset only. The `rounded-[Npx]` syntax is banned.

| Class | Computed | Use for |
|---|---|---|
| `rounded-sm` | `calc(var(--radius) - 4px)` ≈ 2px | Inset highlights |
| `rounded-md` | `calc(var(--radius) - 2px)` ≈ 4px | Inputs, badges, filter pills |
| `rounded-lg` | `var(--radius)` ≈ 6px | **Cards**, table containers, modal panels |
| `rounded-xl` | `calc(var(--radius) + 4px)` ≈ 10px | Hero panels, large stat cards |

### Bans

- ❌ `rounded-2xl` (16px) — only ever used in feedback page local Card; consolidate to `rounded-lg`
- ❌ `rounded-[10px]` — magic value; same as `rounded-xl` semantically

## 4. Spacing

Use the Tailwind 4-px grid (`p-1` = 4px, `p-2` = 8px, ...). The
arbitrary `p-[Npx]` syntax is banned for the same drift reason.

| Common pattern | Class | Use for |
|---|---|---|
| Page gutter | `p-6` (24px) | Outer page padding |
| Card padding | `p-4` (16px) | Stat cards, list cards |
| Card padding (large) | `p-5` (20px) | Hero cards, error / empty states |
| Cell padding | `p-3.5` (14px) | Table cells / headers |
| Stack gap | `gap-3` (12px) | Card grids, vertical lists |
| Inline gap | `gap-1.5` / `gap-2` | Badge icon + label, button + icon |

## 5. Shadows

Tailwind shadow scale + tokens defined in globals.css.

| Class | Use for |
|---|---|
| `shadow-sm` | Default card depth |
| `shadow` (default) | Hover state on interactive cards |
| `shadow-md` | Floating menus, dropdowns |
| `shadow-lg` | Modals, slide-overs |

## 6. Focus indicator

Globally enforced in `globals.css`:

```css
a:focus-visible,
button:focus-visible,
[role="button"]:focus-visible,
[tabindex]:not([tabindex="-1"]):focus-visible {
  @apply outline-none ring-2 ring-ring ring-offset-2 ring-offset-background;
}
```

Components opting into a custom focus state (e.g. `<Button>` cva
variants) override this naturally. Do NOT remove the rule from
globals — it's the safety net for every plain `<a className="no-
underline">` in the codebase.

Forced-colors mode (`@media (forced-colors: active)`) falls back to
the OS-drawn `outline: 2px solid CanvasText` so Windows High
Contrast users get a guaranteed-visible cue.

## 7. Component primitives in `components/ui/`

| Primitive | When to use |
|---|---|
| `<Button variant>` | Any clickable that performs an action (delete, submit, retry). |
| `<Card>` + `<CardHeader>` + `<CardTitle>` + `<CardContent>` | Any rectangular surface with a heading + body. **Stop reimplementing `<div className="rounded-xl border bg-card">`.** |
| `<Badge variant>` | Status / category chip. Locked variants pair color + leading icon for color-blind redundancy. |
| `<Table>` family + `<SortableHeader>` | Data tables. SortableHeader handles `aria-sort` + `scope="col"` automatically. |
| `<FilterTab>` | URL-driven toggle pill. Renders as `<a>`, NOT `<button>` — preserves filter state on refresh / share. |
| `<EmptyState>` | "No data" rows. Replaces ad-hoc `<td colSpan>` muted lines. |
| `<ErrorState>` | Server / network error UI. Replaces `common.error: <message>` divs. |

## 8. Migration notes

These are deliberately left for a follow-up cleanup commit so the
design-system pass commit stays scoped to *adding* the primitives + tokens, not rewriting every page that consumes them.

### `--dash-*` legacy aliases

10 files still reference `var(--dash-bg)` / `.dash-panel` / etc. The
aliases live at the bottom of `:root` and `.dark` blocks in
`globals.css`. Migration plan:

1. Replace `var(--dash-bg)` → `var(--background)` (etc.) in each
   page with a focused `Edit` pass per file.
2. Replace `<div className="dash-panel">` → `<Card>` from
   `components/ui/card.tsx`.
3. Delete the alias block from `globals.css` + the `.dash-panel`
   selector.
4. A sweep grep for `dash-` in PR review locks it down.

### Page rewrites pending

The audited 4 pages (`/admin/sessions`, `/admin/sessions/[id]`,
`/admin/analytics`, `/admin/feedback`) still inline:

- 3 different Card implementations
- 2 different StatCard implementations
- Hardcoded `<a>` filter pills (sessions)
- Manual `<table>` with raw `<th>` (sessions, analytics confusion table)
- Status badges with `bg-red-50/text-red-700` / `bg-green-100/text-green-800` patterns
- Empty-row `<td colSpan>` lines
- `common.error: <message>` divs

Each page gets its own focused refactor commit consuming the new
primitives. NOT done in this commit — the goal here is to land the
design system; consumption follows when Track A's new operator
surfaces (review queue, lead-link curate) are built **on the
primitives directly** (drift prevention). Existing pages can migrate
opportunistically.

### ESLint rule (deferred)

The bans in §2-4 are documented but not yet enforced. A future
commit should add to `eslint.config.mjs`:

```js
{
  files: ["app/**/*.{tsx,ts}", "components/**/*.{tsx,ts}"],
  rules: {
    "no-restricted-syntax": [
      "error",
      // Bans text-[Npx] / rounded-[Npx] / p-[Npx] / m-[Npx]
      {
        selector: "Literal[value=/(?:text|rounded|p[xytrbl]?|m[xytrbl]?)-\\[\\d+px\\]/]",
        message: "Arbitrary Tailwind values banned — use the documented ramp in dashboard/docs/DESIGN_TOKENS.md.",
      },
    ],
  },
}
```

Without ESLint enforcement the bans rely on PR review discipline.
That works for a small team but won't survive scale.
