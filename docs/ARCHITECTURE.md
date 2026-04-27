# Mimari özet

TriAIge: ön-triyaj asistanı — backend, mobil (Expo) ve dashboard (Next.js) bileşenleri.

---

## Yüksek seviye akış

```mermaid
flowchart LR
  subgraph Client
    M[Mobil Expo]
    D[Dashboard Next.js]
  end
  subgraph Backend
    API[FastAPI /v1]
    Triage[Triage Turn]
    Summary[Summary Email / Export]
    Push[Push Token]
  end
  subgraph Data
    Supabase[(Supabase)]
    Redis[(Redis opsiyonel)]
  end
  M --> API
  D --> API
  API --> Triage
  API --> Summary
  API --> Push
  Triage --> Supabase
  Summary --> Supabase
  API --> Redis
```

---

## Mobil (Expo) akışı

```mermaid
flowchart TD
  A[Giriş / Intro] --> B[Serbest metin semptom]
  B --> C[POST /v1/triage/turn]
  C --> D{Sonuç?}
  D -->|QUESTION| E[Soru ekranı]
  E --> C
  D -->|RESULT| F[Sonuç ekranı]
  F --> G[Özet e-posta / Metin indir / Paylaş]
  F --> H[Push token kaydı]
  D -->|EMERGENCY| I[Acil ekranı]
  D -->|ERROR| J[Hata ekranı + Tekrar dene]
  A --> K[Dil ekranı]
  K --> L[AsyncStorage + locale]
```

- **i18n:** AsyncStorage + expo-localization; TR/EN/DE/RU/AR; Arapça RTL.
- **API:** triage turn, feedback, send-summary, export-summary, push-token.

---

## Backend endpoint’ler (özet)

| Prefix / Endpoint | Açıklama |
|-------------------|----------|
| `POST /v1/triage/turn` | Oturum başlatma, cevap, sonuç (tek endpoint). |
| `POST /v1/triage/feedback` | Kullanıcı oylaması (up/down). |
| `POST /v1/triage/send-summary` | Özet e-postası (session_id, email, locale). Rate limit: 5/dk (export-summary ile paylaşır). |
| `POST /v1/triage/export-summary` | Özet metin (payload, locale). Rate limit: 5/dk (send-summary ile paylaşır). |
| `POST /v1/triage/push-token` | Expo Push Token kaydı. |
| `GET /v1/facilities` | Tesis keşfi. |
| `GET /health` | Liveness + Supabase durumu. |

---

## Veri (Supabase)

- **triage_sessions_v5 / triage_sessions:** Oturum kayıtları; send-summary session’ı buradan okur.
- **Feedback / admin tabloları:** Dashboard ve analitik için.

Redis: rate limit (triage, feedback, send-summary, export-summary) için opsiyonel; yoksa in-memory kullanılır. send-summary ve export-summary IP başına 5/dk paylaşımlı limit kullanır.
