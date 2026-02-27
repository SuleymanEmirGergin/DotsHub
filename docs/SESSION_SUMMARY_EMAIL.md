# Oturum özeti e-posta

Triage oturumu bittikten sonra kullanıcının girdiği e-posta adresine özet e-postası gönderilir.

## Bileşenler

- **`app/services/email_summary.py`**: Özet metni üretir (`build_summary_body`) ve gönderici arayüzü ile gönderir (`send_session_summary_email`).
- **`app/services/email_sender_resend.py`**: Resend API ile gerçek gönderim (opsiyonel).
- **`app/api/routes/summary_email.py`**: `POST /v1/triage/send-summary` endpoint’i.

## Ortam değişkenleri

| Değişken | Açıklama |
|----------|----------|
| `SEND_SUMMARY_EMAIL` | `1` ise özet e-postası gönderimi açık; yoksa sadece log. |
| `RESEND_API_KEY` | Resend API anahtarı (Resend kullanılacaksa). |
| `RESEND_FROM` | Gönderen adres (örn. `noreply@yourdomain.com`). Boşsa Resend varsayılanı kullanılır. |

## main.py entegrasyonu

Router’ı uygulamaya ekleyin (genelde `/v1` prefix’i ile):

```python
from app.api.routes import summary_email

app.include_router(summary_email.router, prefix="/v1")
```

Böylece endpoint: `POST /v1/triage/send-summary`.

## İstek örneği

```json
POST /v1/triage/send-summary
Content-Type: application/json

{
  "session_id": "uuid-oturum-id",
  "email": "kullanici@example.com",
  "locale": "tr"
}
```

Yanıt: `{"status": "ok", "message": "Summary email sent or queued"}`

## Mobil / dashboard tarafı

Oturum sonuç ekranında kullanıcıdan e-posta alıp bu endpoint’e `session_id` ve `email` ile POST atabilirsiniz. Rate limit ve (isteğe bağlı) kimlik doğrulama eklenebilir.
