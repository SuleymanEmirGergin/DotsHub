# Veri ve kalite

Bu belge: yeni hastalık/belirti ekleme, eş anlamlılar genişletme ve geri bildirim (feedback) kullanımı.

---

## 1. Yeni hastalık / belirti ekleme

Triaj pipeline’ı şu verilerle çalışır:

- **`backend/app/data/kaggle_cache/disease_symptoms.json`**  
  Her hastalık için Kaggle tarafındaki belirti listesi. Yeni hastalık eklemek için:
  - Yeni bir blok ekleyin: `"disease_label": "Hastalık adı", "symptoms": ["symptom_1", "symptom_2", ...]`.
  - `symptoms` içindeki her değer **Kaggle belirti adı** olmalı (örn. `cough`, `headache`).

- **`backend/app/data/kaggle_cache/kaggle_to_canonical.json`**  
  Kaggle belirti adı → Türkçe canonical eşlemesi. Yeni belirti eklemek için:
  - `"kaggle_symptom_name": "canonical_tr"` ekleyin (örn. `"new_symptom": "yeni belirti"`).
  - Canonical adı, soru bankası (`symptom_question_bank_tr.json`) ve eş anlamlılar (`synonyms_tr.json`) ile uyumlu olmalı.

- **Soru bankası**  
  Yeni canonical için soru yoksa `symptom_question_bank_tr.json` (ve isteğe bağlı `symptom_question_bank_en.json`) içine ilgili `canonical_symptom` ile bir soru ekleyin.

- **Hastalık–belirti eşlemesi**  
  Yeni hastalık eklediğinizde `disease_symptoms.json` içindeki `symptoms` listesinde kullandığınız her Kaggle belirtisinin `kaggle_to_canonical.json` içinde karşılığı olmalı.

**Özet:** Yeni hastalık → `disease_symptoms.json`. Yeni belirti → `kaggle_to_canonical.json` + gerekirse soru bankası + eş anlamlılar.

---

## 2. Eş anlamlılar (synonyms_tr.json)

Kullanıcının yazdığı ifadelerin doğru canonical belirtiye düşmesi için:

- **Dosya:** `backend/app/data/synonyms_tr.json`
- **Yapı:** `"synonyms": [ { "canonical": "canonical_belirti_adı", "type": "symptom" | "red_flag", "variants_tr": ["ifade1", "ifade2", ...] } ]`
- **Kullanım:** Specialty scorer, triage engine ve canonical çıkarımı bu dosyayı kullanır; kullanıcı metninde `variants_tr` içinden biri geçerse ilgili `canonical` sayılır.

**Örnek:** “tıkanıyorum”, “nefesim yetmiyor” → `nefes darlığı`. Bu tür ifadeleri `nefes darlığı` canonical’ına ait `variants_tr` listesine ekleyin.

**Yeni eşleme ekleme:**  
- Var olan bir canonical’a yeni ifade: İlgili nesnenin `variants_tr` listesine ekleyin.  
- Yeni canonical: Yeni bir `{ "canonical": "...", "type": "symptom", "variants_tr": [...] }` nesnesi ekleyin; `kaggle_to_canonical.json` ve soru bankası ile uyumlu bir isim kullanın.

---

## 3. Feedback döngüsü (“Bu yönlendirme doğru muydu?”)

Kullanıcı geri bildirimi:

- **Endpoint:** `POST /v1/triage/feedback`
- **Body:** `{ "session_id": "uuid", "rating": "up" | "down", "comment": "opsiyonel", "user_selected_specialty_id": "opsiyonel" }`
- **rating:** `"up"` = yönlendirme doğru/uygun, `"down"` = yanlış/uygunsuz (örn. “Bu yönlendirme doğru muydu?” sorusuna cevap).
- **comment:** Kullanıcı yorumu (analitik / kalite için).
- **user_selected_specialty_id:** Kullanıcı farklı bir branş seçtiyse buraya yazılabilir.

Veriler Supabase `triage_feedback` tablosuna yazılır; analitik ve ileride model/kural güncellemesi için kullanılabilir. Down rating’li oturumlar `synonym_suggest.py` vb. ile eş anlamlı önerisi üretmek için de kullanılabilir.
