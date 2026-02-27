import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Spacing, FontSizes, BorderRadius } from '../constants/theme';

interface ChatBubbleProps {
  role: 'user' | 'ai' | 'system';
  content: string;
  timestamp?: string;
}

export default function ChatBubble({ role, content, timestamp }: ChatBubbleProps) {
  const isUser = role === 'user';

  return (
    <View style={[styles.row, isUser ? styles.rowUser : styles.rowAI]}>
      {!isUser && (
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>🩺</Text>
        </View>
      )}
      <View
        style={[
          styles.bubble,
          isUser ? styles.bubbleUser : styles.bubbleAI,
        ]}
      >
        <Text
          style={[
            styles.text,
            isUser ? styles.textUser : styles.textAI,
          ]}
        >
          {content}
        </Text>
        {timestamp && (
          <Text style={[styles.time, isUser ? styles.timeUser : styles.timeAI]}>
            {new Date(timestamp).toLocaleTimeString('tr-TR', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    marginVertical: Spacing.xs,
    marginHorizontal: Spacing.md,
    alignItems: 'flex-end',
  },
  rowUser: {
    justifyContent: 'flex-end',
  },
  rowAI: {
    justifyContent: 'flex-start',
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.primaryLight,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.sm,
  },
  avatarText: {
    fontSize: 16,
  },
  bubble: {
    maxWidth: '75%',
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm + 2,
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
    elevation: 1,
  },
  bubbleUser: {
    backgroundColor: Colors.bubbleUser,
    borderBottomRightRadius: 4,
  },
  bubbleAI: {
    backgroundColor: Colors.bubbleAI,
    borderBottomLeftRadius: 4,
  },
  text: {
    fontSize: FontSizes.md,
    lineHeight: 22,
  },
  textUser: {
    color: Colors.bubbleUserText,
  },
  textAI: {
    color: Colors.bubbleAIText,
  },
  time: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  timeUser: {
    color: 'rgba(255,255,255,0.7)',
    textAlign: 'right',
  },
  timeAI: {
    color: Colors.textLight,
  },
});
