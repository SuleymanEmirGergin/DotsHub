# Bağlam ve demografik sorular

Triaj akışında eksik profil bilgisi sohbet içinde sorulur. Sorular **normal belirti sorularından önce** (red-flag’ten de önce) sırayla gelir.

## Veri

- **`backend/app/data/context_questions.json`**  
  - `id`: age, sex, pregnancy, chronic  
  - `question_tr`, `answer_type`, `profile_field`, `when_ask`, `order`  
  - **when_ask**:  
    - `always`: Profil alanı eksikse sor (yaş, cinsiyet, kronik).  
    - `when_female_and_relevant`: Sadece cinsiyet kadın **ve** `when_symptoms_any` içinden en az biri varsa sor (hamilelik).

## Akış

1. **Soru sırası**: Önce bağlam (yaş → cinsiyet → [hamilelik koşullu] → kronik), sonra red-flag, sonra discriminative sorular.
2. **Cevap**: Kullanıcı cevabı `context_questions.parse_context_answer(id, text)` ile parse edilir; `state.profile` güncellenir (yoksa `UserProfile()` oluşturulur).
3. **Hamilelik**: Sadece `profile.sex` kadın **ve** `known_symptoms` içinde karın ağrısı / kanama / lekelenme / vajinal kanama varsa sorulur.

## Modül

- **`backend/app/agents/context_questions.py`**  
  - `get_next_context_question(state, asked_context_ids)` → sorulacak bir sonraki soru veya `None`  
  - `parse_context_answer(context_id, answer_text)` → `{ profile_field: value }`  
  - Yaş: sayı parse; cinsiyet: Erkek/Kadın/Belirtmek istemiyorum; hamilelik: evet/hayır; kronik: evet → `["Var"]`, hayır → `[]`

## Orkestratör

- **SessionState**: `asked_context_ids`, `_last_context_id`  
- **handle_turn**:  
  - Gelen cevap `_last_context_id` ile bağlam cevabıysa → parse, profile güncelle, `consumed_by_context=True` (normal canonical güncellemesi yapılmaz).  
  - Soru seçiminde: `get_next_context_question` → varsa bu soru sorulur, `_last_context_id` set edilir.

## Yeni bağlam sorusu ekleme

1. `context_questions.json` içine yeni nesne ekle: `id`, `question_tr`, `answer_type`, `profile_field`, `when_ask` (ve gerekirse `when_symptoms_any`, `choices_tr`).  
2. `parse_context_answer` içinde bu `id` için parse mantığı ekle.  
3. `_profile_missing` veya `get_next_context_question` içinde “eksik” / “ne zaman sorulacak” mantığını bu alana göre güncelle.
