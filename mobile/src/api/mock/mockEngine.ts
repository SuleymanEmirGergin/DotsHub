import type { Envelope, TriageTurnRequest } from "@/src/state/types";
import { buildFlows } from "./flows";

const mem: Record<string, any> = {};
const flows = buildFlows();

export function mockTurn(req: TriageTurnRequest): Envelope {
  if (!mem.session_id && req.session_id) {
    mem.session_id = req.session_id;
  }

  for (const f of flows) {
    if (f.match(req, mem)) return f.reply(req, mem);
  }

  // Generic fallback: ask for more info
  return {
    type: "QUESTION",
    session_id: req.session_id ?? "S_GENERIC",
    turn_index: 1,
    payload: {
      question_id: "q_generic",
      canonical: "free_text_more",
      question_tr:
        "Birkaç belirti daha söyleyebilir misin? (Örn: ateş, öksürük, bulantı...)",
      answer_type: "free_text",
    },
  };
}

/** Reset mock state (for new session) */
export function resetMock() {
  Object.keys(mem).forEach((k) => delete mem[k]);
}
