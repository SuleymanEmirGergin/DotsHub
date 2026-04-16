# tenant_id migration (20260306)

Bu migration, multi-tenant Faz 1 için `triage_sessions`, `triage_events`, `triage_feedback` ve (varsa) `tuning_tasks` tablolarına `tenant_id` sütununu ekler.

## Dosya

- **Backend:** `backend/sql/20260306_add_tenant_id.sql`

## Çalıştırma

### 1) Supabase Dashboard (SQL Editor)

1. [Supabase Dashboard](https://supabase.com/dashboard) → projenizi seçin.
2. **SQL Editor** → **New query**.
3. `backend/sql/20260306_add_tenant_id.sql` içeriğini yapıştırın.
4. **Run** ile çalıştırın.

### 2) psql ile

```bash
# Bağlantı bilgisini Supabase proje ayarlarından alın (Database → Connection string, URI)
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres" -f backend/sql/20260306_add_tenant_id.sql
```

### 3) Supabase CLI

```bash
supabase db execute -f backend/sql/20260306_add_tenant_id.sql
# veya remote proje için:
supabase link --project-ref [PROJECT_REF]
supabase db push  # migration'ları link'lenmiş projeye uygular (migrations klasörü kullanılıyorsa)
```

Not: `db push` genelde `supabase/migrations/` altındaki dosyaları kullanır. Bu tek seferlik migration’ı doğrudan çalıştırmak için `supabase db execute` veya SQL Editor kullanın.

## Ne yapar?

- `triage_sessions`, `triage_events`, `triage_feedback`: `tenant_id text not null default 'default'` eklenir, mevcut satırlar `'default'` yapılır, index eklenir.
- `tuning_tasks` tablosu varsa: aynı şekilde `tenant_id` ve index eklenir.

## Sonrası

- Backend zaten `tenant_id` ile insert/filter yapıyor; migration sonrası uygulama aynı şemayla çalışır.
- Yeni deploy öncesi bu migration’ı çalıştırmak yeterlidir.
