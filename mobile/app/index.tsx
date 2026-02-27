import React from "react";
import { SafeAreaView, StyleSheet } from "react-native";
import IntroScreen from "@/src/screens/IntroScreen";
import ChatScreen from "@/src/screens/ChatScreen";
import QuestionScreen from "@/src/screens/QuestionScreen";
import ResultScreen from "@/src/screens/ResultScreen";
import EmergencyScreen from "@/src/screens/EmergencyScreen";
import ErrorScreen from "@/src/screens/ErrorScreen";
import { useTriageStore } from "@/src/state/triageStore";
import { tokens } from "@/src/ui/designTokens";

/**
 * V4 routing hub - renders screen based on store state.
 *
 * Priority order:
 * 1. !acceptIntro -> IntroScreen
 * 2. emergency -> EmergencyScreen
 * 3. error -> ErrorScreen
 * 4. result -> ResultScreen
 * 5. pendingQuestion -> QuestionScreen
 * 6. default -> ChatScreen (free-text input)
 */
export default function Home() {
  const acceptIntro = useTriageStore((s) => s.acceptIntro);
  const pendingQuestion = useTriageStore((s) => s.pendingQuestion);
  const result = useTriageStore((s) => s.result);
  const emergency = useTriageStore((s) => s.emergency);
  const error = useTriageStore((s) => s.error);

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
