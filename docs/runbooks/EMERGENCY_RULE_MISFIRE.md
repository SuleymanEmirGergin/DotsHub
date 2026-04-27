# Runbook: Emergency Rule Misfire (False Positive / Negative)

Risk lineage: `RISK_REGISTER_2026_04.md:C-2 (Critical, klinik)`. Tech-debt: `TECH_DEBT_2026_04.md:#1`. Konsolidasyon planı: `docs/adr/ADR-001-safety-guard-consolidation.md`.

## Quick checklist (rapor → green)

- [ ] Raporu kategorize et: **false positive** (panic'e itti, gerek yoktu) veya **false negative** (kritik semptomu kaçırdı)
- [ ] Severity belirle (aşağı bak — false negative her zaman P0)
- [ ] Etkilenen `session_id` ve trigger'ı topla (admin panel veya `triage_events`)
- [ ] **HARD ROLLBACK gerekiyor mu?** Son `rules.json` deploy'u şüpheliyse evet
- [ ] Klinik triage akışı (false negative ise) — kullanıcıya nasıl ulaşırız?
- [ ] Comms: Slack `#dotshub-ops` + KVKK Md.12(5) tetikleyici mi sorgula
- [ ] Post-mortem ticket (alt)

## Symptoms

### False positive (panic'e itti)
- Kullanıcı feedback: "yanlış paniğe sevk etti", "112'ye yönlendirdi ama acil değildim"
- Admin panel sparkline: emergency oranı son 24 saatte ani sıçrama (>%50 jump)
- Trigger ID listesi (`triage_events.data.rule_id`) belirli bir kuralda yoğunlaşmış

### False negative (kaçırdı) — KLİNİK KRİTİK
- Kullanıcı / yakını rapor ediyor: "X uygulamayı kullandı, 'dahiliyeye git' dedi, sonra hastaneye gittiler ve enfarktüstü"
- Şikayet, basın, ya da regulatöre direkt bildirim
- `triage_events`'te emergency tetiklenmemiş ama post-hoc bilgi (ölüm, ICU yatışı) öğrenildi

## Severity

| Tip | Severity | Süre |
|-----|----------|------|
| **False negative** (klinik zarar onaylı veya yüksek olası) | **P0** | Anında — saatlerin meselesi |
| **False positive** (yaygın, ürün kullanılamaz hale getiriyor) | **P1** | <1 saat |
| **False positive** (tek bir kural, izole) | **P2** | <8 saat |

P0 her zaman: incident commander + klinik danışman + hukuk + KVKK DPO.

## Immediate mitigation

### False negative — Step 1: hard rollback

`rules.json`'da son değişiklik şüpheliyse:

```bash
git log -- backend/app/data/rules.json | head -10
git revert <commit_sha>          # son değişikliği geri al
fly deploy -a triage-backend     # acil deploy
```

Doğrula: `curl $BACKEND/health` → `app_version` değişti mi.

### False negative — Step 2: kural ekle (provisional)

Rapor edilen semptom hard trigger'larda yoksa:

1. `backend/app/data/rules.json` → `red_flags.hard_triggers`'a ekle (regex + keywords).
2. **Test:** `pytest tests/test_emergency_router_*.py` + manual:
   ```bash
   curl -X POST $BACKEND/v1/triage/turn -d '{"text":"<şüpheli semptom>"}'
   # Beklenen: status="EMERGENCY"
   ```
3. Deploy + log: `triage_events`'te yeni rule_id görünmeye başlamalı.

### False positive — Step 1: kuralı izole et

`triage_events.data.rule_id` filtreleyip son 24 saatte hangi kural fazla tetikledi öğren:

```sql
SELECT data->>'rule_id' AS rule, COUNT(*)
FROM triage_events
WHERE event = 'emergency_triggered'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY 1 ORDER BY 2 DESC;
```

### False positive — Step 2: hızlı yumuşatma

İki yol var:
- **Regex daraltma** (tercih): `rules.json`'da kuralın `regex` field'ını daha spesifik yap (örn. word boundary `\b` ekle).
- **Keyword listesinden çıkar:** false positive'in tek kaynağı tek kelimeyse kaldır.

Test + deploy + log doğrula.

## Klinik akış (sadece false negative)

1. **Etkilenen kullanıcıyla iletişim:** Kullanıcı session anonim olduğundan biz proaktif ulaşamayız. Eğer şikayet üzerinden öğrendiysek geri bildirim kanalından (e-posta, telefon) iletişimi sürdür. Tıbbi süreç hakkında YORUM YAPMA — sadece **olayın bize ulaştığını + soruşturmaya alındığını + 7 gün içinde dönüş yapacağımızı** söyle.
2. **Klinik danışman**: vakayı teknik özetle paylaş — semptom metni, ürünün döndüğü çıktı, ne olması gerektiği. Klinik karar bizim değil.
3. **Sigorta + hukuk**: Ürün sorumluluğu sigortası varsa derhal bildirim. Hukuk ekibi paralel hareket eder.

## Data integrity & forensics

- Etkilenen `session_id`'yi **TOMBSTONE ETME** — vaka soruşturmasında ham veri gerekli olabilir.
- `triage_sessions` + `triage_events` + `llm_calls` (varsa) tablolarından session_id ile snapshot al, ayrı bir bucket'a koy:
  ```bash
  python scripts/export_session.py --session-id $SID --out incidents/$SID.json
  ```
- Kullanıcı erasure talep ederse: hukuk danışmanı ile koordine et — KVKK Md.11 silme talebi ile soruşturmanın "yasal yükümlülük" istisnası çatışıyor (KVKK Md.7). Genellikle soruşturma sona erene kadar tombstone ertelenir, kullanıcıya yazılı gerekçe ile bildirilir.

## KVKK / GDPR tetikleyici kontrol

Hatanın klinik zarar üretmesi tek başına KVKK ihlali DEĞİLDİR (kişisel veri ihlali değil, klinik karar hatası). **AMA**:

- Eğer hata bir veri ifşası içeriyorsa (örn. başka kullanıcının semptomları yanıtta gösterildi) → `DATA_BREACH.md` runbook'una geç.
- Eğer "automated decision-making" şikayeti gelirse (GDPR Art. 22) → hukuk değerlendirmesi.

## Rollback (full)

Eğer son deploy'da `rules.json` + safety_guard kodu birlikte değiştiyse:

```bash
fly releases list -a triage-backend
fly releases rollback <prev_version> -a triage-backend
```

Bu **tüm uygulamayı** önceki sürüme döndürür; sadece kural değil. Daha hedefli rollback için `git revert`.

## Verification (post-fix)

- [ ] `tests/test_emergency_router_*.py` yeşil
- [ ] Etkilenen semptom için `/v1/triage/turn` doğru status dönüyor (false neg → EMERGENCY, false pos → QUESTION/RESULT)
- [ ] `triage_events.data.rule_id` patterni 24 saat içinde normalleşti (false pos için)
- [ ] Admin sparkline: emergency oranı normal aralığa döndü

## Escalation

| Durum | Kontak | SLA |
|-------|--------|-----|
| False negative + klinik zarar | Incident commander + klinik danışman + hukuk | <30 dk |
| False positive yaygın | On-call eng + ürün | <1 saat |
| Basın/sosyal medya | Comms lead + hukuk | <2 saat — onaylı mesaj olmadan paylaşım YOK |

## Post-mortem ticket

- Tetikleyici: trigger_id, son deploy SHA, kural commit'i.
- Severity, etki süresi, etkilenen oturum sayısı.
- Root cause: kural yazımı, regex hatası, test corpus eksikliği.
- Aksiyon: `tests/test_safety_guard_consolidated.py` (ADR-001 sonrası) test corpus'una vakayı ekle.
- ADR-001 tamamlanmadıysa hızlandır.

## History

| Tarih | Tip (FP/FN) | Trigger | Çözüm |
|-------|-------------|---------|-------|
| _ilk yazıldığında çalıştırılmadı_ | | | Şablon |
