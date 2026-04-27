# Dashboard Track A — Developer Handoff

**Audience**: dashboard developer who will build 4 new operator
pages backed by Track A's backend endpoints
([A0 commit](../../#) `1387daa`,
[A1](../../#) `3876da5`,
[A2](../../#) `3506c76`,
[A3](../../#) `546f4ab`).

**Pre-reqs landed in session 23**:
- Design tokens cleanup + 5 primitives (commit `edfe5bc`)
- A11y baseline + critique reports
  ([baseline](DASHBOARD_CRITIQUE_BASELINE.md),
  [a11y](DASHBOARD_ACCESSIBILITY_REVIEW.md))
- Token + ramp doc: [`dashboard/docs/DESIGN_TOKENS.md`](../../dashboard/docs/DESIGN_TOKENS.md)

**Constraint**: every interactive surface MUST consume the new
primitives. NO inline `<table>`, NO `<span className="bg-red-50
text-red-700">`, NO `text-[Npx]` magic numbers. Drift prevention is
the goal — Track A's pages must NOT recreate the patterns flagged in
the baseline. New pages set the standard older pages will migrate to.

---

## Conventions used throughout

### Auth headers (all admin endpoints)

The dashboard already has `requireAdmin()` (uses cookie / SSR check).
For Track A pages add a thin auth-aware fetch helper:

```text
fetch(path, {
  headers: {
    "x-admin-key":    <ADMIN_API_KEY>          // for super-admin pages (operators CRUD)
    "x-operator-key": <OPERATOR_API_KEY>       // for operator-tier pages (uploads, leads)
  }
})
```

The page's auth tier (super-admin vs operator) determines which
header gets sent. Both can be set when the operator is also using
ADMIN_API_KEY for testing — backend prefers `x-admin-key` if valid.

### Role-gated CTAs (operator pages)

The auth context (returned by `require_admin_or_operator()` on the
backend) carries `role`: `reviewer | manager | admin` plus
`is_super_admin`. The dashboard pages should fetch the operator's own
profile once on load (small endpoint or a bootstrap GET), cache it,
and gate UI accordingly. **Never rely on hiding-only-via-CSS** for
authorization — that's purely a UX nicety; backend role enforcement
is the actual gate.

| Capability | Min role |
|---|---|
| Read upload queue + lead links | `reviewer` |
| Review (PATCH `/uploads/{id}/review`) | `reviewer` |
| Curate lead uploads (PATCH `/leads/{id}/uploads`) | `manager` |
| Manage other operators | `super-admin` only |

### Copy strategy

- Primary language: **Türkçe** (operator team is TR-based)
- Fallback: English (already supported via `getText(locale, ...)`)
- New i18n keys: prefix `track_a.<page>.<key>` to avoid collision
  with existing `sessions.*` / `analytics.*` namespaces
- Empty / error states get the most translation effort — those are
  what an operator sees on a bad day

### Loading + error pattern

Every async surface uses:
- **Loading**: skeleton inside `<Card>` (no spinners on top of data
  — flash-on-refresh kills perceived performance)
- **Error**: `<ErrorState>` primitive (`role="alert"`)
- **Empty**: `<EmptyState>` primitive (`role="status"`)

Polling endpoints (upload queue showing in-flight items) refresh
every 5s **only when there's at least one row in `pending` or
`processing`** — full reload otherwise wastes Wiro quota.

### Page header pattern

Every Track A page uses this layout (replaces the inline header
divergence flagged in the baseline):

```text
┌──────────────────────────────────────────────────────────┐
│ Breadcrumb: Yönetim › <Page Title>                       │
│                                                          │
│  <H1 class=text-2xl font-bold>                  [CTA]    │
│  <Subtitle class=text-sm text-muted-foreground>          │
└──────────────────────────────────────────────────────────┘
```

H1 is `text-2xl font-bold` (NOT `text-[26px]` / NOT `font-black`).
CTA on the right is the page's primary action (e.g. "+ Yeni
operatör" on `/admin/operators`).

---

## Page 1 — `/admin/operators` (super-admin only)

### Overview

Super-admin manages dashboard operator accounts. Each operator gets
a per-user API key (shown ONCE on create) + a role
(reviewer/manager/admin). This page is the operations counterpart
to provisioning a new dashboard user.

**Auth**: `x-admin-key` only. Operator-tier keys hit 401 here even
if their role is `admin` (backend enforces — see `admin_operators_
api.py`).

### Layout (desktop, `>1024px`)

```text
┌────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Yönetim › Operatörler                              │
│                                                                │
│  Operatörler                                  [+ Yeni operatör]│
│  Dashboard erişimi olan kullanıcıları yönet               (CTA)│
│                                                                │
│  [Aktif] [Pasifleri göster]                                    │
│  ─────────────────────────────────────────────────────────────  │
│  ┌─ Card ──────────────────────────────────────────────────┐   │
│  │ E-posta              | Ad         | Rol     | Son işlem │   │
│  │ ──────────────────── | ────────── | ─────── | ───────── │   │
│  │ ops1@clinic.tr      | Ali Veli   | manager | [edit][⊘] │   │
│  │ rev2@clinic.tr      | …          | reviewer| [edit][⊘] │   │
│  │ admin@clinic.tr     | …          | admin   | [edit]    │   │
│  └────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Props | Notes |
|---|---|---|
| `<Breadcrumb>` | `items: [{label, href?}]` | Existing — `/admin/operators/...` paths |
| `<Button variant="default">` | `{children, onClick, asChild}` | "+ Yeni operatör" — opens create dialog |
| `<FilterTab tone="primary">` | `{href, active}` | Aktif (default) / Pasifleri göster |
| `<Table>` + `<SortableHeader>` | `sortKey="email"` etc., `current` + `order` from URL params, `hrefBuilder` | E-posta, Ad-soyad, Rol, Oluşturma tarihi, Son güncelleme |
| `<Badge variant>` | `variant="success"` for admin, `"warning"` for manager, `"info"` for reviewer | Role chips in the table |
| `<Button variant="ghost" size="sm">` | "Düzenle" + "Pasifleştir" inline actions | Per-row CTAs |
| `<Dialog>` (NEW — needs primitive) | Create + Edit modals | NOT in current primitive set; see "Open questions" |
| `<EmptyState>` | When no live operators | Title: "Operatör yok" / Sub: "+ Yeni operatör ile ekle" / Action: same CTA |

### Create operator flow

```text
Click [+ Yeni operatör]
  → Dialog opens (modal)
  → Form fields:
      - E-posta (required)         | text input
      - Ad-soyad (required)        | text input
      - Rol                        | <Select> reviewer | manager | admin
  → [Vazgeç]  [Oluştur]
  → On success (201):
      Dialog content REPLACES with success state:
        ┌─────────────────────────────────────────┐
        │ ✓ Operatör oluşturuldu                  │
        │                                         │
        │ Bu API anahtarını şimdi kopyalayın —    │
        │ daha sonra GÖRÜNTÜLEYEMEZSİNİZ.         │
        │                                         │
        │ ┌───────────────────────────────────┐   │
        │ │ a3f9b2c8d1e7...   [📋 Kopyala]    │   │
        │ └───────────────────────────────────┘   │
        │                                         │
        │ E-posta: ops1@clinic.tr                │
        │ Rol: reviewer                           │
        │                                         │
        │           [Anladım, kapat]              │
        └─────────────────────────────────────────┘
      Dialog stays open until "Anladım, kapat" — this prevents the
      operator from accidentally dismissing before saving the key.
      Closing also triggers a list refresh.
  → On 409 (email collision):
      Inline error below the email field:
        "Bu e-postayla aktif bir operatör zaten var. Önce
        pasifleştirin, sonra yeniden oluşturun."
  → On 422 (validation):
      Inline error per field; submit button stays disabled until
      every required field has a value.
```

### API contract

```text
GET /v1/admin/operators?include_deactivated=false
  Headers: x-admin-key: <ADMIN_API_KEY>
  Response 200:
    [
      {id, email, full_name, role, deactivated_at?, created_at, updated_at},
      ...
    ]
  401 -> redirect to /admin/login
  503 -> ErrorState ("Sunucu hazırlanıyor")

POST /v1/admin/operators
  Headers: x-admin-key, Content-Type: application/json
  Body:    {email, full_name, role}
  Response 201:
    {id, email, full_name, role, api_key, created_at}
              ^^^^^^^^^ plaintext, surfaced ONCE
  409 -> "Bu e-postayla aktif bir operatör zaten var..."
  422 -> per-field errors

PATCH /v1/admin/operators/{id}
  Headers: x-admin-key
  Body:    {full_name?: string, role?: "reviewer"|"manager"|"admin"}
  Response 200: row (no api_key)
  404 -> Toast "Operatör bulunamadı"
  422 -> per-field errors

DELETE /v1/admin/operators/{id}
  Headers: x-admin-key
  Response 204
  404 -> Toast "Operatör zaten pasif veya yok"
```

### Copy

| Key | Türkçe | English |
|---|---|---|
| `track_a.operators.title` | Operatörler | Operators |
| `track_a.operators.subtitle` | Dashboard erişimi olan kullanıcıları yönet | Manage dashboard users |
| `track_a.operators.cta_create` | + Yeni operatör | + New operator |
| `track_a.operators.tab_active` | Aktif | Active |
| `track_a.operators.tab_deactivated` | Pasifleri göster | Show deactivated |
| `track_a.operators.empty_title` | Operatör yok | No operators yet |
| `track_a.operators.empty_subtitle` | + Yeni operatör ile ilk kullanıcıyı ekle | + New operator to create the first user |
| `track_a.operators.col_email` | E-posta | Email |
| `track_a.operators.col_name` | Ad-soyad | Full name |
| `track_a.operators.col_role` | Rol | Role |
| `track_a.operators.col_created` | Oluşturma | Created |
| `track_a.operators.col_updated` | Son güncelleme | Last updated |
| `track_a.operators.action_edit` | Düzenle | Edit |
| `track_a.operators.action_deactivate` | Pasifleştir | Deactivate |
| `track_a.operators.dialog_create_title` | Yeni operatör oluştur | Create new operator |
| `track_a.operators.dialog_field_email` | E-posta | Email |
| `track_a.operators.dialog_field_name` | Ad-soyad | Full name |
| `track_a.operators.dialog_field_role` | Rol | Role |
| `track_a.operators.dialog_role_reviewer` | İnceleyici | Reviewer |
| `track_a.operators.dialog_role_manager` | Yönetici | Manager |
| `track_a.operators.dialog_role_admin` | Süper-yönetici | Admin |
| `track_a.operators.dialog_btn_cancel` | Vazgeç | Cancel |
| `track_a.operators.dialog_btn_create` | Oluştur | Create |
| `track_a.operators.dialog_success_title` | ✓ Operatör oluşturuldu | ✓ Operator created |
| `track_a.operators.dialog_key_warning` | Bu API anahtarını şimdi kopyalayın — daha sonra GÖRÜNTÜLEYEMEZSİNİZ. | Copy this API key now — you will NOT be able to view it again. |
| `track_a.operators.dialog_btn_copy` | 📋 Kopyala | 📋 Copy |
| `track_a.operators.dialog_btn_dismiss` | Anladım, kapat | Got it, close |
| `track_a.operators.error_email_collision` | Bu e-postayla aktif bir operatör zaten var. Önce pasifleştirin, sonra yeniden oluşturun. | A live operator with this email already exists. Deactivate first, then recreate. |
| `track_a.operators.confirm_deactivate` | "{email}" pasifleştirilsin mi? Mevcut anahtarı çalışmayı bırakır. | Deactivate "{email}"? Their current API key will stop working. |

### A11y annotations

- `<Dialog>` traps focus on open; `<Esc>` closes; restores focus to
  the triggering button on close
- Plaintext API key in the success state: visually rendered with
  `font-mono`, in a `<span role="textbox" aria-readonly="true">` so
  screen readers announce it as content (not as a label); the
  copy-to-clipboard button has `aria-label="API anahtarını kopyala"`
- Deactivate row action triggers a `<Confirm>` modal (NOT a JS
  `confirm()` — primitive needs adding); `aria-describedby` points
  to a paragraph with the impact statement
- Role select: `<select>` with `aria-label="Rol"`; once
  `<Select>` primitive lands, swap

### States

| State | Visual | Trigger |
|---|---|---|
| Default | Live operators table | Page load |
| Loading | Card skeleton (3 rows) | Initial fetch |
| Empty | `<EmptyState>` with create CTA | List returns `[]` |
| Error | `<ErrorState>` with retry | 5xx / network |
| Creating | Submit button shows spinner + disabled | POST in flight |
| Created (success) | Dialog flips to success state, shows api_key | 201 received |
| Updating | Row gets `bg-muted` while PATCH in flight | Inline edit save |
| Deactivating | Row fades + disabled | DELETE in flight |
| Deactivated | Row hidden (default) or shown muted (toggle on) | After 204 |

---

## Page 2 — `/admin/uploads` (operator review queue)

### Overview

The dashboard's "to-review" list. Operator filters by status / kind,
clicks into a row to review. **Highest-traffic page** post Track A
launch.

**Auth**: super-admin OR any operator role (reviewer minimum). Read-
only on this page; review actions land on the detail page.

### Layout

```text
┌────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Yönetim › Yüklemeler                               │
│                                                                │
│  Yüklemeler                                                    │
│  İncelenmeyi bekleyen hasta yüklemeleri                        │
│                                                                │
│  Filters:                                                      │
│   [Tümü] [Beklemede] [İşleniyor] [Başarılı] [Başarısız]        │
│   [Tüm türler] [Görsel] [Ses] [Video] [Belge]                  │
│   ☐ Pasifleştirilmişleri göster                                │
│                                                                │
│  ┌─ Card ──────────────────────────────────────────────────┐   │
│  │ Tarih ↓ | Tür   | AI Durum | İnceleme | Sağlayıcı | →   │   │
│  │ ────────|───────|──────────|──────────|───────────|──── │   │
│  │ 26 Apr  │ 🖼️ img │ ✓ ok    │ 🟡bekle │ moondream │ →   │   │
│  │ 26 Apr  │ 🎙️ aud │ ⏳ proc  │ —       │ whisper   │ →   │   │
│  │ 26 Apr  │ 📄 doc │ ✗ fail  │ 🔴 red   │ dots-ocr  │ →   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  Toplam: 134       [<<] [<] Sayfa 1 / 3 [>] [>>]               │
└────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Props | Notes |
|---|---|---|
| `<FilterTab tone="primary">` | Status filter (5 pills) | Tümü/Beklemede/İşleniyor/Başarılı/Başarısız |
| `<FilterTab tone="primary">` | Kind filter (5 pills) | Renders below status row, separate URL param |
| `<Checkbox>` (NEW) | `include_tombstoned` | NOT in primitives yet; minimal `<input type=checkbox>` for now |
| `<Table>` + `<SortableHeader>` | sortKey: `created_at` (default DESC), columns | "Tarih ↓ | Tür | AI Durum | İnceleme | Sağlayıcı | →" |
| `<Badge variant>` | per-status mapping (table 1 in the badge spec below) | Status + kind cells |
| `<EmptyState>` | When 0 results | "Eşleşen yükleme yok" |
| `<ErrorState>` | On 5xx | Retry returns to default filters |

#### Status badge mapping (memorize)

| Domain | `<Badge variant>` | Türkçe label |
|---|---|---|
| `ai_status=pending` | `neutral` | Beklemede |
| `ai_status=processing` | `info` | İşleniyor |
| `ai_status=succeeded` | `success` | Başarılı |
| `ai_status=failed` | `destructive` | Başarısız |
| `review_status=pending_review` | `warning` | İnceleme bekliyor |
| `review_status=approved` | `success` | Onaylandı |
| `review_status=rejected` | `destructive` | Reddedildi |
| `review_status=needs_followup` | `info` | Takip gerekli |
| `kind=image` | `default` w/ leading 🖼️ | Görsel |
| `kind=audio` | `default` w/ leading 🎙️ | Ses |
| `kind=video` | `default` w/ leading 🎞️ | Video |
| `kind=document` | `default` w/ leading 📄 | Belge |

### API contract

```text
GET /v1/admin/uploads?
    ai_status=pending|processing|succeeded|failed
    &kind=image|audio|video|document
    &session_id=<uuid>
    &created_after=<ISO>&created_before=<ISO>
    &include_tombstoned=true|false (default false)
    &limit=50  (1..200)
    &offset=0
  Headers: x-admin-key OR x-operator-key
  Response 200:
    {
      items: [
        {asset_id, session_id, ai_status, ai_provider, ai_result_text,
         ai_error, ai_latency_ms, upload_kind, content_type, size_bytes,
         consent_to_process, expires_at, created_at, processed_at,
         deleted_at, review_status, reviewer_notes, reviewed_at,
         reviewed_by},
        ...
      ],
      total: int,
      limit: int,
      offset: int
    }
  401 -> redirect to login
  422 -> validation (bad enum / out-of-range pagination)
```

### Polling rule

```js
// Pseudocode — concrete implementation up to dev
const hasInflight = items.some(
  i => i.ai_status === "pending" || i.ai_status === "processing"
);
if (hasInflight) {
  setTimeout(refetch, 5000);
}
```

Polling stops when every visible row is in a terminal state. Server
returns full snapshot — no diff endpoint needed at this scale.

### Copy

| Key | Türkçe | English |
|---|---|---|
| `track_a.uploads.title` | Yüklemeler | Uploads |
| `track_a.uploads.subtitle` | İncelenmeyi bekleyen hasta yüklemeleri | Pending patient uploads |
| `track_a.uploads.filter_status_all` | Tümü | All |
| `track_a.uploads.filter_status_pending` | Beklemede | Pending |
| `track_a.uploads.filter_status_processing` | İşleniyor | Processing |
| `track_a.uploads.filter_status_succeeded` | Başarılı | Succeeded |
| `track_a.uploads.filter_status_failed` | Başarısız | Failed |
| `track_a.uploads.filter_kind_all` | Tüm türler | All kinds |
| `track_a.uploads.filter_kind_image` | Görsel | Image |
| `track_a.uploads.filter_kind_audio` | Ses | Audio |
| `track_a.uploads.filter_kind_video` | Video | Video |
| `track_a.uploads.filter_kind_document` | Belge | Document |
| `track_a.uploads.toggle_show_tombstoned` | Pasifleştirilmişleri göster | Show tombstoned |
| `track_a.uploads.col_date` | Tarih | Date |
| `track_a.uploads.col_kind` | Tür | Kind |
| `track_a.uploads.col_ai_status` | AI Durum | AI status |
| `track_a.uploads.col_review_status` | İnceleme | Review |
| `track_a.uploads.col_provider` | Sağlayıcı | Provider |
| `track_a.uploads.action_view` | Aç | View |
| `track_a.uploads.empty_title` | Eşleşen yükleme yok | No matching uploads |
| `track_a.uploads.empty_subtitle` | Filtreleri değiştirin veya yeni hasta yüklemesi bekleyin | Adjust filters or wait for new patient uploads |
| `track_a.uploads.pagination_total` | Toplam: {count} | Total: {count} |

### Loading + empty + error states

```text
Loading (initial fetch):
  ┌─ Card ──────────────────────────────────────┐
  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ (5 row skeletons)
  └──────────────────────────────────────────────┘

Empty:
  <EmptyState
    icon={<Inbox/>}
    title="Eşleşen yükleme yok"
    description="Filtreleri değiştirin veya yeni hasta yüklemesi bekleyin"
    action={<Button variant="ghost" asChild><a href="?">Filtreleri sıfırla</a></Button>}
  />

Error:
  <ErrorState
    title="Yüklemeler yüklenemedi"
    message="Sunucuyla bağlantı kurulamadı veya geçici bir sorun oluştu."
    retryHref={pathname + searchParams}  // re-render same URL
    hint={<>Sorun devam ederse <a href="/admin/status">/admin/status</a>'e bakın.</>}
  />
```

### A11y annotations

- Filter pills: `<FilterTab>` already sets `aria-current="page"` on
  active; URL-driven so back-button works
- Sortable headers: `<SortableHeader>` already sets `aria-sort` +
  `scope="col"` (handled by primitive)
- Polling: while polling is active, render a visually-hidden
  `<span role="status" aria-live="polite">İşleniyor: 3 yükleme</span>`
  so SR users hear updates without spam (debounced — only announces
  when the count changes)
- Pagination buttons: `aria-label="Önceki sayfa"` / `"Sonraki sayfa"`
  (numbers alone are ambiguous to SR)

### States

| State | Visual | Trigger |
|---|---|---|
| Default | Filter row + table + pagination | Page load |
| Loading | Skeleton table inside Card | Initial fetch / filter change |
| Empty | EmptyState | 0 results matching filter |
| Error | ErrorState | 5xx / network |
| Polling | Subtle pulse on rows in pending/processing status | hasInflight=true |
| Filter change | URL params update, list re-fetches with skeleton | Click any FilterTab / checkbox |

---

## Page 3 — `/admin/uploads/[asset_id]` (review action)

### Overview

Single-asset detail + review action form. Operator reads the AI
output, sees the dispatcher metadata, sets a `review_status`, leaves
notes.

**Auth**: super-admin OR operator with role >= reviewer. Form shown
to all roles >= reviewer; super-admin authed requests record
`reviewed_by="admin"`, operator authed records the operator's
email.

### Layout

```text
┌────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Yönetim › Yüklemeler › <asset_id>                  │
│                                                                │
│  Yükleme — <kind chip> <ai_status badge>                       │
│  Asset {asset_id} • Oluşturma 26 Apr 2026 14:23                │
│                                                                │
│  ┌─ Card "AI Sonucu" ──────────────────────────────────────┐   │
│  │ Sağlayıcı: moondream:hair_loss_norwood                  │   │
│  │ Süre: 4.5s                                              │   │
│  │                                                         │   │
│  │ {                                                       │   │
│  │   "norwood_stage": 3,                                   │   │
│  │   "density_observed": "diffuse thinning at crown",      │   │
│  │   ...                                                   │   │
│  │ }                                                 [📋]  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─ Card "Yükleme bilgisi" ────────────────────────────────┐   │
│  │ Tür: Görsel (image/png)                                 │   │
│  │ Boyut: 2.4 MB                                           │   │
│  │ Onay: ✓ Hasta tarafından onaylandı                      │   │
│  │ Onay metni: "Saç ekimi öncesi Norwood değerlendirmesi"  │   │
│  │ Hasta seansı: <Link to /admin/sessions/{id}>            │   │
│  │ Son tarih: 26 May 2026                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─ Card "İnceleme" ───────────────────────────────────────┐   │
│  │                                                         │   │
│  │ Mevcut durum: <Badge variant=warning>İnceleme bekliyor</│   │
│  │                                                         │   │
│  │ Yeni durum:                                             │   │
│  │   ◯ İnceleme bekliyor                                   │   │
│  │   ◯ Onaylandı                                           │   │
│  │   ◉ Takip gerekli                                       │   │
│  │   ◯ Reddedildi                                          │   │
│  │                                                         │   │
│  │ Notlar (op):                                            │   │
│  │ ┌─────────────────────────────────────────────────────┐ │   │
│  │ │ Hasta tekrar fotoğraf göndersin — açı yetersiz.    │ │   │
│  │ └─────────────────────────────────────────────────────┘ │   │
│  │ 156 / 2000 karakter                                     │   │
│  │                                                         │   │
│  │ Son inceleme: doctor@clinic.tr • 26 Apr 2026 15:01      │   │
│  │                                                         │   │
│  │                              [Vazgeç]   [Kaydet]        │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Props | Notes |
|---|---|---|
| `<Card>` family | 3 cards: AI Sonucu, Yükleme bilgisi, İnceleme | Each `<CardHeader>` + `<CardContent>` |
| `<Badge variant>` | Per kind / ai_status / review_status | All chips |
| `<pre>` w/ wrapper | AI output JSON. Wrap in `role="region" aria-label="AI çıktısı"` (a11y review #8) | Copy-to-clipboard button on the card header |
| Button "Kopyala" | `<Button variant="ghost" size="icon">` | Top-right of AI output card |
| `<RadioGroup>` (NEW) | NOT in primitives yet — use 4 native `<label><input type="radio">` for now | review_status options |
| `<Textarea>` (NEW) | NOT in primitives yet — use native `<textarea>` w/ Tailwind for now | reviewer_notes |
| `<Button variant="outline">` | "Vazgeç" — navigates back to /admin/uploads with preserved filters | Cancel |
| `<Button variant="default">` | "Kaydet" — disabled until form dirty | Submit |

### API contract

```text
GET /v1/admin/uploads/<asset_id>
  -> NOT a separate endpoint. Use the row from the queue list OR
     filter by session_id=<asset_id>... actually backend doesn't
     have a single-asset GET. Two choices:
        (a) [Pragmatic] add GET /v1/admin/uploads/{asset_id} backend-
            side as a small follow-up commit before this page lands
        (b) [Workaround] call GET /v1/admin/uploads?session_id=...
            with appropriate filter and pick the matching row

  → DECISION pending: see "Open questions" below.
  → For this handoff, assume option (a): backend will add it.

PATCH /v1/admin/uploads/{asset_id}/review
  Headers: x-admin-key OR x-operator-key, Content-Type: application/json
  Body:
    {
      review_status: "pending_review"|"approved"|"rejected"|"needs_followup",
      reviewer_notes: string (optional, max 2000)
    }
  Response 200: full updated row (same shape as queue items)
  401 -> redirect to login
  403 -> Toast "Bu işlem için yetkiniz yok" (operator below reviewer
        — defensive; reviewer is the lowest tier so this should be
        rare)
  404 -> ErrorState ("Yükleme bulunamadı veya pasifleştirilmiş")
  422 -> Per-field error
```

### Form behavior

- Initial state: `review_status` = current value from row, notes
  field pre-filled
- Form is "dirty" when any field differs from initial → "Kaydet"
  enables
- On successful save: optimistic UI update (badge flips immediately,
  notes persist), then re-fetch to confirm; on error: revert + show
  inline error
- "Vazgeç" returns to `/admin/uploads` with the previously-active
  filter URL preserved (use `useSearchParams()` or pass as query)

### Copy

| Key | Türkçe | English |
|---|---|---|
| `track_a.upload_detail.title` | Yükleme | Upload |
| `track_a.upload_detail.section_ai` | AI Sonucu | AI result |
| `track_a.upload_detail.section_metadata` | Yükleme bilgisi | Upload info |
| `track_a.upload_detail.section_review` | İnceleme | Review |
| `track_a.upload_detail.label_provider` | Sağlayıcı | Provider |
| `track_a.upload_detail.label_latency` | Süre | Latency |
| `track_a.upload_detail.label_kind` | Tür | Kind |
| `track_a.upload_detail.label_size` | Boyut | Size |
| `track_a.upload_detail.label_consent` | Onay | Consent |
| `track_a.upload_detail.consent_yes` | ✓ Hasta tarafından onaylandı | ✓ Patient consented |
| `track_a.upload_detail.label_consent_text` | Onay metni | Consent context |
| `track_a.upload_detail.label_session` | Hasta seansı | Patient session |
| `track_a.upload_detail.label_expires` | Son tarih | Expires |
| `track_a.upload_detail.label_current_status` | Mevcut durum | Current status |
| `track_a.upload_detail.label_new_status` | Yeni durum | New status |
| `track_a.upload_detail.status_pending` | İnceleme bekliyor | Pending review |
| `track_a.upload_detail.status_approved` | Onaylandı | Approved |
| `track_a.upload_detail.status_rejected` | Reddedildi | Rejected |
| `track_a.upload_detail.status_followup` | Takip gerekli | Needs follow-up |
| `track_a.upload_detail.label_notes` | Notlar (op) | Operator notes |
| `track_a.upload_detail.label_last_review` | Son inceleme | Last reviewed |
| `track_a.upload_detail.btn_cancel` | Vazgeç | Cancel |
| `track_a.upload_detail.btn_save` | Kaydet | Save |
| `track_a.upload_detail.btn_copy_ai` | Kopyala | Copy |
| `track_a.upload_detail.toast_saved` | İnceleme kaydedildi | Review saved |
| `track_a.upload_detail.error_save` | Kaydedilemedi: {message} | Save failed: {message} |
| `track_a.upload_detail.notes_char_count` | {count} / 2000 karakter | {count} / 2000 characters |

### A11y annotations

- AI output `<pre>` wrapped in `<section role="region"
  aria-label="AI çıktısı (ham)">` (a11y review #8)
- Copy-to-clipboard button: `aria-label="AI çıktısını kopyala"` +
  toast "Panoya kopyalandı" on success (live region)
- RadioGroup: each `<label>` wraps `<input type="radio"
  name="review_status">` so click on label toggles input; `<fieldset>`
  + `<legend>` for SR grouping
- Notes `<textarea>`: `aria-describedby` points to the char-count
  span; visually-hidden status updates char count for SR
- Form submission: `<form onSubmit={...}>`; Enter inside notes does
  NOT submit (prevent accidental save while editing)
- Save button: `aria-busy="true"` while in flight
- Toast on success: `role="status"` aria-live="polite"; on error:
  `role="alert"` aria-live="assertive"

### States

| State | Visual | Trigger |
|---|---|---|
| Default | Form pre-filled, save disabled | Page load |
| Loading | Skeleton on each Card | Initial fetch |
| 404 | ErrorState ("Yükleme bulunamadı...") with link back to queue | GET returns 404 / row tombstoned |
| Dirty | Save enabled, "Vazgeç" focuses on confirm if dirty | User types in notes / changes radio |
| Saving | Save button spinner + disabled, form fields disabled | PATCH in flight |
| Saved | Toast success + form re-renders fresh row | 200 |
| Error | Inline error below form + Save re-enabled | 4xx/5xx |

---

## Page 4 — `/admin/leads/[lead_id]/uploads` (lead-link curate)

### Overview

Operator's lead detail surface (subset). Shows the lead's currently-
linked uploads, plus a "select more" panel to add/remove. Save flips
the link set with replace semantics + atomic precheck.

**Auth**: GET reviewer+; PATCH manager+. Reviewer-tier sees the
current links (read-only); manager-tier sees the editable form.

### Layout

```text
┌────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Yönetim › Lead'ler › <lead_id> › Yüklemeler        │
│                                                                │
│  Lead {lead_id} — Bağlı Yüklemeler                             │
│  Bu lead için inceleme dosyalarını seç                         │
│                                                                │
│  ┌─ Card "Şu an bağlı (3)" ────────────────────────────────┐   │
│  │ ✓ A1 — Görsel — Norwood 3 — onaylandı   [Çıkar]         │   │
│  │ ✓ A2 — Belge — lab sonucu — bekliyor    [Çıkar]         │   │
│  │ ✓ A3 — Ses  — voice memo — başarısız    [Çıkar]         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─ Card "Mevcut yüklemelerden bağla" ────────────────────┐   │
│  │ Ara: [_____________] (asset_id, session_id, prompt...)  │   │
│  │                                                         │   │
│  │ ☐ A4 — Görsel — Norwood 5 — bekliyor                    │   │
│  │ ☐ A5 — Video — saç klibi — başarılı                     │   │
│  │ ☐ A6 — Belge — sigorta belgesi — bekliyor               │   │
│  │ ...                                                     │   │
│  │                                                         │   │
│  │ Sayfa 1/8                                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─ Diff özeti (kaydet öncesi) ──────────────────────────┐    │
│  │  Eklenecek: A4, A5  •  Çıkarılacak: A3                │    │
│  │                          [Vazgeç]   [Değişiklikleri kaydet] │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

The "Diff özeti" card is **sticky bottom** when any change exists in
the working set (visual diff between current backend state and
operator's selection). Hidden when working set == backend state.

### Components

| Component | Props | Notes |
|---|---|---|
| `<Card>` × 3 | "Şu an bağlı", "Bağla", "Diff özeti" | |
| `<Button variant="ghost" size="sm">` | "Çıkar" inline action | Removes from working set (does NOT call API yet) |
| `<input type="search">` | Search box | Filters the available list (debounced 250ms) |
| `<Checkbox>` (NEW primitive needed) | Per available row | Adds to working set |
| `<Badge variant>` | kind + ai_status + review_status chips per row | Same mapping as queue page |
| `<Button variant="outline">` | "Vazgeç" — discards working set | |
| `<Button variant="default">` | "Değişiklikleri kaydet" | Disabled when no diff |

### State machine (client-side working set)

```text
backend_links = [A1, A2, A3]        // from GET on load
working_set   = [A1, A2, A3]        // initial copy

User clicks "Çıkar A3"      → working_set = [A1, A2]
User checks A4              → working_set = [A1, A2, A4]
User checks A5              → working_set = [A1, A2, A4, A5]

diff = {
  added:   [A4, A5],
  removed: [A3],
  kept:    [A1, A2],
  current: working_set,
}

PATCH .../uploads with { asset_ids: working_set }
  → On 200: backend_links = response.current
            working_set = response.current
            "Diff özeti" hides
  → On 422 (one of working_set is tombstoned/missing):
            inline error listing the bad asset_ids
            working_set unchanged so user can fix
```

### API contract

```text
GET /v1/admin/leads/{lead_id}/uploads
  Headers: x-admin-key OR x-operator-key
  Response 200: list of link rows
    [{id, lead_id, asset_id, linked_at, linked_by_operator_id}, ...]
  404 -> ErrorState ("Lead bulunamadı")

PATCH /v1/admin/leads/{lead_id}/uploads
  Headers: x-admin-key OR x-operator-key (manager+ only)
  Body:    { asset_ids: ["A1", "A4", ...] } (max 100)
  Response 200:
    { added: [...], removed: [...], kept: [...], current: [...] }
  404 -> "Lead bulunamadı"
  403 -> "Manager rolü gerekli"
  422 -> "Bilinmeyen veya pasifleştirilmiş asset_id'ler: [..]"
```

### Available uploads search (server vs client)

For the "Bağla" card's available list, two implementations:

**MVP (recommended)**: just paginate `/admin/uploads` with no
session-id filter, render its rows with checkboxes. Operator
manually scrolls to find candidates. Cap at 50/page.

**v2 (deferred)**: add a `?search=<term>` query param to backend
`/admin/uploads` matching against `asset_id`, `session_id`,
`ai_result_text` (PII-safe — already in DB). Out-of-scope for this
handoff.

### Copy

| Key | Türkçe | English |
|---|---|---|
| `track_a.lead_uploads.title` | Bağlı Yüklemeler | Linked Uploads |
| `track_a.lead_uploads.subtitle` | Bu lead için inceleme dosyalarını seç | Select review files for this lead |
| `track_a.lead_uploads.section_current` | Şu an bağlı ({count}) | Currently linked ({count}) |
| `track_a.lead_uploads.section_available` | Mevcut yüklemelerden bağla | Link from available uploads |
| `track_a.lead_uploads.section_diff` | Değişiklik özeti | Change summary |
| `track_a.lead_uploads.action_remove` | Çıkar | Remove |
| `track_a.lead_uploads.search_placeholder` | asset_id, session_id, AI çıktısı… | asset_id, session_id, AI output… |
| `track_a.lead_uploads.diff_added` | Eklenecek: {ids} | Will add: {ids} |
| `track_a.lead_uploads.diff_removed` | Çıkarılacak: {ids} | Will remove: {ids} |
| `track_a.lead_uploads.btn_save` | Değişiklikleri kaydet | Save changes |
| `track_a.lead_uploads.btn_cancel` | Vazgeç | Cancel |
| `track_a.lead_uploads.empty_current_title` | Henüz bağlı yükleme yok | No uploads linked yet |
| `track_a.lead_uploads.empty_current_sub` | Aşağıdan dosya seçerek başla | Pick a file from below to get started |
| `track_a.lead_uploads.confirm_discard` | Kaydedilmemiş değişiklikleri at? | Discard unsaved changes? |
| `track_a.lead_uploads.error_invalid_assets` | Şu asset'ler eklenemedi (silinmiş veya bilinmiyor): {ids} | Couldn't link these assets (deleted or unknown): {ids} |
| `track_a.lead_uploads.role_required` | Bu işlem yönetici (manager) rolü gerektirir | This action requires manager role |

### A11y annotations

- Checkboxes in the available list: each wrapped in `<label>` with
  the row content; native `<input type="checkbox">` until primitive
  lands; `aria-checked` follows native state
- Diff summary card: `role="region" aria-label="Değişiklik özeti"`;
  on first appearance announces via live region "{count} değişiklik
  bekliyor"
- "Çıkar" buttons: `aria-label="A3'ü bağlantıdan çıkar"` (inserts
  the asset id so SR distinguishes between same-named buttons in a
  list)
- Search box: `<label>` with text "Mevcut yüklemelerde ara";
  debounced filter announces "{count} sonuç" via live region after
  type stops
- "Vazgeç" prompt: native `<dialog>` or `<Confirm>` (when primitive
  lands); focus traps and restores
- "Kaydet" button: `aria-busy="true"` while PATCH in flight; on
  error keeps focus on the button (don't move the user mid-action)

### States

| State | Visual | Trigger |
|---|---|---|
| Initial load | Skeleton both cards | GET in flight |
| Lead 404 | ErrorState | GET returns 404 |
| Reviewer role (read-only) | Cards rendered without checkboxes / Çıkar buttons; "Diff" card hidden | role < manager |
| Default (manager) | Both cards interactive, "Diff" hidden | working_set == backend_links |
| Dirty | "Diff" card slides in (sticky bottom) | Any add/remove |
| Saving | Save button spinner; cards disabled | PATCH in flight |
| Saved | Toast success; "Diff" hides; backend_links updates | 200 |
| Save error | Inline error in "Diff" card; working set unchanged | 422 / 5xx |

---

## Shared: layout sidebar (separate commit, blocks Track A pages from inheriting drift)

The baseline flagged: every page repeats hardcoded cross-link
header. Track A's 4 new pages need a sidebar OR they'll inherit
the drift. Recommended structure for `app/admin/layout.tsx`:

```text
┌──┬──────────────────────────────────────────────────────────┐
│  │ <existing sticky header: locale + theme>                 │
│  ├──────────────────────────────────────────────────────────┤
│SB│                                                          │
│  │   <page content (this is where {children} renders)>      │
│  │                                                          │
│  │                                                          │
└──┴──────────────────────────────────────────────────────────┘

SB (sidebar) — sticky left, fixed-width 240px:
  📊 Analitik          /admin/analytics
  💬 Geri bildirim     /admin/feedback
  📋 Seanslar          /admin/sessions
  ─────────────────
  📤 Yüklemeler        /admin/uploads          ← Track A
  👤 Operatörler       /admin/operators        ← Track A (super-admin only)
  ─────────────────
  🏥 Lead'ler          /admin/leads
  🔧 Tuning            /admin/tuning-tasks
  📈 Live              /admin/live
  ⚙️  Status            /admin/status
```

Active route: `bg-accent text-accent-foreground` + leading icon
darker. Mobile (< 768px): collapse to top nav (deferred — operator
team uses desktop primarily).

This sidebar lands as a **separate commit before the page
implementations** so Track A's pages can rely on it being there.
Pre-existing pages can keep their current header until they're
migrated (deferred drift cleanup).

---

## Open questions / unresolved decisions

1. **Single-asset GET endpoint** — the upload detail page (Page 3)
   needs `GET /v1/admin/uploads/{asset_id}`. Backend currently only
   has `GET /v1/admin/uploads` (queue). Two options:
   - **Add it before page 3 implementation** (recommended — small
     1-commit backend addition)
   - **Workaround**: filter the queue list by asset_id-as-session_id
     (hack; doesn't work cleanly because session can have multiple
     uploads)

2. **Dialog primitive** — the operators page (Page 1) needs
   `<Dialog>` (radix-ui's `@radix-ui/react-dialog`). Currently only
   `@radix-ui/react-slot` is in `package.json`. Add as part of a
   primitive-batch follow-up commit.

3. **Select primitive** — the operators create form has a role
   `<Select>`. Use native `<select>` until `@radix-ui/react-select`
   primitive lands; visually a step down but functional.

4. **Checkbox primitive** — the lead-uploads page (Page 4) and the
   uploads queue page (Page 2 — `include_tombstoned`) need
   `<Checkbox>`. Use native `<input type="checkbox">` for MVP.

5. **Confirm primitive** — Several places use confirmation modals
   (deactivate operator, discard unsaved changes). Same dependency
   chain as `<Dialog>`. Use native `confirm()` for MVP IF the
   confirmation isn't critical; for the ones that ARE
   (discard-unsaved with substantive work), block on the Dialog
   primitive landing.

6. **Toast primitive** — Many states announce success/error via
   toast. Native browser alerts are inappropriate. Options:
   `sonner` library (lightweight, ~3KB) OR build a minimal toast
   primitive. Defer decision; for MVP, render success messages
   inline (next to the button that triggered them).

7. **Operator profile bootstrap** — Page-level role gating needs the
   operator's own role. Two implementations:
   - Backend adds `GET /v1/admin/me` returning the auth context
   - Each page reads operator info from a cookie set at login

   The latter is faster but ties role to login; the former survives
   role changes mid-session. Recommended: add `GET /v1/admin/me`.

---

## Implementation sequence (recommended order)

Each step lands as its own commit so the drift-prevention discipline
holds:

1. **Backend follow-ups** (1-2 commits, ~100 lines):
   - `GET /v1/admin/uploads/{asset_id}` (single-row read)
   - `GET /v1/admin/me` (auth context echo for role gating)

2. **`app/admin/layout.tsx` sidebar** (1 commit, ~150 lines):
   - Layout component + 9 nav links
   - Active-route highlighting
   - i18n keys for nav labels

3. **`/admin/operators`** (1 commit, ~400 lines):
   - List page + create / edit / deactivate flows
   - Native `<dialog>` + `<select>` until primitives land
   - 12 i18n keys

4. **`/admin/uploads`** (1 commit, ~350 lines):
   - Queue + filter + pagination + polling
   - 18 i18n keys

5. **`/admin/uploads/[asset_id]`** (1 commit, ~300 lines):
   - Detail + review form
   - 22 i18n keys

6. **`/admin/leads/[lead_id]/uploads`** (1 commit, ~400 lines):
   - Curate + diff
   - 16 i18n keys

7. **Primitive batch** (1 commit, ~600 lines):
   - `<Dialog>`, `<Select>`, `<Checkbox>`, `<Confirm>`, `<Toast>`
   - Migrate the four pages above to consume them
   - This is intentionally LAST so each page's MVP form is tested
     before the primitive layer locks in

Total: ~7 commits, ~2,300 lines of dashboard code + ~100 lines of
backend follow-ups. **Do NOT bundle pages together** — each one is
a focused review surface.

---

## What you should NOT do

- ❌ Reach for `bg-red-50 text-red-700` (or any raw Tailwind palette).
  Use `<Badge variant>` instead.
- ❌ Inline `<table>` markup. Use `<Table>` + `<SortableHeader>`.
- ❌ Use `text-[Npx]` / `rounded-[Npx]` arbitrary values. Pick from
  the ramp in [`DESIGN_TOKENS.md`](../../dashboard/docs/DESIGN_TOKENS.md).
- ❌ Re-implement empty / error / loading states. Use the primitives.
- ❌ Hide the api_key plaintext in logs / Sentry breadcrumbs / URL
  params. It's shown ONCE in the success dialog and never again.
- ❌ Cache the operator role in localStorage. It's session-scoped;
  re-fetch on each page mount via `GET /v1/admin/me`.
- ❌ Optimistic update on lead-link save (Page 4). The diff endpoint
  is atomic — wait for the response, THEN apply. Optimism here can
  lead to silent data loss if the server rejects.
