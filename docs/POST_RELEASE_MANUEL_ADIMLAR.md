# Post-release manuel adımlar

Release sonrası aşağıdaki adımlar **kod değişikliği gerektirmez**; repo ayarları ve production ortamında elle yapılır.

---

## 1. Branch protection (GitHub repo ayarları)

**Nerede:** GitHub repo → **Settings → Branches → Branch protection rules** (örn. `main` için kural).

**Ne yapılacak:** [BRANCH_PROTECTION_CHECKLIST.md](BRANCH_PROTECTION_CHECKLIST.md) içindeki maddeleri uygulayın:

- Required check’ler: `golden-flow-regression`, `dashboard-quality`
- İsteğe bağlı: `supabase-db-smoke`, `guardrail`
- PR zorunluluğu, onay sayısı, konuşma çözümü vb. (checklist’teki tüm madde başlıkları)

Bu adım yalnızca repo sahibi / admin tarafından yapılır.

---

## 2. Production güvenlik kontrolü (deploy sonrası)

Deploy tamamlandıktan sonra production ortamında aşağıdaki kontrolleri yapın. Ayrıntılı rehber: [GUVENLIK_RELEASE_KONTROL.md](GUVENLIK_RELEASE_KONTROL.md).

- **CORS:** `CORS_ORIGINS` production’da yalnızca gerçek origin’ler (localhost değil).
- **Güvenlik header’ları:** `APP_ENV=production` ile HSTS, X-Content-Type-Options vb. etkin.
- **Admin rate limit:** `/v1/admin/*` için limit ve dokümantasyon uyumlu.

RELEASE_CHECKLIST bölüm 7 maddeleri bu kontrollerden sonra işaretlenebilir.

---

## Özet

| Adım | Doküman | Kim / ne zaman |
|------|---------|-----------------|
| Branch protection | [BRANCH_PROTECTION_CHECKLIST.md](BRANCH_PROTECTION_CHECKLIST.md) | Repo admin; release sonrası bir kez veya güncelleme |
| Production güvenlik | [GUVENLIK_RELEASE_KONTROL.md](GUVENLIK_RELEASE_KONTROL.md) | Her deploy sonrası kontrol |
