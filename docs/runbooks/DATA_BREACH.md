# Runbook: Data Breach Notification (KVKK + GDPR)

Risk lineage: `RISK_REGISTER_2026_04.md:M-1`. Compliance: `COMPLIANCE_CHECK_2026_04.md:Y-1`.

> Bu runbook, `SECURITY_INCIDENT.md`'in **regülatör bildirim katmanını** tamamlar. Önce SECURITY_INCIDENT'la incident'ı stabilize et; veri ifşası ONAYLANDIĞINDA buraya geç.

## Quick checklist

- [ ] **SECURITY_INCIDENT.md** runbook'undaki ilk 30 dk tamamlandı mı? (evidence preservation, severity, escalation)
- [ ] Veri ifşası **onaylandı** mı, yoksa şüphe mi? (alt: "Bildirim eşiği")
- [ ] **T+0** noktasını saat olarak kaydet — KVKK + GDPR'da 72 saat sayacı buradan başlar
- [ ] DPO / hukuk bilgilendirildi mi (1. saat zorunlu)
- [ ] Etkilenen kişi sayısı + veri kategorisi belirlendi mi
- [ ] KVKK ihlal bildirim formu hazırlanıyor mu (T+72 saat içinde sunulmalı)
- [ ] GDPR ilgili kişi (ICO/CNIL/AB DPA) bildirim — AB mukim kullanıcı varsa
- [ ] Veri sahibine bildirim gerekli mi (yüksek risk varsa zorunlu, KVKK Md.12(5) + GDPR Art.34)
- [ ] Post-incident raporu (alt)

## Bildirim eşiği — bildirim ZORUNLU mu?

Aşağıdakilerden **birisi varsa** bildirim zorunlu:

| Senaryo | KVKK | GDPR |
|---------|------|------|
| Özel nitelikli veri (sağlık) ifşa veya şüpheli erişim | EVET (Md.12(5)) | EVET (Art.33) |
| Şifrelenmemiş kişisel veri sızması | EVET | EVET (riskli ise) |
| Şifreli ama anahtar kompromize | EVET | EVET |
| Şifreli + anahtar güvende | Tartışmalı | HAYIR (genelde) |
| Sadece IP hash sızdı (ham IP yok) | HAYIR (kişisel veri değil) | HAYIR (anonimleştirilmiş) |

**Sağlık verisi içerdiği için bizim ürünümüzde herhangi bir veri ifşası ≈ kesin bildirim.**

## Severity ve eşik

| Etki büyüklüğü | Aksiyon |
|----------------|---------|
| 1-100 kullanıcı, sağlık verisi | Bildirim ZORUNLU; veri sahiplerine de bildirim |
| 100-1000 kullanıcı | Bildirim ZORUNLU; basın açıklaması düşünülmeli |
| 1000+ kullanıcı veya yetkili erişim | KVKK Kurulu doğrudan — proaktif iletişim |

## T+0 → T+72 timeline

### T+0 to T+1 hour — kapsama belirle

1. **Etkilenen veri kategorileri** (ne sızdı?):
   - [ ] Triage session input_text (semptomlar) — ÖZEL KATEGORI
   - [ ] User_canonicals_tr / answers — ÖZEL KATEGORI
   - [ ] E-posta adresleri (send-summary)
   - [ ] Push token'lar
   - [ ] IP hash (ÖZEL KATEGORİ DEĞİL)
   - [ ] Admin / yetkili erişim?
2. **Etkilenen kişi sayısı:** Supabase'te `triage_sessions` row count for affected window.
3. **Süre:** İhlal ne zaman başladı, ne zaman fark edildi, ne zaman durduruldu?
4. **Kök neden hipotezi:** vendor compromise / leaked credential / RCE / privilege escalation / yanlış config.

### T+1 to T+24 hour — DPO/hukuk hazırlık

1. DPO + hukuk + ürün sahibi (veri sorumlusu) toplantı.
2. KVKK form taslağı (alt şablon).
3. AB mukim etkilenen kullanıcı varsa: hangi DPA bildirilecek? (kullanıcı lokasyonuna göre).
4. Veri sahibine bildirim gerekiyor mu karar:
   - **GDPR Art.34**: "yüksek risk" varsa zorunlu — sağlık verisi default yüksek risk.
   - **KVKK Md.12(5)**: ilgili kişiye bildirim zorunlu.
5. Comms taslakları hazırla (KVKK formu + kullanıcı e-postası + basın hazır cevabı).

### T+24 to T+72 hour — bildirim sun

1. **KVKK** → https://veribihlalbildirim.kvkk.gov.tr (resmi form üzerinden)
2. **AB tarafı** → ilgili Supervisory Authority'nin online bildirim portalı (ICO, CNIL, BfDI, Garante, vb. — kullanıcı lokasyonuna göre)
3. Veri sahibine bildirim:
   - E-posta adresi olan kullanıcılara doğrudan e-posta
   - Mobil app: in-app banner (ResultScreen ve IntroScreen üstünde)
   - Dashboard / public web: `/security-notice` sayfası
4. **HER BİLDİRİMDEN COPY tut**: tarihler, alıcılar, içerikler — denetim için.

## KVKK ihlal bildirim formu — zorunlu içerik

KVKK Md.12(5) ve "Veri İhlal Bildirimi Tebliği" çerçevesinde:

```
1. Veri sorumlusu kimliği:
   - Ad / unvan
   - VKN
   - Adres + iletişim

2. İhlal tarihi/zamanı:
   - Başlangıç (tahmin)
   - Tespit
   - Sonlandırma

3. İhlalin niteliği:
   - Tip (yetkisiz erişim / yanlış erişim / kayıp / değişiklik / ifşa)
   - Etkilenen sistem (Supabase Postgres / Redis / Sentry / vb.)

4. Etkilenen kişisel veri kategorileri:
   - [x] Sağlık verisi (özel nitelikli)
   - [x] İletişim (e-posta)
   - [ ] Kimlik
   - [x] İşlem güvenliği (IP hash)

5. Etkilenen ilgili kişi sayısı (yaklaşık)

6. Olası sonuçlar:
   - Klinik (sağlık verisi yanlış kullanım)
   - İletişim (spam, phishing)
   - İtibar (kullanıcı için)

7. Alınan/alınacak tedbirler:
   - Anlık (rate-limit sıkılaştırma, anahtar rotasyonu, vb.)
   - Yapısal (ek encryption, access review, vb.)

8. İletişim noktası (DPO / sorumlu)
```

## Veri sahibine bildirim — Türkçe şablon

> **Konu:** Verilerinizin güvenliğine ilişkin önemli bildirim
>
> Sayın Kullanıcımız,
>
> [TARİH] tarihinde [SİSTEM]'de [TİP] türünden bir güvenlik olayı tespit ettik. Yapılan inceleme, sizin de aralarında bulunduğunuz [SAYI] kullanıcının [VERİ KATEGORİSİ] verilerinin [ETKİ TÜRÜ] olduğunu göstermektedir.
>
> **Ne yaptık:**
> - Olayı [SAAT] içinde durdurduk.
> - [TEDBİRLER]
> - Kişisel Verileri Koruma Kurulu'na resmi bildirimde bulunduk.
>
> **Sizden ne yapmanızı rica ediyoruz:**
> - [Mevcutsa: parolanızı değiştirin]
> - [E-posta etkilendiyse: tanımadığınız mesajlara dikkat edin]
> - Sağlık verileriniz etkilendiyse, hekiminizle bu durumu paylaşmanızı tavsiye ederiz.
>
> **Haklarınız (KVKK Madde 11):** Erişim, düzeltme, silme, veri taşınabilirliği. [İLETİŞİM ADRESİ] üzerinden başvurabilirsiniz.
>
> **Sorularınız için:** [DPO E-POSTA]
>
> KVKK Kurumu'na şikâyet hakkınız saklıdır.
>
> Saygılarımızla,
> [VERİ SORUMLUSU]

(EN, DE, RU, AR çevirileri ihlal anında hızlı çevrilebilmesi için DPO arşivinde hazır tutulmalı.)

## Veri sahibi bildirim — istisna durumu

Veri sahibine bildirim ZORUNLU değildir eğer:

1. (KVKK + GDPR) Veri etkin şekilde **şifreli** ve anahtar kompromize değil → bildirim "yüksek risk" yaratmaz.
2. (GDPR Art.34(3)) Sonradan alınan tedbirler riski "muhtemel" olmaktan çıkardı.
3. (GDPR Art.34(3)) Bireysel bildirim **orantısız çaba** gerektiriyor → public communication (ör. basın bildirisi) yeterli.

İstisna iddiası DPO + hukuk birlikte kararı.

## Decision log — bu olay için

| Soru | Cevap | Karar veren | Saat |
|------|-------|-------------|------|
| Bildirim eşiği aşıldı mı | | DPO | |
| Veri sahibine bildirim zorunlu mu | | DPO+Hukuk | |
| Hangi DPA'ya bildirim | | DPO | |
| Basın açıklaması | | Comms+Hukuk | |

## Post-incident rapor

- KVKK form sunum tarihi, referans no.
- DPA referansları (varsa).
- Veri sahibi bildirim sayısı, gönderim metodu.
- Yapısal aksiyon listesi (ihlali aynı şekilde tekrar etmeyecek tedbirler).
- 30 gün sonra follow-up: planlanan aksiyonlar tamamlandı mı?

## Escalation

| Durum | Kontak | Süre |
|-------|--------|------|
| İhlal onayı | DPO | <1 saat |
| Hukuk değerlendirmesi | İç hukuk + dış danışman | <4 saat |
| Veri sorumlusu (CEO/founder) onayı | Veri sorumlusu | <8 saat |
| KVKK form sunumu | DPO | T+72 saat |
| Veri sahibi bildirim | DPO + comms | T+72 saat (yüksek risk) |

## History

| Tarih | Olay özeti | KVKK ref | DPA ref |
|-------|-----------|----------|---------|
| _ilk yazıldığında çalıştırılmadı_ | | | Şablon |
