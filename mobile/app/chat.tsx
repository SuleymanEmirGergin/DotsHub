/**
 * Screen 2 - Chat Interface (V2 with quick replies + Envelope)
 */

import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  FlatList, KeyboardAvoidingView, Platform, ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, FontSizes, BorderRadius } from '../constants/theme';
import { useSessionStore } from '../store/useSessionStore';
import ChatBubble from '../components/ChatBubble';
import EmergencyBanner from '../components/EmergencyBanner';

const QUICK_REPLIES = [
  { label: 'Evet', value: 'Evet' },
  { label: 'Hayır', value: 'Hayır' },
  { label: 'Bilmiyorum', value: 'Bilmiyorum' },
];

export default function ChatScreen() {
  const router = useRouter();
  const {
    messages, status, isLoading,
    emergencyReason, emergencyInstructions,
    currentUiHints, currentAnswerType, currentChoices,
    sendMessage,
  } = useSessionStore();

  const [input, setInput] = useState('');
  const flatListRef = useRef<FlatList>(null);

  // Show quick replies based on ui_hints from Envelope or answer_type
  const showQuickReplies = (
    currentUiHints?.quick_replies === true
    || currentAnswerType === 'yes_no'
    || (currentAnswerType === 'multiple_choice' && currentChoices.length > 0)
  ) && !isLoading && status === 'chatting';

  useEffect(() => {
    if (status === 'done') {
      const timer = setTimeout(() => router.push('/result'), 1500);
      return () => clearTimeout(timer);
    }
  }, [status]);

  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [messages.length, isLoading]);

  const handleSend = async (text?: string) => {
    const msg = (text || input).trim();
    if (!msg || isLoading) return;
    setInput('');
    await sendMessage(msg);
  };

  const isDisabled = status === 'done' || status === 'emergency';

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}
    >
      {status === 'emergency' && emergencyInstructions.length > 0 && (
        <EmergencyBanner
          instructions={emergencyInstructions}
          reason={emergencyReason || undefined}
        />
      )}

      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={(_, index) => index.toString()}
        renderItem={({ item }) => (
          <ChatBubble role={item.role as any} content={item.content} timestamp={item.timestamp} />
        )}
        contentContainerStyle={styles.messageList}
        ListFooterComponent={
          isLoading ? (
            <View style={styles.typingRow}>
              <View style={styles.typingBubble}>
                <View style={styles.typingDots}>
                  <View style={[styles.dot, styles.dot1]} />
                  <View style={[styles.dot, styles.dot2]} />
                  <View style={[styles.dot, styles.dot3]} />
                </View>
                <Text style={styles.typingText}>Yazıyor…</Text>
              </View>
            </View>
          ) : status === 'done' ? (
            <View style={styles.doneRow}>
              <Text style={styles.doneText}>Analiz tamamlandı. Sonuçlara yönlendiriliyorsunuz...</Text>
            </View>
          ) : null
        }
      />

      {/* Quick Replies — uses choices_tr from envelope, fallback to defaults */}
      {showQuickReplies && (
        <View style={styles.quickReplies}>
          {(currentChoices.length > 0
            ? currentChoices.map((c) => ({ label: c, value: c }))
            : QUICK_REPLIES
          ).map((qr) => (
            <TouchableOpacity
              key={qr.value}
              style={styles.quickReplyButton}
              onPress={() => handleSend(qr.value)}
            >
              <Text style={styles.quickReplyText}>{qr.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {!isDisabled && (
        <View style={styles.inputBar}>
          <TextInput
            style={styles.textInput}
            placeholder="Cevabınızı yazın..."
            placeholderTextColor={Colors.textLight}
            value={input}
            onChangeText={setInput}
            editable={!isLoading}
            onSubmitEditing={() => handleSend()}
            returnKeyType="send"
          />
          <TouchableOpacity
            style={[styles.sendButton, (!input.trim() || isLoading) && styles.sendButtonDisabled]}
            onPress={() => handleSend()}
            disabled={!input.trim() || isLoading}
          >
            <Text style={styles.sendIcon}>➤</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Safety note */}
      {status === 'chatting' && (
        <View style={styles.safetyNote}>
          <Text style={styles.safetyNoteText}>Acil olabilecek belirtiler varsa 112'yi arayın.</Text>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.backgroundChat },
  messageList: { paddingVertical: Spacing.md, flexGrow: 1 },
  inputBar: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm, backgroundColor: Colors.background,
    borderTopWidth: 1, borderTopColor: Colors.borderLight,
  },
  textInput: {
    flex: 1, backgroundColor: Colors.backgroundSecondary, borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm + 2,
    fontSize: FontSizes.md, color: Colors.textPrimary, maxHeight: 100,
  },
  sendButton: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: Colors.primary,
    justifyContent: 'center', alignItems: 'center', marginLeft: Spacing.sm,
  },
  sendButtonDisabled: { opacity: 0.4 },
  sendIcon: { color: Colors.textWhite, fontSize: 18, fontWeight: '700' },
  // Quick replies
  quickReplies: {
    flexDirection: 'row', justifyContent: 'center', gap: Spacing.sm,
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    backgroundColor: Colors.background, borderTopWidth: 1, borderTopColor: Colors.borderLight,
  },
  quickReplyButton: {
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full, borderWidth: 1.5, borderColor: Colors.primary,
    backgroundColor: Colors.primaryLight,
  },
  quickReplyText: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.primary },
  // Typing
  typingRow: { flexDirection: 'row', marginHorizontal: Spacing.md, marginVertical: Spacing.xs },
  typingBubble: {
    backgroundColor: Colors.bubbleAI, borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm + 2,
    flexDirection: 'row', alignItems: 'center',
  },
  typingDots: { flexDirection: 'row', marginRight: Spacing.sm },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: Colors.textLight, marginHorizontal: 2, opacity: 0.6 },
  dot1: { opacity: 0.4 }, dot2: { opacity: 0.6 }, dot3: { opacity: 0.8 },
  typingText: { fontSize: FontSizes.sm, color: Colors.textLight, fontStyle: 'italic' },
  // Done
  doneRow: { alignItems: 'center', paddingVertical: Spacing.md, marginHorizontal: Spacing.md },
  doneText: { fontSize: FontSizes.sm, color: Colors.primary, fontWeight: '600', textAlign: 'center' },
  // Safety
  safetyNote: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xs, backgroundColor: Colors.background },
  safetyNoteText: { fontSize: FontSizes.xs, color: Colors.textLight, textAlign: 'center' },
});
