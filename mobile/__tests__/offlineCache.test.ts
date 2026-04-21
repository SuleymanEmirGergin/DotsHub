/**
 * Unit tests for the offline-results cache.
 *
 * Runs against the in-memory fallback — under the `testEnvironment: "node"`
 * jest config the optional `@react-native-async-storage/async-storage`
 * require returns a shape that doesn't satisfy the `AsyncStorageLike`
 * interface (or throws), so the cache transparently uses its internal
 * `memoryStore` Map. That's the whole point of the fallback: tests don't
 * need to mock the native module.
 */
import {
  __resetOfflineCacheForTests,
  clearCachedResults,
  getCachedResults,
  saveResult,
  type CachedSession,
} from "../src/state/offlineCache";
import type { Envelope } from "../src/state/types";

beforeEach(async () => {
  __resetOfflineCacheForTests();
  await clearCachedResults();
});

function resultEnvelope(sessionId: string, specialtyTr = "Dahiliye"): Envelope {
  return {
    type: "RESULT",
    session_id: sessionId,
    turn_index: 3,
    payload: {
      urgency: "ROUTINE",
      recommended_specialty: { id: "internal", name_tr: specialtyTr },
      top_conditions: [],
      doctor_ready_summary_tr: [],
      safety_notes_tr: [],
      confidence_0_1: 0.82,
      confidence_label_tr: "Yüksek",
      stop_reason: "confidence_reached",
    },
  };
}

function emergencyEnvelope(sessionId: string): Envelope {
  return {
    type: "EMERGENCY",
    session_id: sessionId,
    turn_index: 1,
    payload: {
      urgency: "EMERGENCY",
      reason_tr: "Göğüs ağrısı + nefes darlığı",
      instructions_tr: ["112'yi arayın"],
    },
  };
}

describe("offlineCache", () => {
  it("starts empty when no data has been written", async () => {
    const entries = await getCachedResults();
    expect(entries).toEqual([]);
  });

  it("persists a RESULT envelope as a summary row", async () => {
    await saveResult(resultEnvelope("sess-1", "Kardiyoloji"));
    const entries = await getCachedResults();

    expect(entries).toHaveLength(1);
    expect(entries[0].id).toBe("sess-1");
    expect(entries[0].envelope_type).toBe("RESULT");
    expect(entries[0].recommended_specialty_tr).toBe("Kardiyoloji");
    expect(entries[0].confidence_label_tr).toBe("Yüksek");
    expect(entries[0].confidence_0_1).toBe(0.82);
    expect(entries[0].stop_reason).toBe("confidence_reached");
    // created_at is set by the cache, should be a valid ISO-ish string.
    expect(typeof entries[0].created_at).toBe("string");
    expect(new Date(entries[0].created_at).toString()).not.toBe(
      "Invalid Date",
    );
  });

  it("persists an EMERGENCY envelope with the reason as the summary line", async () => {
    await saveResult(emergencyEnvelope("sess-emerg"));
    const entries = await getCachedResults();

    expect(entries).toHaveLength(1);
    expect(entries[0].id).toBe("sess-emerg");
    expect(entries[0].envelope_type).toBe("EMERGENCY");
    // We reuse `recommended_specialty_tr` as the visible summary line
    // for emergencies so HistoryScreen doesn't need a special branch.
    expect(entries[0].recommended_specialty_tr).toContain("Göğüs ağrısı");
  });

  it("ignores QUESTION and ERROR envelopes", async () => {
    const question: Envelope = {
      type: "QUESTION",
      session_id: "sess-q",
      turn_index: 0,
      payload: {
        question_id: "q1",
        canonical: "pain_location",
        question_tr: "Ağrı nerede?",
        answer_type: "free_text",
      },
    };
    const err: Envelope = {
      type: "ERROR",
      session_id: "sess-e",
      turn_index: 0,
      payload: { code: "BACKEND_DOWN", message_tr: "Hata" },
    };

    await saveResult(question);
    await saveResult(err);
    expect(await getCachedResults()).toEqual([]);
  });

  it("puts the newest entry first (LIFO display order)", async () => {
    await saveResult(resultEnvelope("sess-A", "A"));
    await saveResult(resultEnvelope("sess-B", "B"));
    await saveResult(resultEnvelope("sess-C", "C"));

    const entries = await getCachedResults();
    expect(entries.map((e: CachedSession) => e.id)).toEqual([
      "sess-C",
      "sess-B",
      "sess-A",
    ]);
  });

  it("caps the cache at 10 entries and drops the oldest", async () => {
    for (let i = 0; i < 12; i++) {
      await saveResult(resultEnvelope(`sess-${i}`, `S${i}`));
    }
    const entries = await getCachedResults();
    expect(entries).toHaveLength(10);
    // The two oldest (sess-0, sess-1) must have been evicted.
    const ids = entries.map((e: CachedSession) => e.id);
    expect(ids).toContain("sess-11");
    expect(ids).toContain("sess-2");
    expect(ids).not.toContain("sess-1");
    expect(ids).not.toContain("sess-0");
  });

  it("dedupes by session_id: re-saving bumps the existing row to the top", async () => {
    await saveResult(resultEnvelope("sess-dup", "First"));
    await saveResult(resultEnvelope("sess-other", "Other"));
    await saveResult(resultEnvelope("sess-dup", "Second"));

    const entries = await getCachedResults();
    expect(entries).toHaveLength(2);
    expect(entries[0].id).toBe("sess-dup");
    expect(entries[0].recommended_specialty_tr).toBe("Second");
    expect(entries[1].id).toBe("sess-other");
  });

  it("clearCachedResults() empties the cache", async () => {
    await saveResult(resultEnvelope("sess-x"));
    expect((await getCachedResults()).length).toBe(1);

    await clearCachedResults();
    expect(await getCachedResults()).toEqual([]);
  });

  it("handles a null/absent session_id by synthesising an id", async () => {
    const env = resultEnvelope("placeholder");
    // @ts-expect-error — simulating a legacy envelope without session_id.
    env.session_id = null;

    await saveResult(env);
    const entries = await getCachedResults();
    expect(entries).toHaveLength(1);
    expect(entries[0].id).toMatch(/^cached-\d+/);
  });
});
