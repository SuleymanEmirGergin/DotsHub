# Veri Saklama Politikası — Retention Policy

Compliance lineage: `COMPLIANCE_CHECK_2026_04.md:KR-3`. Risk: `RISK_REGISTER_2026_04.md:H-2`.

KVKK Madde 7 + GDPR Art. 5(1)(e) gereği saklama süreleri tanımlı, sınırlı, ve gerekçelendirilmiş olmalıdır. Bu doküman ürünün her veri kategorisi için saklama süresini, hukuki gerekçeyi ve teknik uygulamayı belirler.

> Aydınlatma metninin (KR-2) ve veri sahipleri başvurularının cevabında bu sayılar referans alınır. Sayıları değiştirmek = aydınlatma metnini güncellemek.

---

## Saklama tablosu

| Veri kategorisi | Tablo / kaynak | Saklama süresi | Hukuki gerekçe | Teknik uygulama |
|---|---|---|---|---|
| Triage oturumu (içerik) | `triage_sessions.input_text/answers/...` | **90 gün** sonra **tombstone**; **180 gün** sonra **fully purge** | KVKK Md.7(1): "amaca uygun + gerekli süre". Pre-triage kararı kullanıcıya verildikten sonra kalıcı klinik değer yok. | `app_retention_purge()` SQL fonksiyonu — content kolonlarını NULL'a çeker (mevcut tombstone pattern), 180 gün sonra row'u DELETE eder |
| Triage olay logu | `triage_events` | **90 gün** | Audit + hata ayıklama için makul pencere. Daha uzun saklamak klinik değer yaratmıyor. | `DELETE WHERE created_at < NOW() - 90 days` |
| LLM çağrı logu | `llm_calls` | **30 gün** | LLM çıktıları yüksek hassasiyetli (semptom + system prompt + response). En kısa pencere. | `DELETE WHERE created_at < NOW() - 30 days` |
| Geri bildirim | `triage_feedback` | **365 gün** | Tuning loop için trend analizi (kalite ölçümü). Anonim (session_id ile linkli ama tombstone sonrası session içeriği yok). | `DELETE WHERE created_at < NOW() - 365 days` |
| Push token | `push_tokens` | **90 gün inactive** sonra sil | Token cihaza özel; uzun süre kullanılmıyorsa cihaz değişmiş veya app silinmiştir. | `DELETE WHERE updated_at < NOW() - 90 days` |
| IP hash (oturum metadata) | `triage_sessions.meta` | Oturumla aynı (90/180 gün) | Hash + salt ile, ham IP saklanmıyor. Oturumla aynı pencerede silinir. | Tombstone + purge ile birlikte gider |
| Audit log (admin işlem) | `tenant_catalog_audit` | **730 gün (2 yıl)** | İdari soruşturma + denetim ihtiyacı. Kişisel veri içermez (admin user_id + işlem türü). | Manuel review — cron tarafından temizlenmez |
| WORM audit log (forensik) | `audit_log` | **730 gün (2 yıl)** | KVKK Md.12 (güvenlik + ihlal kanıtı) + GDPR Art.30 (records of processing). PII içermez (ip_hash + UUID actor/target). | DB-level UPDATE/DELETE yasağı (trigger); `app_retention_purge` bu tabloya dokunmaz; bkz. `backend/sql/20260427_audit_log.sql`. Quarterly review için ayrı arama. |
| E-posta gönderim logları | (Resend tarafında) | 30 gün max | Resend dashboard config; webhook event'leri saklanmıyor (uçtan uca pass-through). | Resend retention config |
| Sentry breadcrumb / event | (Sentry tarafında) | 90 gün (Sentry default) | Hata gözlem; PII masking aktif. | Sentry org config |

**Tombstone** = içerik kolonları NULL, `deleted_at` set; `id` + `created_at` kalır (analitik join'leri kırmamak için). Bkz: `backend/sql/20260418_session_tombstone.sql`.

---

## Backup retention

Supabase backup'ları silinmiş veriyi kapsayabilir. Politika:

- Supabase otomatik backup retention: **maksimum 30 gün** (Pro plan default + manuel ayar).
- KVKK / GDPR perspektifinden: aydınlatma metninde "silinme talebiniz backup arşivinden 30 gün içinde tamamlanır" ifadesi gerekli.
- Point-in-time recovery: erasure talebinden sonra restore yapılırsa silinmiş veri geri gelebilir; ops protokolü: restore sonrası `app_retention_purge()` derhal çalıştır.

---

## Yapılandırma

Backend `app/core/config.py`:

```python
RETENTION_DAYS_SESSIONS_TOMBSTONE = 90    # tombstone window
RETENTION_DAYS_SESSIONS_PURGE     = 180   # full delete window
RETENTION_DAYS_EVENTS             = 90
RETENTION_DAYS_LLM_CALLS          = 30
RETENTION_DAYS_FEEDBACK           = 365
RETENTION_DAYS_PUSH_TOKENS        = 90
RETENTION_DAYS_AUDIT              = 730
```

Env ile override edilebilir (örn. dev ortamında daha kısa: `RETENTION_DAYS_LLM_CALLS=7`).

---

## Çalıştırma — 3 seçenek

### A. Supabase pg_cron (önerilen)

Supabase'te `pg_cron` extension'ı etkinleştirilebilir. Günde 1 kez:

```sql
select cron.schedule(
    'app_retention_daily',
    '0 3 * * *',  -- her gün 03:00 UTC
    $$select public.app_retention_purge()$$
);
```

Avantaj: dış bağımlılık yok, downtime'a dayanıklı, audit log Postgres'te.
Dezavantaj: parametre değişiklikleri için SQL function güncellenmeli.

### B. GitHub Actions cron

Mevcut workflow paterni (alerts, kaggle ingest):

```yaml
# .github/workflows/retention-purge.yml
on:
  schedule:
    - cron: "0 3 * * *"
jobs:
  purge:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python backend/scripts/run_retention_purge.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
```

Avantaj: parametre olarak `RETENTION_DAYS_*` env'den okunur, dry-run desteği var.
Dezavantaj: GH Actions outage bir günü kaçırabilir (kümülatif zarar düşük).

### C. Backend internal scheduler

`apscheduler` veya FastAPI lifespan task. Şu an yapısal olarak yok. Eklemek istersek `app.main` lifespan'ında periodic task olarak başlatılabilir — ek bağımlılık ve test maliyeti var.

**Karar:** Production'da **A (pg_cron)** + manuel paralel olarak **B (GH Actions, dry-run)** ile uyum kontrolü. C'yi şimdilik aldık dışı.

---

## Erasure ile etkileşim

Kullanıcı `DELETE /v1/me/sessions/{id}` çağırırsa:

1. Endpoint derhal tombstone'lar (`deleted_reason='user_request'`).
2. Cron job, tombstone'lanmış row'u 90 gün sonra (180 gün toplam yaş yerine 90 gün **tombstone yaşı**) hard-delete eder. Bkz: `app_retention_purge()` `--purge-grace-days` parametresi.
3. Kullanıcıya verilen yanıtta "verileriniz X gün içinde fiziksel olarak silinecektir" bilgisi mobil/dashboard tarafında gösterilebilir.

Soruşturma istisnası: Klinik incident veya hukuki soruşturma açıkken sessiz tombstone yetersiz; runbook `EMERGENCY_RULE_MISFIRE.md`'de "tombstone ETME, hukuki danışman kararıyla beklet" notu var.

---

## Test ve doğrulama

- `backend/tests/test_retention_config.py` — config sabitlerinin yüklenmesi + env override
- Supabase staging branch'inde `app_retention_purge(dry_run := true)` ile dry-run önce
- Production cron etkinleştirmeden önce 7 gün staging gözlem
- Quarterly: row count'ları log + alert (beklenmedik düşüş = bug)

---

## Değişiklik kontrolü

Bu sayılar değişirse:
1. PR'da **aydınlatma metni güncellemesi şart** (compliance KR-2).
2. CHANGELOG'a yazılır.
3. Mevcut kullanıcılara duyuru (in-app banner) — yeni süreler eski verilere uygulanmadan önce.
4. SQL fonksiyonu güncellenir; cron schedule değişmez.

Politika sahibi: Hukuk + DPO. Teknik sahibi: Backend eng. Yıllık review: 2027-04.
