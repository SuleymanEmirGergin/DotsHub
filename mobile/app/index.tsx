import React from "react";
import { SafeAreaView, StyleSheet } from "react-native";
import IntroScreen from "@/src/screens/IntroScreen";
import ChatScreen from "@/src/screens/ChatScreen";
import QuestionScreen from "@/src/screens/QuestionScreen";
import ResultScreen from "@/src/screens/ResultScreen";
import EmergencyScreen from "@/src/screens/EmergencyScreen";
import ErrorScreen from "@/src/screens/ErrorScreen";
import HistoryScreen from "@/src/screens/HistoryScreen";
import SessionDetailScreen from "@/src/screens/SessionDetailScreen";
import SettingsScreen from "@/src/screens/SettingsScreen";
import { useTriageStore } from "@/src/state/triageStore";
import { tokens } from "@/src/ui/designTokens";

/**
 * V4 routing hub - renders screen based on store state.
 *
 * Priority order:
 * 1. showSessionDetailId -> SessionDetailScreen (top-most overlay; lets
 *      a user drilling from History → Detail back-stack out of the
 *      detail without losing the History list scroll position).
 * 2. showSettings -> SettingsScreen (overlay, preserves state behind)
 * 3. showHistory -> HistoryScreen (same pattern)
 * 4. !acceptIntro -> IntroScreen
 * 5. emergency -> EmergencyScreen
 * 6. error -> ErrorScreen
 * 7. result -> ResultScreen
 * 8. pendingQuestion -> QuestionScreen
 * 9. default -> ChatScreen (free-text input)
 */
export default function Home() {
  const acceptIntro = useTriageStore((s) => s.acceptIntro);
  const showHistory = useTriageStore((s) => s.showHistory);
  const setShowHistory = useTriageStore((s) => s.setShowHistory);
  const showSettings = useTriageStore((s) => s.showSettings);
  const setShowSettings = useTriageStore((s) => s.setShowSettings);
  const showSessionDetailId = useTriageStore((s) => s.showSessionDetailId);
  const setShowSessionDetailId = useTriageStore(
    (s) => s.setShowSessionDetailId,
  );
  const pendingQuestion = useTriageStore((s) => s.pendingQuestion);
  const result = useTriageStore((s) => s.result);
  const emergency = useTriageStore((s) => s.emergency);
  const error = useTriageStore((s) => s.error);

  // Session detail override — drilled into from History card tap.
  // Takes precedence over the History list so back returns to the
  // list (showHistory stays true under the detail).
  if (showSessionDetailId) {
    return (
      <SafeAreaView style={styles.safe}>
        <SessionDetailScreen
          sessionId={showSessionDetailId}
          onBack={() => setShowSessionDetailId(null)}
        />
      </SafeAreaView>
    );
  }

  // Settings screen override — takes precedence so the user can reach
  // settings from anywhere (intro, result, chat) without losing context.
  if (showSettings) {
    return (
      <SafeAreaView style={styles.safe}>
        <SettingsScreen onBack={() => setShowSettings(false)} />
      </SafeAreaView>
    );
  }

  // History screen override
  if (showHistory) {
    return (
      <SafeAreaView style={styles.safe}>
        <HistoryScreen
          onBack={() => setShowHistory(false)}
          onViewSession={(id) => setShowSessionDetailId(id)}
        />
      </SafeAreaView>
    );
  }

  let Screen;

  if (!acceptIntro) {
    Screen = IntroScreen;
  } else if (emergency) {
    Screen = EmergencyScreen;
  } else if (error) {
    Screen = ErrorScreen;
  } else if (result) {
    Screen = ResultScreen;
  } else if (pendingQuestion) {
    Screen = QuestionScreen;
  } else {
    Screen = ChatScreen;
  }

  return (
    <SafeAreaView style={styles.safe}>
      <Screen />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: tokens.colors.background,
  },
});
