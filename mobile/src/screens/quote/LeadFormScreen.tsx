/**
 * Step 5 — Lead form (contact + KVKK consent).
 *
 * The KVKK gate is critical: without consent_to_share, the backend
 * still records the lead but redacts PII before dispatching to the
 * operator's CRM. Make the consent toggle prominent and explain what
 * each option does.
 */
import React, { useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useI18n, RTL_TEXT_STYLE } from "@/i18n/I18nProvider";
import { useQuoteStore } from "@/src/state/quoteStore";
import { tokens } from "@/src/ui/designTokens";
import {
  Card,
  MutedText,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
} from "@/src/ui/primitives";

export default function LeadFormScreen() {
  const { t, isRTL } = useI18n();
  const submitContactLead = useQuoteStore((s) => s.submitContactLead);
  const setStep = useQuoteStore((s) => s.setStep);
  const loading = useQuoteStore((s) => s.loading);
  const selectedClinic = useQuoteStore((s) => s.selectedClinic);
  const procedure = useQuoteStore((s) => s.procedure);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [consent, setConsent] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const rtlText = isRTL ? RTL_TEXT_STYLE : undefined;

  const handleSubmit = async () => {
    if (!consent) {
      setLocalError(t("quote.lead.consentRequiredError"));
      return;
    }
    if (!name.trim() || (!email.trim() && !phone.trim())) {
      setLocalError(t("quote.lead.contactRequiredError"));
      return;
    }
    setLocalError(null);
    await submitContactLead(
      { name: name.trim(), email: email.trim(), phone: phone.trim() },
      consent,
      notes.trim() || undefined,
    );
  };

  return (
    <ScreenContainer style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Pressable
          onPress={() => setStep("quote")}
          style={styles.backLink}
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
        >
          <Text style={[styles.backText, rtlText]}>← {t("common.back")}</Text>
        </Pressable>
        <Text style={[styles.title, rtlText]}>{t("quote.lead.title")}</Text>
        <MutedText style={[styles.subtitle, rtlText]}>
          {procedure && selectedClinic
            ? t("quote.lead.subtitle")
                .replace("{procedure}", procedure.name.tr)
                .replace("{clinic}", selectedClinic.clinic_name)
            : t("quote.lead.subtitle")
                .replace("{procedure}", "—")
                .replace("{clinic}", "—")}
        </MutedText>

        <Card style={styles.card}>
          <Text style={[styles.fieldLabel, rtlText]}>
            {t("quote.lead.nameLabel")}
          </Text>
          <TextInput
            value={name}
            onChangeText={setName}
            placeholder={t("quote.lead.namePlaceholder")}
            autoCapitalize="words"
            style={styles.input}
            accessibilityLabel={t("quote.lead.nameLabel")}
          />

          <Text style={[styles.fieldLabel, rtlText]}>
            {t("quote.lead.emailLabel")}
          </Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder="name@example.com"
            keyboardType="email-address"
            autoCapitalize="none"
            style={styles.input}
            accessibilityLabel={t("quote.lead.emailLabel")}
          />

          <Text style={[styles.fieldLabel, rtlText]}>
            {t("quote.lead.phoneLabel")}
          </Text>
          <TextInput
            value={phone}
            onChangeText={setPhone}
            placeholder="+90 5XX XXX XX XX"
            keyboardType="phone-pad"
            style={styles.input}
            accessibilityLabel={t("quote.lead.phoneLabel")}
          />

          <Text style={[styles.fieldLabel, rtlText]}>
            {t("quote.lead.notesLabel")}
          </Text>
          <TextInput
            value={notes}
            onChangeText={setNotes}
            placeholder={t("quote.lead.notesPlaceholder")}
            multiline
            numberOfLines={3}
            style={[styles.input, styles.notesInput]}
            accessibilityLabel={t("quote.lead.notesLabel")}
          />
        </Card>

        <Card style={styles.consentCard}>
          <Pressable
            style={styles.consentRow}
            onPress={() => setConsent((v) => !v)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: consent }}
            accessibilityLabel={t("quote.lead.consentToggle")}
          >
            <View style={[styles.checkbox, consent && styles.checkboxChecked]}>
              {consent ? <Text style={styles.checkmark}>✓</Text> : null}
            </View>
            <Text style={[styles.consentLabel, rtlText]}>
              {t("quote.lead.consentToggle")}
            </Text>
          </Pressable>
          <MutedText style={[styles.consentHelp, rtlText]}>
            {t("quote.lead.consentHelp")}
          </MutedText>
        </Card>

        {localError ? (
          <Text style={[styles.errorText, rtlText]}>{localError}</Text>
        ) : null}

        <View style={styles.actions}>
          <SecondaryButton onPress={() => setStep("quote")}>
            {t("common.back")}
          </SecondaryButton>
          <PrimaryButton
            onPress={handleSubmit}
            disabled={loading}
            style={styles.cta}
          >
            {loading ? t("common.loading") : t("quote.lead.submitCta")}
          </PrimaryButton>
        </View>
      </ScrollView>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: tokens.spacing.lg },
  scroll: { paddingBottom: tokens.spacing.xxl },
  backLink: { paddingVertical: tokens.spacing.xs, marginBottom: tokens.spacing.sm },
  backText: { ...tokens.typography.bodySmall, color: tokens.colors.textSecondary },
  title: { ...tokens.typography.title, marginBottom: tokens.spacing.xs },
  subtitle: { marginBottom: tokens.spacing.md },
  card: { marginBottom: tokens.spacing.md },
  fieldLabel: { ...tokens.typography.h2, marginBottom: tokens.spacing.xs },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: tokens.colors.border,
    borderRadius: tokens.radius.md,
    backgroundColor: tokens.colors.surface,
    paddingHorizontal: tokens.spacing.md,
    paddingVertical: tokens.spacing.sm,
    marginBottom: tokens.spacing.md,
    fontSize: 16,
    color: tokens.colors.textPrimary,
  },
  notesInput: { minHeight: 80, textAlignVertical: "top" },
  consentCard: { marginBottom: tokens.spacing.md },
  consentRow: { flexDirection: "row", alignItems: "center" },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: tokens.radius.sm,
    borderWidth: 2,
    borderColor: tokens.colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginRight: tokens.spacing.sm,
    backgroundColor: tokens.colors.surface,
  },
  checkboxChecked: {
    backgroundColor: tokens.colors.primary,
    borderColor: tokens.colors.primary,
  },
  checkmark: {
    color: "#FFFFFF",
    fontSize: 14,
    lineHeight: 14,
    fontWeight: "700",
  },
  consentLabel: { ...tokens.typography.body, flex: 1 },
  consentHelp: { marginTop: tokens.spacing.sm },
  errorText: {
    color: tokens.colors.error,
    marginBottom: tokens.spacing.sm,
  },
  actions: {
    flexDirection: "row",
    gap: tokens.spacing.md,
    marginTop: tokens.spacing.md,
  },
  cta: { flex: 1 },
});
