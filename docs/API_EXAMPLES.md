# API Örnekleri

Temel endpoint’ler için `curl` örnekleri. `BASE` olarak API kök adresinizi kullanın (örn. `http://localhost:8000`).

## Sağlık Kontrolü

```bash
curl -s "${BASE}/health" | jq .
```

Örnek cevap: `{"status":"ok","service":"dotshub-api","version":"4.0.0","supabase":"ok"}`

---

## Triaj Turn (Yeni Oturum)

```bash
curl -s -X POST "${BASE}/v1/triage/turn" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: my-request-123" \
  -H "X-Device-ID: my-device-id" \
  -d '{
    "session_id": null,
    "locale": "tr-TR",
    "user_message": "Başım ağrıyor ve bulantı var"
  }' | jq .
```

Cevapta `envelope_type` (`QUESTION`, `RESULT`, `EMERGENCY` vb.), `session_id` ve (varsa) `question` yer alır. Sonraki turn’de aynı `session_id` gönderilir.

---

## Triaj Turn (Cevap ile Devam)

```bash
curl -s -X POST "${BASE}/v1/triage/turn" \
  -H "Content-Type: application/json" \
  -H "X-Device-ID: my-device-id" \
  -d '{
    "session_id": "<önceki_response.session_id>",
    "locale": "tr-TR",
    "user_message": "",
    "answer": { "canonical": "Baş ağrısı", "value": "Evet" }
  }' | jq .
```

---

## Rate Limit Header’ları

Triaj ve feedback isteklerinde cevap header’larında şunlar döner:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset` (saniye)
- `X-Request-ID`

429 alırsanız gövdede `reset_in_sec` kullanılabilir.

---

## Tesis Listesi (Facilities)

```bash
curl -s "${BASE}/v1/facilities?specialty=neurology&city=Istanbul&limit=5" | jq .
```

İsteğe bağlı konum ile (mesafeye göre sıralama):

```bash
curl -s "${BASE}/v1/facilities?specialty=cardiology&lat=41.0082&lon=28.9784&limit=5" | jq .
```

---

## Admin API (Örnek)

Admin endpoint’leri `ADMIN_API_KEY` veya Bearer token ile korunur. Örnek (key’i header’da):

```bash
curl -s "${BASE}/v1/admin/stats/overview?lookback_limit=100" \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY" | jq .
```

Admin istekleri ayrı rate limit’e tabidir (varsayılan 60/dk per IP).
