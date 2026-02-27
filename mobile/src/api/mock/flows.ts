import type { Envelope, TriageTurnRequest } from "@/src/state/types";

type FlowMem = Record<string, any>;

type FlowStep = {
  match: (req: TriageTurnRequest, mem: FlowMem) => boolean;
  reply: (req: TriageTurnRequest, mem: FlowMem) => Envelope;
};

export function buildFlows(): FlowStep[] {
  const flows: FlowStep[] = [];

  // ─── Flow A: Headache → Migraine ───
  flows.push({
    match: (req, mem) =>
      mem.flow === "HEADACHE" ||
      (req.user_message.toLowerCase().includes("baş") &&
        req.user_message.toLowerCase().includes("ağr")),
    reply: (req, mem) => {
      mem.flow = "HEADACHE";
      mem.session_id = mem.session_id || "S_HEADACHE";
      mem.turn = (mem.turn || 0) + 1;

      // Turn 1: initial symptom → ask about nausea
      if (req.user_message && mem.turn === 1) {
        return {
          type: "QUESTION",
          session_id: mem.session_id,
          turn_index: 1,
          payload: {
            question_id: "q_001",
            canonical: "bulantı",
            question_tr: "Mide bulantısı var mı?",
            answer_type: "yes_no",
            choices_tr: ["yes", "no"],
            why_asking_tr: "Migren ve benzeri durumları ayırt etmek için.",
          },
        };
      }

      // Turn 2: answered nausea → ask about vision
      if (req.answer?.canonical === "bulantı") {
        mem.nausea = req.answer.value;
        return {
          type: "QUESTION",
          session_id: mem.session_id,
          turn_index: 2,
          payload: {
            question_id: "q_002",
            canonical: "bulanık görme",
            question_tr: "Bulanık görme veya görme bozukluğu var mı?",
            answer_type: "yes_no",
            choices_tr: ["yes", "no"],
            why_asking_tr: "Görsel aura migren belirtisi olabilir.",
          },
        };
      }

      // Turn 3: answered vision → RESULT
      if (req.answer?.canonical === "bulanık görme") {
        const hasNausea = mem.nausea === "yes";
        const hasVision = req.answer.value === "yes";
        return {
          type: "RESULT",
          session_id: mem.session_id,
          turn_index: 3,
          payload: {
            urgency: "ROUTINE",
            recommended_specialty: { id: "neurology", name_tr: "Nöroloji" },
            top_conditions: [
              { disease_label: "Migraine", score_0_1: hasNausea && hasVision ? 0.56 : 0.42 },
              { disease_label: "(vertigo) Paroymsal  Positional Vertigo", score_0_1: 0.22 },
            ],
            doctor_ready_summary_tr: [
              "Baş ağrısı mevcut.",
              `Bulantı: ${hasNausea ? "evet" : "hayır"}.`,
              `Bulanık görme: ${hasVision ? "evet" : "hayır"}.`,
            ],
            safety_notes_tr: [
              "Bu bir ön değerlendirmedir, teşhis değildir.",
              "Ani şiddetli baş ağrısı, konuşma bozukluğu, tek taraflı güçsüzlük olursa acile başvur.",
            ],
          },
        };
      }

      return {
        type: "ERROR",
        session_id: mem.session_id,
        turn_index: mem.turn,
        payload: { code: "MOCK_FLOW_ERROR", message_tr: "Mock baş ağrısı akışı adımı bulunamadı." },
      };
    },
  });

  // ─── Flow B: UTI ───
  flows.push({
    match: (req, mem) =>
      mem.flow === "UTI" ||
      req.user_message.toLowerCase().includes("idrar") ||
      req.user_message.toLowerCase().includes("yanıyor"),
    reply: (req, mem) => {
      mem.flow = "UTI";
      mem.session_id = mem.session_id || "S_UTI";
      mem.turn = (mem.turn || 0) + 1;

      if (req.user_message && mem.turn === 1) {
        return {
          type: "QUESTION",
          session_id: mem.session_id,
          turn_index: 1,
          payload: {
            question_id: "q_u1",
            canonical: "ateş",
            question_tr: "Ateşiniz var mı?",
            answer_type: "yes_no",
            choices_tr: ["yes", "no"],
            why_asking_tr: "Ateş varlığı durumun ciddiyetini belirler.",
          },
        };
      }

      if (req.answer?.canonical === "ateş") {
        return {
          type: "RESULT",
          session_id: mem.session_id,
          turn_index: 2,
          payload: {
            urgency: "ROUTINE",
            recommended_specialty: { id: "urology_internal", name_tr: "Üroloji (gerekirse Dahiliye)" },
            top_conditions: [
              { disease_label: "Urinary tract infection", score_0_1: 0.61 },
            ],
            doctor_ready_summary_tr: [
              "İdrar yaparken yanma mevcut.",
              "Sık idrara çıkma mevcut.",
              `Ateş: ${req.answer.value === "yes" ? "var" : "yok"}.`,
            ],
            safety_notes_tr: [
              "Bu bir ön değerlendirmedir, teşhis değildir.",
              "Yüksek ateş/titreme veya yan ağrısı olursa aynı gün değerlendirme gerekebilir.",
            ],
          },
        };
      }

      return {
        type: "ERROR",
        session_id: mem.session_id,
        turn_index: mem.turn,
        payload: { code: "MOCK_FLOW_ERROR", message_tr: "Mock UTI akışı adımı bulunamadı." },
      };
    },
  });

  // ─── Flow C: EMERGENCY ───
  flows.push({
    match: (req) => {
      const t = req.user_message.toLowerCase();
      return (
        t.includes("göğüs") &&
        (t.includes("bask") || t.includes("ağr")) &&
        (t.includes("ter") || t.includes("nefes"))
      );
    },
    reply: (_req, _mem) => ({
      type: "EMERGENCY",
      session_id: "S_EMERGENCY",
      turn_index: 1,
      payload: {
        urgency: "EMERGENCY",
        reason_tr: "Göğüs baskısı + nefes darlığı/terleme acil değerlendirme gerektirebilir.",
        instructions_tr: [
          "112'yi ara veya en yakın acile başvur.",
          "Yalnızsan bir yakınını haberdar et.",
          "Belirti artıyorsa bekleme.",
        ],
      },
    }),
  });

  return flows;
}
