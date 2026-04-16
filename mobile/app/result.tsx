/**
 * Screen 3 - Results (V2 with Envelope data)
 */

import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Share, Alert, ActivityIndicator, Linking, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors, Spacing, FontSizes, BorderRadius } from '../constants/theme';
import { useSessionStore } from '../store/useSessionStore';
import ResultCard from '../components/ResultCard';
import RiskBadge from '../components/RiskBadge';
import EmergencyBanner from '../components/EmergencyBanner';
import { buildSummaryHtml, shareSummaryAsPdf } from '../utils/sharePdf';
import { API_BASE } from '../constants';
import { getCurrentLocation } from '../utils/location';
import { useI18n } from '@/i18n/I18nProvider';

function getMapUrl(f: { address: string; lat?: number; lon?: number }): string {
  if (typeof f.lat === 'number' && typeof f.lon === 'number') {
    if (Platform.OS === 'ios') return `https://maps.apple.com/?ll=${f.lat},${f.lon}&q=${encodeURIComponent(f.address)}`;
    return `https://www.google.com/maps?q=${f.lat},${f.lon}`;
  }
  const q = encodeURIComponent(f.address);
  if (Platform.OS === 'ios') return `https://maps.apple.com/?q=${q}`;
  return `https://www.google.com/maps/search/?api=1&query=${q}`;
}

function getOsmUrl(f: { lat?: number; lon?: number }): string | null {
  if (typeof f.lat === 'number' && typeof f.lon === 'number') {
    return `https://www.openstreetmap.org/?mlat=${f.lat}&mlon=${f.lon}&zoom=17`;
  }
  return null;
}

const URGENCY_CONFIG: Record<string, { color: string; label: string; icon: string }> = {
  ER_NOW: { color: Colors.urgencyER, label: 'Hemen Acil', icon: '🔴' },
  SAME_DAY: { color: Colors.urgencySameDay, label: 'Bugün İçinde', icon: '🟠' },
  WITHIN_3_DAYS: { color: Colors.urgencyWithin3Days, label: '1–3 Gün İçinde', icon: '🟡' },
  ROUTINE: { color: Colors.urgencyRoutine, label: 'Rutin', icon: '🟢' },
};

export default function ResultScreen() {
  const router = useRouter();
  const { t } = useI18n();
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

  const [sharingPdf, setSharingPdf] = useState(false);
  const [moreFacilities, setMoreFacilities] = useState<{ name: string; address: string; distance_km?: number; lat?: number; lon?: number }[] | null>(null);
  const [loadingMoreFacilities, setLoadingMoreFacilities] = useState(false);

  const handleShareSummary = async () => {
    const lines: string[] = [
      '═══════════════════════════════',
      'ÖN-TRİYAJ ASİSTANI - SONUÇ ÖZETİ',
      '═══════════════════════════════\n',
    ];
    if (recommendedSpecialty) {
      lines.push(`Önerilen branş: ${recommendedSpecialty}`);
      if (urgencyInfo) lines.push(`Aciliyet: ${urgencyInfo.label}\n`);
    }
    if (rationale.length > 0) {
      lines.push('Gerekçe:');
      rationale.forEach((r) => lines.push(`  • ${r}`));
      lines.push('');
    }
    if (candidates.length > 0) {
      lines.push('Olası durumlar:');
      candidates.forEach((c) => lines.push(`  • ${c.label_tr} (%${Math.round((c.probability_0_1 ?? 0) * 100)})`));
      lines.push('');
    }
    if (emergencyWatchouts.length > 0) {
      lines.push('Acil uyarılar:');
      emergencyWatchouts.forEach((w) => lines.push(`  • ${w}`));
      lines.push('');
    }
    lines.push(disclaimer);
    try {
      await Share.share({ message: lines.join('\n'), title: 'Ön-Triyaj Sonuç Özeti' });
    } catch {
      Alert.alert('Hata', 'Paylaşım açılamadı.');
    }
  };

  const handleSharePdf = async () => {
    setSharingPdf(true);
    try {
      const html = buildSummaryHtml({
        title: 'Ön-Triyaj Asistanı - Sonuç Özeti',
        specialty: recommendedSpecialty ?? undefined,
        urgency: urgencyInfo?.label,
        rationale: rationale.length ? rationale : undefined,
        candidates: candidates.map((c) => ({ label: c.label_tr, probability: c.probability_0_1 })),
        emergencyWatchouts: emergencyWatchouts.length ? emergencyWatchouts : undefined,
        disclaimer,
      });
      const ok = await shareSummaryAsPdf(html, handleShareSummary);
      if (!ok) Alert.alert('Bilgi', 'PDF paylaşımı bu cihazda desteklenmiyor; metin paylaşıldı.');
    } catch {
      Alert.alert('Hata', 'PDF oluşturulamadı.');
    } finally {
      setSharingPdf(false);
    }
  };

  const handleLoadMoreFacilities = async () => {
    if (!facilityDiscovery || loadingMoreFacilities) return;
    setLoadingMoreFacilities(true);
    try {
      const loc = await getCurrentLocation();
      const params = new URLSearchParams({
        specialty: facilityDiscovery.specialty_id,
        limit: '15',
      });
      if (typeof (facilityDiscovery as { city?: string }).city === 'string') {
        params.set('city', (facilityDiscovery as { city?: string }).city ?? '');
      }
      if (loc) {
        params.set('lat', String(loc.lat));
        params.set('lon', String(loc.lon));
      }
      const r = await fetch(`${API_BASE}/v1/facilities?${params}`);
      const data = await r.json();
      if (data?.items?.length) setMoreFacilities(data.items);
      else setMoreFacilities(facilityDiscovery.items);
    } catch {
      Alert.alert(t('result.alertError'), t('result.facilitiesLoadError'));
    } finally {
      setLoadingMoreFacilities(false);
    }
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
          <Text style={styles.sectionTitle}>{t('result.nearbyFacilities')}</Text>
          {(moreFacilities ?? facilityDiscovery.items).map((f, idx) => {
            const osmUrl = getOsmUrl(f);
            return (
              <View key={`${f.name}-${idx}`} style={styles.facilityCard}>
                <Text style={styles.facilityName}>{f.name}</Text>
                <Text style={styles.facilityAddress}>{f.address}</Text>
                {typeof f.distance_km === 'number' && (
                  <Text style={styles.facilityDistance}>{`${f.distance_km.toFixed(1)} km`}</Text>
                )}
                <View style={styles.mapLinksRow}>
                  <TouchableOpacity
                    style={styles.mapLink}
                    onPress={() => Linking.openURL(getMapUrl(f)).catch(() => Alert.alert(t('result.alertError'), t('result.mapOpenError')))}
                    accessibilityLabel={t('result.openOnMap')}
                    accessibilityRole="button"
                  >
                    <Text style={styles.mapLinkText}>{t('result.openOnMap')}</Text>
                  </TouchableOpacity>
                  {osmUrl && (
                    <TouchableOpacity
                      style={styles.mapLink}
                      onPress={() => Linking.openURL(osmUrl).catch(() => Alert.alert(t('result.alertError'), t('result.mapOpenError')))}
                      accessibilityLabel={t('result.openInOsm')}
                      accessibilityRole="button"
                    >
                      <Text style={styles.mapLinkText}>{t('result.openInOsm')}</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            );
          })}
          {!moreFacilities && (
            <TouchableOpacity style={styles.moreFacilitiesButton} onPress={handleLoadMoreFacilities} disabled={loadingMoreFacilities}>
              {loadingMoreFacilities ? <ActivityIndicator size="small" color={Colors.primary} /> : <Text style={styles.moreFacilitiesText}>{t('result.moreFacilities')}</Text>}
            </TouchableOpacity>
          )}
          <Text style={styles.facilityDisclaimer}>{facilityDiscovery.disclaimer}</Text>
        </View>
      )}

      <View style={styles.actions} accessibilityRole="menu">
        <TouchableOpacity style={styles.summaryButton} onPress={handleViewSummary} accessibilityLabel="Doktora gösterilecek özet" accessibilityRole="button" accessibilityHint="Özet sayfasına gider">
          <Text style={styles.summaryButtonText}>Doktora Gösterilecek Özet</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.shareButton} onPress={handleShareSummary} accessibilityLabel="Özeti metin olarak paylaş" accessibilityRole="button">
          <Text style={styles.shareButtonText}>Özeti paylaş (metin)</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.shareButton} onPress={handleSharePdf} disabled={sharingPdf} accessibilityLabel={sharingPdf ? 'Hazırlanıyor' : 'PDF olarak paylaş'} accessibilityRole="button">
          <Text style={styles.shareButtonText}>{sharingPdf ? 'Hazırlanıyor…' : 'PDF olarak paylaş'}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.resetButton} onPress={handleStartOver} accessibilityLabel="Yeni analiz başlat" accessibilityRole="button" accessibilityHint="Baştan başlar">
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
  mapLinksRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 8 },
  mapLink: { alignSelf: 'flex-start' },
  mapLinkText: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.primary },
  facilityDisclaimer: { fontSize: FontSizes.xs, color: Colors.textLight, lineHeight: 18, marginTop: Spacing.xs },
  moreFacilitiesButton: { paddingVertical: Spacing.sm, alignItems: 'center', marginTop: Spacing.xs },
  moreFacilitiesText: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.primary },
  actions: { paddingHorizontal: Spacing.md, marginTop: Spacing.md },
  summaryButton: {
    backgroundColor: Colors.primary, borderRadius: BorderRadius.md, paddingVertical: Spacing.md,
    alignItems: 'center', marginBottom: Spacing.sm,
    shadowColor: Colors.primary, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 8, elevation: 4,
  },
  summaryButtonText: { color: Colors.textWhite, fontSize: FontSizes.md, fontWeight: '700' },
  shareButton: {
    backgroundColor: Colors.background, borderWidth: 1.5, borderColor: Colors.primary,
    borderRadius: BorderRadius.md, paddingVertical: Spacing.md, alignItems: 'center', marginBottom: Spacing.sm,
  },
  shareButtonText: { color: Colors.primary, fontSize: FontSizes.md, fontWeight: '700' },
  resetButton: {
    borderWidth: 1.5, borderColor: Colors.border, borderRadius: BorderRadius.md,
    paddingVertical: Spacing.md, alignItems: 'center',
  },
  resetButtonText: { color: Colors.textSecondary, fontSize: FontSizes.md, fontWeight: '600' },
  disclaimerContainer: { paddingHorizontal: Spacing.md, paddingVertical: Spacing.lg },
  disclaimer: { fontSize: FontSizes.xs, color: Colors.textLight, textAlign: 'center', lineHeight: 18 },
});
