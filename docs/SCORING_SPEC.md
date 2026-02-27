# Scoring Example (TR) — Branş Skoru Nasıl Hesaplanır?

## Amaç
Kullanıcının tek mesajından "hangi branş daha olası?" sinyalini çıkarıp,
agentic soru sorma döngüsünü doğru yöne itmek.

Bu sistem tanı koymaz. Sadece routing sinyali üretir.

---

## Parametreler (specialty_keywords_tr.json)
- keyword_match_points = 3
- phrase_match_points  = 5
- negative_keyword_penalty = -4

---

## Input
Mesaj:
> "Sabah kalktığımdan beri başım dönüyor, midem bulanıyor."

---

## 1) Normalizasyon
- küçük harf
- noktalama sadeleştirme
- türkçe karakterler korunur

---

## 2) Sinyal Çıkarma (phrase > keyword)
ÖNEMLİ: Double-count yok.
- Önce phrase yakala
- Sonra kalan metinde keyword ara
- Aynı kökten gelen sinyali bir kez say

### Örnek sinyaller
- Phrase: "başım dönüyor"
- Keyword (eşdeğer): "baş dönmesi"
- Phrase: "midem bulanıyor"
- Keyword (eşdeğer): "bulantı"

---

## 3) Synonym / eşdeğer kuralı
Basit MVP kuralı:
- "başım dönüyor" -> "baş dönmesi"
- "midem bulanıyor" -> "bulantı"

Uygulama:
- Phrase yakalandıysa, o phrase'in synonym keyword'u tekrar sayılmaz.
  (yani "başım dönüyor" yakalanınca "baş dönmesi" keyword'unu aynı kökten ikinci kez puanlama)

---

## 4) Skor Hesaplama
### Nöroloji
- Phrase match: "başım dönüyor" -> +5
- Keyword match: (aynı kök) "baş dönmesi" -> SAYILMAZ (double-count yok)

Toplam: 5

Ek not:
- Eğer metinde ayrıca "oda dönüyor" geçseydi bu ayrı phrase -> +5 daha alırdı.

### Dahiliye/Gastro
- Phrase match: "midem bulanıyor" -> +5
- Keyword match: "bulantı" -> SAYILMAZ (same-root double-count yok)

Toplam: 5

---

## 5) Eşitlik Bozma (Tie-break)
Nöroloji = 5, Dahiliye = 5

Tie-break sırası:
1) Güvenlik soruları (red-flag dışlama) hangi branşa daha yakın?
   - Stroke/ani nöro bulgular sorusu -> Nöroloji hattını öne alır.
2) Question Generator'ın "ayırt edici soru" stratejisi:
   - "Oda dönüyor mu sersemlik mi?" -> Nöro/KBB hattını netleştirir.
3) Hâlâ belirsizse fallback:
   - Dahiliye (genel branş)

---

## 6) Sonuç
Tek mesajla branş %100 kesinleşmez.
Skor sadece "ilk soruyu nereye yönelteceğiz?" sinyali verir.
Agentic döngü:
- Güvenlik (red-flag) dışla
- Ayırt edici soruyla dominant branşı yükselt
- Stop condition sağlanınca reasoning + routing

Bu, hem güvenli hem pratik MVP yaklaşımıdır.

---

## Deterministik Scoring Spec (kısa özet)

Deterministik olmasının 3 altın kuralı:

1. **Normalize** (lowercase, punctuation→space, whitespace collapse)
2. **Phrase önce** (synonyms variant'larını uzundan kısaya tara)
3. **NO_DOUBLE_COUNT_SAME_CANONICAL** (canonical bir kere skorlanır; phrase > keyword)

Tie-break da deterministik:
1. keyword puanı yüksek olan
2. reasoning agent top-candidate uyumu (varsa)
3. fallback: Dahiliye
