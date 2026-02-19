# Bağımlılık kontrolü (release öncesi veya periyodik)

Release checklist’teki “0. Sürüm öncesi” adımında istenir; release yapmadan da periyodik kontrol için kullanılabilir.

---

## Dashboard (pnpm)

```bash
cd dashboard
pnpm audit
```

Çıktıyı inceleyin; gerekirse `pnpm update` veya belirli paket güncellemesi yapın. [DEPENDENCY_UPDATES.md](DEPENDENCY_UPDATES.md) ile karşılaştırılabilir.

---

## Mobile (npm/pnpm)

```bash
cd mobile
pnpm audit
# veya
npm audit
```

---

## Backend (pip)

```bash
cd backend
# Opsiyonel: venv aktif
pip list --outdated
```

Yeni sürüm çıkmış paketleri gösterir; güncellemek için `pip install -U <paket>` (ve requirements.txt güncellemesi) ayrıca yapılır.

---

Bu dosya yalnızca komutları ve amacı tanımlar; çıktı burada tutulmaz. Çıktıyı saklamak isterseniz:

- `pnpm audit > ../../docs/audit-dashboard.txt`
- `pip list --outdated > ../../docs/outdated-backend.txt`

(İsteğe bağlı; `.gitignore`’a eklenebilir.)
