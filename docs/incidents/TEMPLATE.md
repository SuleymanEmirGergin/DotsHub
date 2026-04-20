# Incident — YYYY-MM-DD — <one-line description>

**Status:** OPEN / RESOLVED / MONITORING  
**Severity:** P0 (full outage) / P1 (degraded, major user impact) / P2 (partial) / P3 (internal only)  
**Duration:** HH:MM–HH:MM UTC = ~N minutes  
**Writer:** <your name / handle> · **Reviewed by:** <second set of eyes, optional>

---

## TL;DR

Tek paragraf, max 3 cümle. "Ne oldu, kime etkiledi, nasıl çözüldü?" Geri kalanı okumayan biri buradan çıksın.

Örnek:
> 22 dakika süren backend 5xx spike'ı. Son deploy'daki N+1 Supabase query 50+ oturum listesinde timeout oluşturdu, mobile + dashboard kullanıcıları "Bir sorun oldu" ekranı gördü. Rollback ile error rate <1%'e düştü. N+1'i çözmek + staging'e gerçekçi seed eklemek pending.

---

## Etki (Impact)

- **Etkilenen servis:** backend / dashboard / mobile / all
- **Etkilenen kullanıcı tahmini:** N sessions / ~X% trafik
- **Veri kaybı:** YES / NO / UNCLEAR
- **Süre:** N dakika (tespit → mitigation)
- **SLO etkisi:** (eğer SLO tanımlıysa — %availability, p99 latency, vs.)

Kullanıcı sayısı için:
```sql
SELECT COUNT(*) 
FROM triage_sessions 
WHERE created_at BETWEEN '<start>' AND '<end>'
  AND envelope_type = 'ERROR';
```

---

## Zaman Çizelgesi (UTC)

Tüm zamanlar UTC. Dakika hassasiyetinde yaz — 5 dk'dan kısa olaylar için birleştir.

| Zaman | Olay |
|-------|------|
| HH:MM | Trigger — deploy / config / external event |
| HH:MM | Alert düştü — `<alert-name>` Grafana/Sentry/webhook |
| HH:MM | On-call görürldü — Slack / SMS |
| HH:MM | İlk hipotez — log / trace ne söylüyor |
| HH:MM | Mitigation başladı — ne yapıldı |
| HH:MM | Mitigation tamamlandı — servis recovered |
| HH:MM | Alert kapandı — error rate normal |

---

## Kök Neden (Root Cause)

Ne oldu? Neden oldu? **Tek değil birden fazla cause varsa hepsini listele** (Swiss cheese model).

### Primary cause
<ana teknik sebep — tek cümle>

### Contributing factors
- <ikincil sebep 1>
- <ikincil sebep 2>

Kod referansı verirken: dosya:satır + commit SHA.

---

## Tespit (Detection)

**Nasıl farkettik?**

- [ ] Otomatik alert (Grafana / Sentry / webhook)
- [ ] Kullanıcı bildirimi (support email / app store review)
- [ ] Manuel log gözlem / rastlantı
- [ ] Başka: ...

Alert düştüyse: tespit gecikmesi kabul edilebilir mi? **İdeal tespit süresi** = olay başladıktan sonraki 5 dakika. 5'i aştıysa: **alert eşiği sıkılmalı** veya **yeni bir alert eklenmeli** (action item).

---

## Mitigation

**Nasıl durdurduk?**

- Adım 1: <ne yapıldı> (sonuç: ne oldu)
- Adım 2: ...

Hızlı mı yavaş mıydı? Neden? (Komut bilinmiyordu? Erişim yoktu? Rollback path karmaşıktı?)

---

## Neden Daha Erken Yakalanmadı

Test / staging / code review neden bu geçişi bulamadı?

- [ ] Test coverage boşluğu (modül X'te edge case yok)
- [ ] Staging test verisi prod'a benzemiyor (örn. tablo boyutu, concurrency)
- [ ] Code review tutumsal (sadece PR OK, perf impact sorgulanmıyor)
- [ ] Dependency upgrade notice kaçtı
- [ ] Externally triggered (downstream outage)

Bu alan **aksiyon'a dönüşmezse okuma zamanı boşa** — her ✓'ye bir follow-up.

---

## Aksiyon Kalemleri (Action Items)

Her action item: kim, ne zaman, nasıl takip edilir.

| # | Aksiyon | Kategori | Sahip | Deadline | Status |
|---|---------|----------|-------|----------|--------|
| 1 | <kod/config fix> | 🔧 tech | <isim> | <tarih> | OPEN |
| 2 | <süreç değişikliği> | 📋 process | <isim> | <tarih> | OPEN |
| 3 | <yeni monitoring> | 📊 monitor | <isim> | <tarih> | OPEN |
| 4 | <runbook update> | 📖 docs | <isim> | <tarih> | OPEN |

Kategoriler:
- 🔧 **tech** — doğrudan kod / config / dep
- 📋 **process** — deploy checklist, review prosedürü
- 📊 **monitor** — yeni alert, dashboard panel, log field
- 📖 **docs** — RUNBOOK, README, ADR, bu klasör

Status'lar: `OPEN` / `IN PROGRESS` / `DONE` / `WONTFIX` (açıklama ile).

---

## Dersler (Lessons)

En fazla **3 takeaway**. Her biri tek cümle. Aksiyondan farkı: daha genel prensip, daha az specific task.

1. <lesson 1>
2. <lesson 2>
3. <lesson 3>

Örnek:
1. Prod DB boyutu staging'i 100x geçebilir; perf regression staging'te görünmez.
2. Rollback komutunu 3 kişi biliyor olması `flyctl releases rollback` süresini 5dk'dan 1dk'ya düşürdü.
3. PowerShell quote escaping'in sessizce tırnak silmesi yaygın bir foot-gun; default'a CSV eklemek savunma katmanı.

---

## Ek

### Kanıt / Referans

- Alert link: `<grafana URL>`
- Sentry issue: `<sentry URL>`
- Slack thread: `<slack perma-link>`
- Deploy SHA: `<commit>`
- İlgili PR'lar (fix + follow-up): `<PR URL'leri>`

### Komut log'u

İncident'ta çalıştırılan kritik komutlar (minus secret values):

```bash
flyctl status --app triaige-backend
flyctl logs --app triaige-backend --no-tail
flyctl releases rollback <id> --app triaige-backend
# ...
```

### Ekran görüntüleri

Eğer paylaşılabilir ise (PII scrub'landı). Grafana panel, Sentry stack trace, dashboard screenshot.

---

_Template version: 1.0 (2026-04-20). Template değişirse docs/incidents/README.md'deki yapısını da güncelle._
