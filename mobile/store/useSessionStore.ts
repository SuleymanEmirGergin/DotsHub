/**
 * Zustand store V2 — Envelope + ui_hints handling.
 */

import { create } from 'zustand';
import {
  api,
  Envelope,
  QuestionPayload,
  ResultPayload,
  EmergencyPayload,
  ErrorPayload,
  CandidateCondition,
  DoctorReadySummary,
  FacilityDiscovery,
  Profile,
  SummaryResponse,
  ChatMessage,
  UiHints,
} from '../services/api';

export type SessionStatus = 'input' | 'chatting' | 'analyzing' | 'done' | 'emergency' | 'error';

interface SessionState {
  // Session
  sessionId: string | null;
  status: SessionStatus;
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;

  // Profile
  profile: Profile | null;

  // Current question hints
  currentUiHints: UiHints | null;
  currentAnswerType: string | null;
  currentChoices: string[];

  // Results
  candidates: CandidateCondition[];
  recommendedSpecialty: string | null;
  urgency: string | null;
  riskLevel: string | null;
  rationale: string[];
  emergencyWatchouts: string[];
  doctorSummary: DoctorReadySummary | null;
  specialtyScores: Record<string, any> | null;
  facilityDiscovery: FacilityDiscovery | null;

  // Emergency
  emergencyReason: string | null;
  emergencyInstructions: string[];

  // Summary
  summary: SummaryResponse | null;

  // Disclaimer
  disclaimer: string;

  // Actions
  setProfile: (profile: Profile) => void;
  startSession: (symptoms: string) => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
  fetchResult: () => Promise<void>;
  fetchSummary: () => Promise<void>;
  reset: () => void;
}

const initialState = {
  sessionId: null,
  status: 'input' as SessionStatus,
  messages: [],
  isLoading: false,
  error: null,
  profile: null,
  currentUiHints: null,
  currentAnswerType: null,
  currentChoices: [],
  candidates: [],
  recommendedSpecialty: null,
  urgency: null,
  riskLevel: null,
  rationale: [],
  emergencyWatchouts: [],
  doctorSummary: null,
  specialtyScores: null,
  facilityDiscovery: null,
  emergencyReason: null,
  emergencyInstructions: [],
  summary: null,
  disclaimer: 'Bu uygulama tanı koymaz; bilgilendirme ve yönlendirme amaçlıdır.',
};

function handleEnvelope(
  envelope: Envelope,
  currentMessages: ChatMessage[],
): Partial<SessionState> {
  const base: Partial<SessionState> = {
    sessionId: envelope.session_id,
    disclaimer: envelope.meta.disclaimer_tr,
    facilityDiscovery: envelope.type === 'RESULT' ? (envelope.meta.facility_discovery || null) : null,
  };

  switch (envelope.type) {
    case 'QUESTION': {
      const p = envelope.payload as QuestionPayload;
      const aiMsg: ChatMessage = {
        role: 'ai',
        content: p.question_tr,
        timestamp: envelope.meta.timestamp,
        metadata: {
          type: 'question',
          answer_type: p.answer_type,
          choices_tr: p.choices_tr,
          ui_hints: p.ui_hints,
        },
      };
      return {
        ...base,
        status: 'chatting',
        messages: [...currentMessages, aiMsg],
        isLoading: false,
        currentUiHints: p.ui_hints || null,
        currentAnswerType: p.answer_type,
        currentChoices: p.choices_tr || [],
      };
    }

    case 'RESULT': {
      const p = envelope.payload as ResultPayload;
      const aiMsg: ChatMessage = {
        role: 'ai',
        content: `Önerilen Branş: ${p.recommended_specialty_tr}`,
        timestamp: envelope.meta.timestamp,
        metadata: { type: 'result' },
      };
      return {
        ...base,
        status: 'done',
        messages: [...currentMessages, aiMsg],
        candidates: p.candidates_tr || [],
        recommendedSpecialty: p.recommended_specialty_tr,
        urgency: p.urgency,
        riskLevel: p.doctor_ready_summary_tr?.risk_level || null,
        rationale: p.rationale_tr || [],
        emergencyWatchouts: p.emergency_watchouts_tr || [],
        doctorSummary: p.doctor_ready_summary_tr || null,
        specialtyScores: p.specialty_scores || null,
        facilityDiscovery: envelope.meta.facility_discovery || null,
        isLoading: false,
        currentUiHints: null,
        currentAnswerType: null,
        currentChoices: [],
      };
    }

    case 'EMERGENCY': {
      const p = envelope.payload as EmergencyPayload;
      const aiMsg: ChatMessage = {
        role: 'ai',
        content: p.reason_tr,
        timestamp: envelope.meta.timestamp,
        metadata: { type: 'emergency' },
      };
      return {
        ...base,
        status: 'emergency',
        messages: [...currentMessages, aiMsg],
        emergencyReason: p.reason_tr,
        emergencyInstructions: p.instructions_tr || [],
        isLoading: false,
        currentUiHints: null,
        currentAnswerType: null,
        currentChoices: [],
      };
    }

    case 'ERROR': {
      const p = envelope.payload as ErrorPayload;
      return {
        ...base,
        status: 'error',
        error: p.message_tr,
        isLoading: false,
      };
    }

    default:
      return { ...base, isLoading: false };
  }
}

export const useSessionStore = create<SessionState>((set, get) => ({
  ...initialState,

  setProfile: (profile: Profile) => set({ profile }),

  startSession: async (symptoms: string) => {
    set({ isLoading: true, error: null });

    try {
      const userMessage: ChatMessage = {
        role: 'user',
        content: symptoms,
        timestamp: new Date().toISOString(),
      };

      const { profile } = get();
      const envelope = await api.startSession(symptoms, profile || undefined);

      const updates = handleEnvelope(envelope, [userMessage]);
      set(updates as any);
    } catch (error: any) {
      set({ error: error.message || 'Bağlantı sorunu var. Tekrar dene.', isLoading: false });
    }
  },

  sendMessage: async (message: string) => {
    const { sessionId, messages } = get();
    if (!sessionId) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };

    const updatedMessages = [...messages, userMessage];
    set({ messages: updatedMessages, isLoading: true, error: null });

    try {
      const envelope = await api.sendMessage(sessionId, message);
      const updates = handleEnvelope(envelope, updatedMessages);
      set(updates as any);
    } catch (error: any) {
      set({ error: error.message || 'Bağlantı sorunu var. Tekrar dene.', isLoading: false });
    }
  },

  fetchResult: async () => {
    const { sessionId } = get();
    if (!sessionId) return;

    try {
      const envelope = await api.getResult(sessionId);
      if (envelope.type === 'RESULT') {
        const p = envelope.payload as ResultPayload;
        set({
          candidates: p.candidates_tr || [],
          recommendedSpecialty: p.recommended_specialty_tr,
          urgency: p.urgency,
          riskLevel: p.doctor_ready_summary_tr?.risk_level || null,
          rationale: p.rationale_tr || [],
          emergencyWatchouts: p.emergency_watchouts_tr || [],
          doctorSummary: p.doctor_ready_summary_tr || null,
          specialtyScores: p.specialty_scores || null,
          facilityDiscovery: envelope.meta.facility_discovery || null,
        });
      }
    } catch (error: any) {
      console.error('Error fetching result:', error);
    }
  },

  fetchSummary: async () => {
    const { sessionId } = get();
    if (!sessionId) return;

    try {
      const summary = await api.getSummary(sessionId);
      set({ summary });
    } catch (error: any) {
      console.error('Error fetching summary:', error);
    }
  },

  reset: () => set(initialState),
}));
