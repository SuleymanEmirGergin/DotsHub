import React, { useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { triageTurn } from "@/src/api/triageClient";
import { useTriageStore } from "@/src/state/triageStore";
import { inputHeights, tokens, touchTargetMin } from "@/src/ui/designTokens";
import { Badge, Card, MutedText, ScreenContainer, SectionTitle } from "@/src/ui/primitives";

const QUICK_CHIPS = ["Baş ağrısı", "Ateş", "Öksürük", "Karın ağrısı", "İdrar yanması"];
const LOADING_TEXT = "Değerlendiriyorum…";

export default function ChatScreen() {
  const [text, setText] = useState("");
  const flatListRef = useRef<FlatList>(null);
  const { sessionId, messages, loading, appendMessage, setLoading, applyEnvelope } =
    useTriageStore();

  async function onSend(msg?: string) {
    const t = (msg || text).trim();
    if (!t) return;

    appendMessage({ role: "user", text: t });
    setText("");
    setLoading(true);
    appendMessage({ role: "assistant", text: LOADING_TEXT });

    const env = await triageTurn({
      session_id: sessionId,
      locale: "tr-TR",
      user_message: t,
      answer: null,
    });
    applyEnvelope(env);
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={Platform.OS === "ios" ? 12 : 0}
    >
      <ScreenContainer style={styles.flex}>
        <View style={styles.headerWrap}>
          <SectionTitle style={styles.headerTitle}>Ön Değerlendirme</SectionTitle>
          <MutedText>
            Birkaç kısa soru soracağım, daha doğru yönlendireceğim.
          </MutedText>
        </View>

        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(_, i) => String(i)}
          style={styles.list}
          contentContainerStyle={styles.listContent}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
          renderItem={({ item }) => {
            const fromUser = item.role === "user";
            return (
              <View
                style={[
                  styles.bubble,
                  fromUser ? styles.bubbleUser : styles.bubbleAssistant,
                ]}
              >
                <Text
                  style={[
                    styles.bubbleText,
                    fromUser ? styles.bubbleTextUser : styles.bubbleTextAssistant,
                  ]}
                >
                  {item.text}
                </Text>
              </View>
            );
          }}
        />

        {messages.length === 0 ? (
          <View style={styles.chipsRow}>
            {QUICK_CHIPS.map((chip) => (
              <Badge key={chip} style={styles.chip}>
                <Pressable
                  onPress={() => onSend(chip)}
                  style={styles.chipPressable}
                  hitSlop={6}
                >
                  <Text style={styles.chipText}>{chip}</Text>
                </Pressable>
              </Badge>
            ))}
          </View>
        ) : null}

        <Card style={styles.inputCard}>
          <View style={styles.inputRow}>
            <TextInput
              value={text}
              onChangeText={setText}
              placeholder="Belirtini yaz…"
              placeholderTextColor={tokens.colors.textMuted}
              style={styles.input}
              editable={!loading}
              onSubmitEditing={() => onSend()}
              returnKeyType="send"
            />
            <Pressable
              onPress={() => onSend()}
              disabled={loading || !text.trim()}
              style={[
                styles.sendBtn,
                (loading || !text.trim()) && styles.sendBtnDisabled,
              ]}
            >
              <Text style={styles.sendBtnText}>Gönder</Text>
            </Pressable>
          </View>
        </Card>

        <MutedText style={styles.disclaimer}>Acil durumlarda 112'yi arayın.</MutedText>
      </ScreenContainer>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  headerWrap: {
    marginTop: tokens.spacing.lg,
    marginBottom: tokens.spacing.md,
  },
  headerTitle: {
    marginBottom: tokens.spacing.xs,
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: tokens.spacing.md,
  },
  bubble: {
    maxWidth: "86%",
    marginVertical: tokens.spacing.xs,
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
    borderRadius: tokens.radius.lg,
    borderWidth: 1,
  },
  bubbleUser: {
    alignSelf: "flex-end",
    backgroundColor: tokens.colors.primary,
    borderColor: tokens.colors.primary,
  },
  bubbleAssistant: {
    alignSelf: "flex-start",
    backgroundColor: tokens.colors.surface,
    borderColor: tokens.colors.border,
  },
  bubbleText: {
    ...tokens.typography.body,
  },
  bubbleTextUser: {
    color: "#FFFFFF",
  },
  bubbleTextAssistant: {
    color: tokens.colors.textPrimary,
  },
  chipsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: tokens.spacing.sm,
    marginBottom: tokens.spacing.md,
  },
  chip: {
    paddingVertical: 0,
    paddingHorizontal: 0,
    borderRadius: tokens.radius.pill,
    backgroundColor: tokens.colors.surface,
    borderColor: tokens.colors.border,
  },
  chipPressable: {
    minHeight: touchTargetMin,
    minWidth: 64,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.xs,
  },
  chipText: {
    ...tokens.typography.bodySmall,
    color: tokens.colors.textSecondary,
    fontWeight: "600",
  },
  inputCard: {
    padding: tokens.spacing.sm,
    borderRadius: tokens.radius.lg,
    marginBottom: tokens.spacing.sm,
    ...tokens.shadow.soft,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: tokens.spacing.sm,
  },
  input: {
    flex: 1,
    minHeight: inputHeights.md,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    borderRadius: tokens.radius.md,
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
    backgroundColor: tokens.colors.surface,
    color: tokens.colors.textPrimary,
    ...tokens.typography.body,
  },
  sendBtn: {
    minHeight: inputHeights.md,
    minWidth: 90,
    borderRadius: tokens.radius.md,
    backgroundColor: tokens.colors.primary,
    paddingHorizontal: tokens.spacing.md,
    alignItems: "center",
    justifyContent: "center",
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
  sendBtnText: {
    ...tokens.typography.button,
  },
  disclaimer: {
    textAlign: "center",
    marginBottom: tokens.spacing.md,
  },
});
