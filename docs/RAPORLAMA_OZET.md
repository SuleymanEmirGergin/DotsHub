# Raporlama ve özet

Doktor özeti (cümle formatı) ve oturum sonucunun metin olarak dışa aktarılması.

---

## 1. Doktor özeti (cümle formatı)

Sonuç ekranında “Doktora söyleyebileceğiniz özet” hem liste hem cümle olarak sunulur.

- **`doctor_ready_summary_tr`**: Satır satır liste (mevcut belirtiler, var/yok cevapları, süre/şiddet/zamanlama).
- **`doctor_ready_summary_sentence_tr`**: Tek veya birkaç cümle halinde akıcı özet. Örnek: *"3 gündür öksürük var, geceleri artıyor. Balgam var. Ateş yok."*

Cümle formatı, süre (`parsed_answers` → `duration_days`) ve zamanlama (`timing`) ile birleştirilerek üretilir; aynı belirti hem süre hem “var” olarak tek cümlede geçer (örn. “3 gündür öksürük var, geceleri artıyor”).

**Üretim:** `orchestrator._build_doctor_summary_sentence(state)` — RESULT payload oluşturulurken çağrılır; payload içinde `doctor_ready_summary_sentence_tr` alanı döner.

---

## 2. Export (yapılandırılmış metin)

Oturum sonucunun düz metin olarak indirilmesi veya e-posta ile uyumlu kullanımı.

- **Servis:** `backend/app/services/export_summary.py`
  - **`build_export_text(payload, locale="tr-TR")`**: RESULT payload’dan başlık, önerilen branş, aciliyet, doktor özeti (cümle veya liste), olası durumlar ve uyarıları içeren metin üretir. `locale` ile TR/EN başlık ve etiketler seçilir.

- **Endpoint:** `POST /v1/triage/export-summary`
  - **Body:** `{ "payload": { ... }, "locale": "tr-TR" }` — `payload`, triage turn RESULT cevabındaki `payload` alanı (aynı yapı).
  - **Response:** `text/plain` — indirilebilir .txt veya e-posta gövdesi olarak kullanılabilir.

Frontend, kullanıcı “İndir” veya “Metin olarak kaydet” dediğinde son RESULT payload’ı bu endpoint’e gönderip dönen metni dosya olarak kaydedebilir.

---

## 3. E-posta özeti ile uyum

- **`POST /v1/triage/send-summary`**: Oturum özetini e-posta ile gönderir (session_id + email). E-posta gövdesi `email_summary.build_summary_body` ile üretilir.
- İsterseniz e-posta gövdesi için `export_summary.build_export_text` çıktısı da kullanılabilir; böylece e-posta ile indirilen metin aynı formatta olur.

---

## 4. PDF (opsiyonel)

PDF üretimi için ek kütüphane gerekir (örn. reportlab, weasyprint). Şu an yalnızca metin export’u vardır; PDF’e geçmek için `build_export_text` çıktısını bir PDF kütüphanesi ile sayfaya dönüştürebilir veya ayrı bir `build_export_pdf(payload, locale)` servisi ekleyebilirsiniz.
