# Triaj çok dillilik (i18n)

Locale’e göre soru metinleri ve hata/güvenlik mesajları seçilir. İstekte `locale` alanı kullanılır (örn. `tr-TR`, `en-US`).

## İstek

- **POST /v1/triage/turn**: `TriageTurnRequest.locale` (varsayılan `"tr-TR"`). Her turda gönderilir; oturumda saklanır (`state.locale`).

## Soru metinleri

1. **Soru bankası (discriminative)**  
   - `symptom_question_bank_tr.json`: `question_tr`, `choices_tr`.  
   - `symptom_question_bank_en.json`: Aynı `canonical_symptom` için `question_en`, `choices_en`.  
   - `question_selector.select_question(..., locale=...)`: Locale `en` ile başlıyorsa `question_en` / `choices_en`, yoksa `question_tr` / `choices_tr` döner. Eksik EN çeviride TR’ye düşer.

2. **Red-flag soruları**  
   - `red_flag_questions.json`: `question_tr`, `question_en`, `reason_tr`, `reason_en`.  
   - Orkestratör locale’e göre soru ve acil açıklamasını seçer; EN’de talimatlar İngilizce.

3. **Bağlam soruları**  
   - `context_questions.json`: `question_tr`, `question_en`, `choices_tr`, `choices_en` (varsa).  
   - Orkestratör locale’e göre metin ve seçenekleri seçer.

## Mesajlar (app/core/i18n.py)

- `get_text(locale, key, fallback=None)`: Locale’e göre metin döndürür.  
- Anahtarlar: `EMPTY_INPUT`, `SESSION_COMPLETE`, `TURN_FAILED`, `safety_note_1`, `safety_note_2`, `rate_limit_exceeded`, `error_internal`.  
- Kullanım: triage route (EMPTY_INPUT, TURN_FAILED), orkestratör (SESSION_COMPLETE, safety_notes).

## Yeni dil / metin ekleme

1. **Soru bankası**: `symptom_question_bank_en.json` benzeri yeni dosya (örn. `symptom_question_bank_de.json`) ve selector’da locale’e göre yükleme veya `question_xx` alanları ekleme.  
2. **Red-flag / context**: İlgili JSON’a `question_en` / `reason_en` (veya yeni dil) ekleyip orkestratörde locale dallanmasını genişlet.  
3. **i18n mesajları**: `_MESSAGES_TR` ve `_LOCALES["en-US"]` (veya yeni locale) içine yeni key ve çevirileri ekle.
