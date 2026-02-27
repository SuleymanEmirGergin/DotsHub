# Soru sırası ve atlama mantığı

Üç mekanizma: koşullu atlama, öncelikli sorular, senaryoya göre maksimum soru sayısı.

## 1. Koşullu atlama (skip rules)

**Dosya:** `backend/app/data/question_skip_rules.json`

- Bir belirti **yok** denmişse, ona bağlı detay soruları **sorulmaz**.
- Örnek: "Öksürük yok" denmişse → balgam, öksürük süresi, öksürük gece artışı, balgam rengi sorulmaz.
- Yapı: `skip_rules[]` içinde her eleman `canonical_symptom` (sorulacak soru) ve `skip_if_denied` (bunlardan biri yok denmişse bu soruyu atla).

**Akış:** `question_selector.select_question(..., denied_symptoms=state.denied_symptoms)` ile `denied_symptoms` verilir; selector bu kurallara göre adayları eler.

## 2. Öncelikli sorular (priority_when_known)

**Dosya:** `backend/app/data/symptom_question_bank_tr.json`

- Soru nesnelerine isteğe bağlı `priority_when_known`: `["göğüs ağrısı"]` gibi bir liste eklenebilir.
- Kullanıcı o belirtilerden en az birini **var** demişse, bu sorunun discriminative skoru **+0.35** artar; böylece süre / baskı / nefes darlığı gibi sorular daha erken seçilir.

**Şu an öncelikli:** Göğüs ağrısı süresi, göğüs ağrısı sabit mi, göğüste baskı, nefes darlığı (hepsi `priority_when_known: ["göğüs ağrısı"]`).

**Akış:** `select_question(..., present_symptoms=state.known_symptoms)` ile `present_symptoms` verilir; selector skoru yükseltir.

## 3. Maksimum soru sayısı (senaryoya göre)

**Dosya:** `backend/app/data/stop_rules.json`

- `max_questions`: Normal senaryo (varsayılan 6).
- `max_questions_emergency`: Acil senaryoda daha erken dur (varsayılan 4).
- `emergency_specialty_ids`: Önerilen branş bu id’lerden biri ise acil say (örn. cardiology, emergency, neurology).
- `emergency_disease_keywords`: En yüksek skorlu hastalık etiketinde bu kelimelerden biri varsa acil say (örn. Heart attack, Paralysis, Stroke).

**Akış:** `_should_stop_v4(state)` içinde acil senaryo tespit edilir; acil ise `max_questions_emergency`, değilse `max_questions` kullanılır.

## Yeni kural ekleme

- **Atlama:** `question_skip_rules.json` → `skip_rules` dizisine `{"canonical_symptom": "...", "skip_if_denied": ["..."]}` ekle.
- **Öncelik:** `symptom_question_bank_tr.json` → ilgili soruya `"priority_when_known": ["ana_belirti"]` ekle.
- **Acil limit:** `stop_rules.json` → `emergency_specialty_ids` veya `emergency_disease_keywords` güncelle; gerekirse `max_questions_emergency` değiştir.
