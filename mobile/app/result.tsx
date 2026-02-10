/**
 * Screen 3 - Results (V2 with Envelope data)
 */

import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, FontSizes, BorderRadius } from '../constants/theme';
import { useSessionStore } from '../store/useSessionStore';
import ResultCard from '../components/ResultCard';
import RiskBadge from '../components/RiskBadge';
import EmergencyBanner from '../components/EmergencyBanner';

const URGENCY_CONFIG: Record<string, { color: string; label: string; icon: string }> = {
  ER_NOW: { color: Colors.urgencyER, label: 'Hemen Acil', icon: '🔴' },
  SAME_DAY: { color: Colors.urgencySameDay, label: 'Bugün İçinde', icon: '🟠' },
  WITHIN_3_DAYS: { color: Colors.urgencyWithin3Days, label: '1–3 Gün İçinde', icon: '🟡' },
  ROUTINE: { color: Colors.urgencyRoutine, label: 'Rutin', icon: '🟢' },
};

export default function ResultScreen() {
  const router = useRouter();
  const {
    candidates, recommendedSpecialty, urgency, riskLevel,
    rationale, emergencyWatchouts, emergencyReason,
    emergencyInstructions, status, fetchSummary, disclaimer, facilityDiscovery,
  } = useSessionStore();

  const urgencyInfo = urgency ? URGENCY_CONFIG[urgency] : null;

  const handleViewSummary = async () => {
    await fetchSummary();
    router.push('/summary');
  };

  const handleStartOver = () => {
    useSessionStore.getState().reset();
    router.replace('/');
  };

  if (!recommendedSpecialty && status !== 'emergency') {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyText}>Analiz sonuçları yükleniyor...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      {status === 'emergency' && emergencyInstructions.length > 0 && (
        <EmergencyBanner instructions={emergencyInstructions} reason={emergencyReason || undefined} />
      )}

      {riskLevel && (
        <View style={styles.riskSection}><RiskBadge level={riskLevel} /></View>
      )}

      {recommendedSpecialty && (
        <View style={styles.specialtyCard}>
          <Text style={styles.sectionLabel}>Önerilen Branş</Text>
          <Text style={styles.specialtyName}>{recommendedSpecialty}</Text>

          {urgencyInfo && (
            <View style={[styles.urgencyBadge, { backgroundColor: urgencyInfo.color + '20' }]}>
              <Text style={styles.urgencyIcon}>{urgencyInfo.icon}</Text>
              <Text style={[styles.urgencyText, { color: urgencyInfo.color }]}>{urgencyInfo.label}</Text>
            </View>
          )}

          {rationale.length > 0 && (
            <View style={styles.rationaleList}>
              {rationale.map((r, idx) => (
                <Text key={idx} style={styles.rationaleItem}>• {r}</Text>
              ))}
            </View>
          )}
        </View>
      )}

      {candidates.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Olası Durumlar</Text>
          {candidates.map((c, idx) => (
            <ResultCard
              key={idx}
              label={c.label_tr}
              probability={c.probability_0_1}
              supporting={c.supporting_evidence_tr || []}
            />
          ))}
        </View>
      )}

      {emergencyWatchouts.length > 0 && (
        <View style={styles.watchoutCard}>
          <Text style={styles.watchoutTitle}>Acil Uyarılar</Text>
          {emergencyWatchouts.map((w, idx) => (
            <Text key={idx} style={styles.watchoutItem}>• {w}</Text>
          ))}
        </View>
      )}

      {facilityDiscovery && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Yakin saglik kuruluslari</Text>
          {facilityDiscovery.items.map((f, idx) => (
            <View key={`${f.name}-${idx}`} style={styles.facilityCard}>
              <Text style={styles.facilityName}>{f.name}</Text>
              <Text style={styles.facilityAddress}>{f.address}</Text>
              {typeof f.distance_km === 'number' && (
                <Text style={styles.facilityDistance}>{`${f.distance_km.toFixed(1)} km`}</Text>
              )}
            </View>
          ))}
          <Text style={styles.facilityDisclaimer}>{facilityDiscovery.disclaimer}</Text>
        </View>
      )}

      <View style={styles.actions}>
        <TouchableOpacity style={styles.summaryButton} onPress={handleViewSummary}>
          <Text style={styles.summaryButtonText}>Doktora Gösterilecek Özet</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.resetButton} onPress={handleStartOver}>
          <Text style={styles.resetButtonText}>Yeni Analiz Başlat</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.disclaimerContainer}>
        <Text style={styles.disclaimer}>{disclaimer}</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.backgroundSecondary },
  scrollContent: { paddingBottom: Spacing.xxl },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyText: { fontSize: FontSizes.md, color: Colors.textSecondary },
  riskSection: { paddingHorizontal: Spacing.md, paddingTop: Spacing.md },
  specialtyCard: {
    backgroundColor: Colors.background, margin: Spacing.md, borderRadius: BorderRadius.lg,
    padding: Spacing.lg, shadowColor: Colors.shadow, shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08, shadowRadius: 6, elevation: 3,
  },
  sectionLabel: {
    fontSize: FontSizes.sm, color: Colors.textSecondary, fontWeight: '600',
    textTransform: 'uppercase', letterSpacing: 1, marginBottom: Spacing.xs,
  },
  specialtyName: { fontSize: FontSizes.xxl, fontWeight: '800', color: Colors.primary, marginBottom: Spacing.md },
  urgencyBadge: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm, borderRadius: BorderRadius.full, alignSelf: 'flex-start', marginBottom: Spacing.md,
  },
  urgencyIcon: { marginRight: Spacing.sm, fontSize: 14 },
  urgencyText: { fontSize: FontSizes.sm, fontWeight: '700' },
  rationaleList: { marginTop: Spacing.xs },
  rationaleItem: { fontSize: FontSizes.sm, color: Colors.textSecondary, lineHeight: 22, marginBottom: Spacing.xs },
  section: { paddingHorizontal: Spacing.md, marginBottom: Spacing.md },
  sectionTitle: { fontSize: FontSizes.lg, fontWeight: '700', color: Colors.textPrimary, marginBottom: Spacing.md },
  watchoutCard: {
    backgroundColor: '#FFF8E1', marginHorizontal: Spacing.md, borderRadius: BorderRadius.md,
    padding: Spacing.md, borderWidth: 1, borderColor: '#FFE082', marginBottom: Spacing.md,
  },
  watchoutTitle: { fontSize: FontSizes.md, fontWeight: '700', color: '#E65100', marginBottom: Spacing.sm },
  watchoutItem: { fontSize: FontSizes.sm, color: '#BF360C', lineHeight: 22, marginBottom: Spacing.xs },
  facilityCard: {
    backgroundColor: Colors.background, borderRadius: BorderRadius.md, borderWidth: 1,
    borderColor: Colors.border, padding: Spacing.md, marginBottom: Spacing.sm,
  },
  facilityName: { fontSize: FontSizes.md, fontWeight: '700', color: Colors.textPrimary, marginBottom: 4 },
  facilityAddress: { fontSize: FontSizes.sm, color: Colors.textSecondary, lineHeight: 20 },
  facilityDistance: { fontSize: FontSizes.xs, color: Colors.textLight, marginTop: 6 },
  facilityDisclaimer: { fontSize: FontSizes.xs, color: Colors.textLight, lineHeight: 18, marginTop: Spacing.xs },
  actions: { paddingHorizontal: Spacing.md, marginTop: Spacing.md },
  summaryButton: {
    backgroundColor: Colors.primary, borderRadius: BorderRadius.md, paddingVertical: Spacing.md,
    alignItems: 'center', marginBottom: Spacing.sm,
    shadowColor: Colors.primary, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 8, elevation: 4,
  },
  summaryButtonText: { color: Colors.textWhite, fontSize: FontSizes.md, fontWeight: '700' },
  resetButton: {
    borderWidth: 1.5, borderColor: Colors.border, borderRadius: BorderRadius.md,
    paddingVertical: Spacing.md, alignItems: 'center',
  },
  resetButtonText: { color: Colors.textSecondary, fontSize: FontSizes.md, fontWeight: '600' },
  disclaimerContainer: { paddingHorizontal: Spacing.md, paddingVertical: Spacing.lg },
  disclaimer: { fontSize: FontSizes.xs, color: Colors.textLight, textAlign: 'center', lineHeight: 18 },
});
