/**
 * Screen 4 - Doctor Summary (V2 with _tr fields)
 */

import React, { useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, Share, Alert,
} from 'react-native';
import { Colors, Spacing, FontSizes, BorderRadius } from '../constants/theme';
import { useSessionStore } from '../store/useSessionStore';
import RiskBadge from '../components/RiskBadge';

export default function SummaryScreen() {
  const {
    summary, recommendedSpecialty, urgency, candidates,
    emergencyWatchouts, messages, riskLevel, doctorSummary,
    disclaimer, fetchSummary,
  } = useSessionStore();

  useEffect(() => {
    if (!summary) fetchSummary();
  }, []);

  const ds = summary?.doctor_ready_summary_tr || doctorSummary;

  const handleShare = async () => {
    const text = buildSummaryText();
    try {
      await Share.share({ message: text, title: 'Ön-Triyaj Asistanı - Sağlık Özeti' });
    } catch {
      Alert.alert('Hata', 'Paylaşım sırasında bir hata oluştu.');
    }
  };

  const buildSummaryText = () => {
    const lines: string[] = [];
    lines.push('═══════════════════════════════');
    lines.push('ÖN-TRİYAJ ASISTANI - SAĞLIK ÖZETİ');
    lines.push('═══════════════════════════════\n');

    if (ds) {
      lines.push('BELIRTILER:');
      ds.symptoms_tr.forEach((s) => lines.push(`  • ${s}`));
      lines.push(`\nSÜRE: ${ds.timeline_tr}`);
      lines.push(`RİSK SEVİYESİ: ${ds.risk_level}`);
    }

    if (recommendedSpecialty) {
      lines.push(`\nÖNERİLEN BRANŞ: ${recommendedSpecialty}`);
      lines.push(`ACİLİYET: ${urgency}`);
    }

    if (candidates.length > 0) {
      lines.push('\nOLASI DURUMLAR:');
      candidates.forEach((c) => lines.push(`  %${Math.round(c.probability_0_1 * 100)} - ${c.label_tr}`));
    }

    const qaMessages = messages.filter((m) => m.role === 'user' || m.role === 'ai');
    if (qaMessages.length > 0) {
      lines.push('\nSORU-CEVAP GEÇMİŞİ:');
      qaMessages.forEach((m) => {
        const prefix = m.role === 'ai' ? 'Asistan' : 'Hasta';
        lines.push(`  ${prefix}: ${m.content}`);
      });
    }

    if (emergencyWatchouts.length > 0) {
      lines.push('\nACİL UYARILAR:');
      emergencyWatchouts.forEach((w) => lines.push(`  • ${w}`));
    }

    lines.push('\n───────────────────────────────');
    lines.push(disclaimer);
    lines.push(`Tarih: ${new Date().toLocaleDateString('tr-TR')}`);

    return lines.join('\n');
  };

  if (!ds && !recommendedSpecialty) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyText}>Özet yükleniyor...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      <View style={styles.headerCard}>
        <Text style={styles.headerTitle}>Doktora Gösterilecek Özet</Text>
        <Text style={styles.headerSubtitle}>
          Bu özeti doktorunuzla paylaşarak daha verimli bir muayene süreci geçirebilirsiniz.
        </Text>
      </View>

      <View style={styles.topRow}>
        {riskLevel && <RiskBadge level={riskLevel} />}
        {recommendedSpecialty && (
          <View style={styles.specialtyChip}>
            <Text style={styles.specialtyChipText}>{recommendedSpecialty}</Text>
          </View>
        )}
      </View>

      {ds && ds.symptoms_tr.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Belirtiler</Text>
          {ds.symptoms_tr.map((s, idx) => (
            <View key={idx} style={styles.bulletRow}>
              <Text style={styles.bullet}>•</Text>
              <Text style={styles.bulletText}>{s}</Text>
            </View>
          ))}
        </View>
      )}

      {ds && ds.timeline_tr && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Süre / Zaman Çizelgesi</Text>
          <Text style={styles.timelineText}>{ds.timeline_tr}</Text>
        </View>
      )}

      {ds && ds.qa_highlights_tr.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Önemli Notlar</Text>
          {ds.qa_highlights_tr.map((h, idx) => (
            <View key={idx} style={styles.bulletRow}>
              <Text style={styles.bullet}>•</Text>
              <Text style={styles.bulletText}>{h}</Text>
            </View>
          ))}
        </View>
      )}

      {candidates.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Olası Durumlar</Text>
          {candidates.map((c, idx) => (
            <View key={idx} style={styles.conditionRow}>
              <View style={styles.conditionBar}>
                <View style={[styles.conditionFill, { width: `${Math.round(c.probability_0_1 * 100)}%` }]} />
              </View>
              <Text style={styles.conditionLabel}>%{Math.round(c.probability_0_1 * 100)} {c.label_tr}</Text>
            </View>
          ))}
        </View>
      )}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Soru-Cevap Geçmişi</Text>
        {messages.filter((m) => m.role !== 'system').map((m, idx) => (
          <View key={idx} style={[styles.chatRow, m.role === 'user' ? styles.chatRowUser : styles.chatRowAI]}>
            <Text style={styles.chatRole}>{m.role === 'user' ? 'Hasta' : 'Asistan'}</Text>
            <Text style={styles.chatContent}>{m.content}</Text>
          </View>
        ))}
      </View>

      {emergencyWatchouts.length > 0 && (
        <View style={styles.watchoutSection}>
          <Text style={styles.watchoutTitle}>Dikkat Edilmesi Gerekenler</Text>
          {emergencyWatchouts.map((w, idx) => (
            <Text key={idx} style={styles.watchoutItem}>• {w}</Text>
          ))}
        </View>
      )}

      <View style={styles.actions}>
        <TouchableOpacity style={styles.shareButton} onPress={handleShare}>
          <Text style={styles.shareButtonText}>Özeti Paylaş</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.disclaimerSection}>
        <Text style={styles.disclaimerText}>
          {disclaimer}{'\n'}Tarih: {new Date().toLocaleDateString('tr-TR')}
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.backgroundSecondary },
  scrollContent: { paddingBottom: Spacing.xxl },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyText: { fontSize: FontSizes.md, color: Colors.textSecondary },
  headerCard: { backgroundColor: Colors.primary, padding: Spacing.lg, alignItems: 'center' },
  headerTitle: { fontSize: FontSizes.xl, fontWeight: '700', color: Colors.textWhite, marginBottom: Spacing.xs },
  headerSubtitle: { fontSize: FontSizes.sm, color: 'rgba(255,255,255,0.85)', textAlign: 'center', lineHeight: 20 },
  topRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, paddingHorizontal: Spacing.md, paddingTop: Spacing.md },
  specialtyChip: { backgroundColor: Colors.primaryLight, paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm, borderRadius: BorderRadius.full },
  specialtyChipText: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.primary },
  section: {
    backgroundColor: Colors.background, marginHorizontal: Spacing.md, marginTop: Spacing.md,
    borderRadius: BorderRadius.md, padding: Spacing.md,
    shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 3, elevation: 1,
  },
  sectionTitle: { fontSize: FontSizes.md, fontWeight: '700', color: Colors.textPrimary, marginBottom: Spacing.sm },
  bulletRow: { flexDirection: 'row', marginBottom: Spacing.xs },
  bullet: { fontSize: FontSizes.md, color: Colors.primary, marginRight: Spacing.sm, lineHeight: 22 },
  bulletText: { flex: 1, fontSize: FontSizes.sm, color: Colors.textPrimary, lineHeight: 22 },
  timelineText: { fontSize: FontSizes.sm, color: Colors.textPrimary, lineHeight: 22 },
  conditionRow: { marginBottom: Spacing.sm },
  conditionBar: { height: 6, backgroundColor: Colors.backgroundSecondary, borderRadius: 3, overflow: 'hidden', marginBottom: Spacing.xs },
  conditionFill: { height: '100%', backgroundColor: Colors.primary, borderRadius: 3 },
  conditionLabel: { fontSize: FontSizes.sm, color: Colors.textSecondary },
  chatRow: { marginBottom: Spacing.sm, padding: Spacing.sm, borderRadius: BorderRadius.sm },
  chatRowUser: { backgroundColor: Colors.primaryLight },
  chatRowAI: { backgroundColor: Colors.backgroundSecondary },
  chatRole: { fontSize: FontSizes.xs, fontWeight: '700', color: Colors.textSecondary, marginBottom: 2 },
  chatContent: { fontSize: FontSizes.sm, color: Colors.textPrimary, lineHeight: 20 },
  watchoutSection: {
    backgroundColor: '#FFF8E1', marginHorizontal: Spacing.md, marginTop: Spacing.md,
    borderRadius: BorderRadius.md, padding: Spacing.md, borderWidth: 1, borderColor: '#FFE082',
  },
  watchoutTitle: { fontSize: FontSizes.md, fontWeight: '700', color: '#E65100', marginBottom: Spacing.sm },
  watchoutItem: { fontSize: FontSizes.sm, color: '#BF360C', lineHeight: 22, marginBottom: Spacing.xs },
  actions: { paddingHorizontal: Spacing.md, marginTop: Spacing.lg },
  shareButton: {
    backgroundColor: Colors.primary, borderRadius: BorderRadius.md, paddingVertical: Spacing.md,
    alignItems: 'center',
    shadowColor: Colors.primary, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 8, elevation: 4,
  },
  shareButtonText: { color: Colors.textWhite, fontSize: FontSizes.md, fontWeight: '700' },
  disclaimerSection: { paddingHorizontal: Spacing.md, paddingVertical: Spacing.lg },
  disclaimerText: { fontSize: FontSizes.xs, color: Colors.textLight, textAlign: 'center', lineHeight: 18 },
});
