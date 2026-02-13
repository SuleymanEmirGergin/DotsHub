# Triaj tarafında eklenebilecekler

Bu belge, soru bankası, belirti yorumlama ve triaj akışı tarafında yapılabilecek ek geliştirmeleri listeler.

---

## 1. Daha fazla detay sorusu

| Belirti | Eklenebilecek soru | Cevap tipi |
|---------|--------------------|------------|
| **Boğaz ağrısı** | Ne kadar süredir boğaz ağrınız var? | free_text |
| **Göğüs ağrısı** | Ne kadar süredir göğüs ağrınız var? / Ağrı sabit mi yoksa gelip geçici mi? | free_text / choice |
| **Kusma** | Günde kaç kez kusma oluyor? | free_text veya choice (1–2, 3–5, 5+) |
| **Ağrı şiddeti** | Ağrınızı 1–10 arası nasıl değerlendirirsiniz? | choice veya free_text |
| **Ateş** | Ateşiniz kaç derece ölçüldü? (biliyorsanız) | free_text |
| **Balgam rengi** | Balgam rengi nasıl? (şeffaf, sarı, yeşil, kanlı) | choice |
| **Karın ağrısı yeri** | Ağrı karnın neresinde? (sağ üst, sol alt, orta vb.) | choice |

Bu sorular için: soru bankası + `kaggle_to_canonical` + ilgili hastalıklara `disease_symptoms` + `symptom_severity` eklenmesi yeterli (bkz. `DETAY_SORULAR_EKLEME.md`).

---

## 2. Güvenlik ve acil yönlendirme

- **Kuralların genişletilmesi**: `rules.json` / `stop_rules.json` ve Safety Guard kurallarına yeni kombinasyonlar (örn. göğüs ağrısı + nefes darlığı → acil, kanlı kusma → acil).
- **Red-flag soruları**: Belirli belirti setlerinde otomatik “Bu belirtilerden herhangi biri var mı?” tarzı kısa kontrol soruları.
- **Aciliyet skoru**: Mevcut urgency (ROUTINE, SAME_DAY, EMERGENCY) yanında sayısal veya kategorik bir “aciliyet skoru” alanı (raporlama / öncelik sırası için).

---

## 3. Bağlam ve demografik sorular

- **Yaş**: Zaten profile’da olabilir; ilk mesajda veya ilk soruda “Yaşınız?” (veya aralık: 0–2, 3–12, 13–17, 18–64, 65+) eklenebilir.
- **Cinsiyet**: Özellikle jinekolojik / ürolojik şikayetlerde soru bankasına cinsiyet bazlı soru veya filtre eklenebilir.
- **Hamilelik**: Kadın + karın ağrısı / kanama vb. senaryolarda “Hamile misiniz?” sorusu.
- **Kronik hastalık / ilaç**: “Şu an kullandığınız sürekli ilaç var mı?” veya “Bilinen kronik hastalığınız var mı?” (evet/hayır + isteğe bağlı free_text).

Bunlar `profile` veya ilk turda sorulacak “bağlam” soruları olarak tasarlanabilir.

---

## 4. Serbest metin cevaplarının yapılandırılması

- **Süre parsing**: “3 gündür”, “1 haftadır” gibi cevapların `duration_days` veya benzeri bir alana otomatik çekilmesi (örn. `duration_parse.py` veya basit regex/kural).
- **Şiddet parsing**: “Çok kötü”, “Hafif” gibi ifadelerin 1–10 veya hafif/orta/ağır ile eşleştirilmesi.
- **Zamanlama parsing**: “Sabah kalkınca”, “Gece yatarken” → mevcut “sabah/akşam” veya “gece/gündüz” seçenekleriyle eşleme.

Böylece free_text cevaplar hem kullanıcı deneyimi hem de skorlama/karar için kullanılabilir.

---

## 5. Soru sırası ve atlama mantığı

- **Koşullu sorular**: Örn. “Öksürük yok” denmişse balgam / öksürük süresi sorulmaz (zaten asked_symptoms ile kısmen var; net “skip” kuralları eklenebilir).
- **Öncelikli sorular**: Belirli şikayetlerde (örn. göğüs ağrısı) süre ve “göğüste baskı / nefes darlığı” gibi soruların daha erken sorulması (soru bankası + discriminative skor veya ek “priority” alanı).
- **Maksimum soru sayısı**: `stop_rules.json` içindeki `max_questions` değerinin senaryoya göre (örn. acil adayı ise daha az soru) ayarlanması.

---

## 6. Çok dillilik (i18n)

- **Soru bankası İngilizce**: `symptom_question_bank_en.json` ve locale’e göre soru metninin seçilmesi.
- **Backend i18n**: Zaten `app/core/i18n.py` var; sonuç mesajları ve güvenlik uyarıları için locale bazlı metinler eklenebilir.

---

## 7. Veri ve kalite

- **Yeni hastalık / belirti**: Kaggle dışı kendi hastalık listesi veya ek belirtiler; `disease_symptoms.json` ve `kaggle_to_canonical` ile uyumlu şekilde eklenebilir.
- **Eş anlamlılar**: `synonyms_tr.json` genişletilerek kullanıcının yazdığı ifadelerin (örn. “tıkanıyorum”, “nefesim yetmiyor”) doğru canonical belirtiye düşmesi iyileştirilebilir.
- **Feedback döngüsü**: “Bu yönlendirme doğru muydu?” gibi geri bildirimin analitikte ve ileride model/kural güncellemesinde kullanılması.

---

## 8. Raporlama ve özet

- **Doktor özeti**: Sonuç ekranında “Doktora söyleyebileceğiniz özet”te süre, zamanlama, efor cevaplarının da cümle halinde yer alması (örn. “3 gündür öksürük, geceleri artıyor, balgam var”).
- **Export**: Oturum sonucunun PDF veya yapılandırılmış metin olarak dışa aktarılması (e-posta özeti ile uyumlu).

---

## Öncelik önerisi

1. **Hızlı kazanım**: Balam rengi, karın ağrısı yeri, ağrı şiddeti (1–10) gibi ek detay soruları.
2. **Güvenlik**: Acil kuralların ve red-flag sorularının gözden geçirilip genişletilmesi.
3. **UX**: Serbest metin süre/zamanlama parsing + doktor özetinde bu bilgilerin yer alması.
4. **İsteğe bağlı**: i18n (EN soru bankası), hamilelik/kronik hastalık soruları, koşullu atlama mantığı.

İlk adım olarak hangi maddeden başlamak istediğinizi söylerseniz, o madde için somut dosya/schema değişikliklerini adım adım yazabilirim.
