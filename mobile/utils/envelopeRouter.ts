// Envelope routing - supports legacy V5 and current V1 envelope shapes.

type AnyEnvelope = {
  envelope_type?: "EMERGENCY" | "SAME_DAY" | "QUESTION" | "RESULT";
  type?: "EMERGENCY" | "QUESTION" | "RESULT" | "ERROR";
  payload?: any;
  stop_reason?: string;
  meta?: any;
  session_id?: string;
};

function normalizeQuestionPayload(payload: any) {
  if (payload?.question?.text) return payload;
  return {
    ...payload,
    question: {
      text: payload?.question_tr ?? payload?.question_text ?? "Belirtini biraz daha aciklar misin?",
    },
  };
}

function normalizeResultPayload(payload: any) {
  const probable = Array.isArray(payload?.probable_conditions)
    ? payload.probable_conditions
    : Array.isArray(payload?.top_conditions)
      ? payload.top_conditions.map((c: any) => ({
          name: c?.disease_label ?? "Bilinmiyor",
          score: Number(c?.score_0_1 ?? 0),
        }))
      : [];

  return {
    ...payload,
    recommended_specialty_id:
      payload?.recommended_specialty_id ?? payload?.recommended_specialty?.id ?? null,
    probable_conditions: probable,
  };
}

export function routeEnvelope(env: AnyEnvelope) {
  const envelopeType = env.envelope_type ?? env.type;

  switch (envelopeType) {
    case "EMERGENCY":
      return { screen: "EmergencyModal", params: { ...env } };
    case "SAME_DAY":
      return { screen: "SameDay", params: { ...env } };
    case "QUESTION":
      return {
        screen: "Chat",
        params: {
          ...env,
          payload: normalizeQuestionPayload(env.payload),
        },
      };
    case "RESULT":
      return {
        screen: "Result",
        params: {
          ...env,
          payload: normalizeResultPayload(env.payload),
        },
      };
    default:
      return { screen: "Home", params: {} };
  }
}
