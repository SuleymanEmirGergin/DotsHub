# Serbest metin cevaplarının yapılandırılması

Kullanıcı süre/şiddet/zamanlama sorularına serbest metin cevap verdiğinde bu metinler otomatik parse edilir; sonuçlar hem stop condition hem doktor özeti için kullanılır.

## Bileşenler

### 1. `duration_parse.py`
- **`extract_duration_days(text)`**: Türkçe süre ifadelerini güne çevirir.
- Örnekler: "3 gündür", "1 haftadır", "2 aydır", "5" → 3, 7, 60, 5.
- Kalıplar: `gündür`, `gün`, `haftadır`, `hafta`, `aydır`, `ay` (Unicode u/ü uyumlu).

### 2. `free_text_parse.py`
- **`parse_duration(text)`**: `extract_duration_days` sarmalayıcı.
- **`parse_severity(text)`**: 1–10 şiddet.
  - Sayı: "7", "7/10" → 7.
  - Sözel: "hafif" → ~2, "orta" → ~6, "şiddetli" → ~8.
- **`parse_timing(text)`**: "sabah kalkınca", "gece" → sabah / akşam / gece / gündüz.
- **`parse_free_text_answer(canonical, raw_value)`**: Canonical semptom adına göre uygun parser’ları çalıştırır; `{ duration_days?, severity_0_10?, timing? }` döner.
- **Canonical setleri** (modül içinde):
  - **DURATION_CANONICALS**: öksürük süresi, baş ağrısı süresi, karın ağrısı süresi, ateş süresi, ishal süresi, boğaz ağrısı süresi, göğüs ağrısı süresi.
  - **SEVERITY_CANONICALS**: ağrı şiddeti.
  - **TIMING_CANONICALS**: öksürük gece artışı, baş ağrısı sabah artışı + süre soruları.

## Akış

1. **Cevap kaydı**: `handle_turn` içinde `state.answers[canonical] = answer_value` atandıktan sonra `parse_free_text_answer(canonical, answer_value)` çağrılır.
2. **Saklama**: Sonuç boş değilse `state.parsed_answers[canonical] = parsed` yazılır.
3. **Stop condition**: `_should_stop_v4` çağrılırken `state.parsed_answers` → `parsed_to_symptom_item` ile semptom benzeri dict’lere çevrilir ve `structured_symptoms["symptoms"]` listesine eklenir; böylece `onset_or_duration_present` ve `severity_estimated` güncellenir.
4. **Sonuç**: `_build_result_payload` hem `doctor_ready_summary_tr` satırlarına süre/şiddet/zamanlama cümlelerini ekler hem de `parsed_answers` alanını payload’da döner.

## Yeni canonical ekleme

- Süre sorusu: `free_text_parse.DURATION_CANONICALS` set’ine canonical adını ekle (örn. "yeni_semptom_süresi").
- Şiddet: `SEVERITY_CANONICALS`’a ekle.
- Zamanlama: `TIMING_CANONICALS`’a ekle.
- Ek sözel şiddet ifadesi: `SEVERITY_MAP` ve `SEVERITY_VALUES` listelerini güncelle.

## Doktor özeti örneği

Parse edilen cevaplar özet satırına şu formatta eklenir:
- "Öksürük süresi: 3 gündür."
- "Ağrı şiddeti: şiddet 7/10."
- "Baş ağrısı süresi: 2 gündür, sabah."
