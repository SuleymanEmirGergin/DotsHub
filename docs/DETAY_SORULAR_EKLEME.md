# Detay soruları (süre, zamanlama, efor) ekleme

Sistemde “var mı?” yerine **süre**, **zamanlama** (gece/gündüz, sabah/akşam) veya **eforla mı istirahatte mi** gibi detay soruları da sorulabilir.

## Yapılan yenilikler (özet)

- **Öksürük**: balgam, ne kadar süredir, geceleri mi gündüzleri mi
- **Baş ağrısı**: ne kadar süredir, sabahları mı akşamları mı
- **Karın ağrısı**: ne kadar süredir
- **Ateş**: ne kadar süredir
- **İshal**: ne kadar süredir
- **Nefes darlığı**: eforla mı istirahatte mi

## Yeni detay sorusu eklemek için

1. **Soru bankası** (`backend/app/data/symptom_question_bank_tr.json`):
   - Yeni `canonical_symptom` (örn. `"belirti süresi"`) ile bir soru ekleyin.
   - `answer_type`: `"yes_no"` | `"free_text"` | `"choice"`.
   - `choice` ise `choices_tr`: `["Seçenek 1", "Seçenek 2", ...]` ekleyin.

2. **Kaggle → canonical** (`backend/app/data/kaggle_cache/kaggle_to_canonical.json`):
   - Yeni Kaggle anahtarı (örn. `symptom_duration_days`) → canonical (örn. `belirti süresi`) eşlemesi ekleyin.

3. **Hastalık belirtileri** (`backend/app/data/kaggle_cache/disease_symptoms.json`):
   - İlgili hastalıkların listesine bu yeni Kaggle anahtarını ekleyin (aksi halde Question Selector bu soruyu seçmez).

4. **Şiddet** (`backend/app/data/kaggle_cache/symptom_severity.json`):
   - Yeni Kaggle anahtarı için 1–7 arası bir değer ekleyin.

5. **İsteğe bağlı**: `backend/scripts/add_detail_symptoms_to_diseases.py` benzeri bir script ile birden fazla hastalığa toplu ekleme yapabilirsiniz.

## Cevap tipleri

- **yes_no**: Evet/Hayır; `known_symptoms` / `denied_symptoms` güncellenir.
- **free_text**: Kullanıcı serbest yazar (örn. “3 gündür”); `state.answers[canonical]` = metin.
- **choice**: Kullanıcı seçeneklerden birini seçer; `state.answers[canonical]` = seçilen metin.

Mobil tarafta `answer_type` ve `choices_tr` kullanılarak uygun UI (metin kutusu veya butonlar) gösterilebilir.
