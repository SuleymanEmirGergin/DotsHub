# Faz 3 — Startup planı (TriAIge)

Faz 1 ve Faz 2 tamamlandıktan sonra TriAIge'in startup hattını
desteklemek için yapılan/yapılacak iş kalemleri. Doküman, kritik
güvenlik yamalarını da takip eder — bunlar release-blocker olmayan
ama hasta-yönlendirme kalitesini doğrudan etkileyen düzeltmelerdir.

---

## Critical safety patches landed

Bu listede yer alan her madde, "saha-kanıtlı" bir bug (demo veya
gerçek kullanıcı senaryosunda gözlemlenmiş) için yapılan minimal,
test-kapalı düzeltmedir. Hepsinin kendi regression testi vardır;
hiçbiri demo-yamaları ile gizlenmemiştir.

| Tarih | Commit | Konu | Test kapsamı |
|-------|--------|------|--------------|
| 2026-04-28 | `271ce7d` | `fix(canonical-extract): handle Turkish suffix forms (possessive, locative, ablative)` — Türkçe agglutinatif eklerin canonical eşleşmesinde kaybolmasını engelliyor; `\b{phrase}\b` boundary'sini Türkçe ek toleransıyla genişletiyor. Demo fizesi `"sağ alt karın bölgemde keskin ağrı"` artık `sağ alt karın ağrısı` canonical'ını çıkarıyor (önceden `[]` dönüyordu). Real-corpus pass-rate baseline (79.1%) korundu, kapsama testinde 81.1%'e (+24 pp baseline'a göre) çıktı. | `backend/tests/test_canonical_extract_turkish_morphology.py` (3-4 ekli varyant × her popüler canonical + deyim negatifleri + negasyon koruması + start-boundary strict kontrolü) |

> Yeni güvenlik yaması eklerken: (a) regression testi olmadan
> commit etmeyin, (b) `python scripts/run_backend_regression.py`
> 4/4 PASS olmalı, (c) tabloda commit hash + test dosyası referansı
> bulunmalı.

---

## Faz 3 hedefleri

(Bu bölüm Faz 3 startup yol haritası dolmaya başladıkça eklenecek.
Şimdilik yalnızca güvenlik yamalarını izlemek için kullanılıyor.)
