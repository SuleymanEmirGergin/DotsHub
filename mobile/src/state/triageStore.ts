import { create } from "zustand";
import type {
  Envelope,
  QuestionPayload,
  ResultPayload,
  EmergencyPayload,
  Msg,
} from "./types";

type TriageState = {
  sessionId: string | null;
  turnIndex: number;
  messages: Msg[];
  pendingQuestion: QuestionPayload | null;
  result: ResultPayload | null;
  emergency: EmergencyPayload | null;
  error: { code: string; message_tr: string } | null;
  loading: boolean;

  acceptIntro: boolean;

  setAcceptIntro: (v: boolean) => void;
  appendMessage: (m: Msg) => void;
  setLoading: (v: boolean) => void;
  resetSession: () => void;
  applyEnvelope: (env: Envelope) => void;
};

export const useTriageStore = create<TriageState>((set, get) => ({
  sessionId: null,
  turnIndex: 0,
  messages: [],
  pendingQuestion: null,
  result: null,
  emergency: null,
  error: null,
  loading: false,

  acceptIntro: false,

  setAcceptIntro: (v) => set({ acceptIntro: v }),

  setLoading: (v) => set({ loading: v }),

  appendMessage: (m) => set({ messages: [...get().messages, m] }),

  resetSession: () =>
    set({
      sessionId: null,
      turnIndex: 0,
      messages: [],
      pendingQuestion: null,
      result: null,
      emergency: null,
      error: null,
      loading: false,
    }),

  applyEnvelope: (env) => {
    const state = get();
    // Remove loading bubble if present
    const msgs = state.messages.filter(
      (m) => !(m.role === "assistant" && m.text === "Değerlendiriyorum…")
    );

    set({
      sessionId: env.session_id,
      turnIndex: env.turn_index,
      messages: msgs,
      loading: false,
    });

    if (env.type === "QUESTION") {
      const q = env.payload as QuestionPayload;
      set({ pendingQuestion: q, result: null, emergency: null, error: null });
      get().appendMessage({ role: "assistant", text: q.question_tr });
      return;
    }

    if (env.type === "RESULT") {
      const r = env.payload as ResultPayload;
      set({ result: r, pendingQuestion: null, emergency: null, error: null });
      get().appendMessage({
        role: "assistant",
        text: `Önerilen branş: ${r.recommended_specialty.name_tr}`,
      });
      return;
    }

    if (env.type === "EMERGENCY") {
      const e = env.payload as EmergencyPayload;
      set({ emergency: e, pendingQuestion: null, result: null, error: null });
      get().appendMessage({ role: "assistant", text: e.reason_tr });
      return;
    }

    // ERROR
    const err = env.payload as { code: string; message_tr: string };
    set({ error: err, pendingQuestion: null, result: null, emergency: null });
  },
}));
