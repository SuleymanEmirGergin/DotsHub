/**
 * Soft banner shown above the main stack when the backend tells us
 * this build is older than MIN_CLIENT_VERSION but enforcement_mode
 * is "warn" (not "block"). Tappable → store link (iOS / Android
 * specific). Dismissable within a session, but comes back on next
 * launch — the banner is fetched fresh from /v1/config/features
 * every cold start via useVersionGate.
 */

import { useMemo, useState } from "react";
import {
  Linking,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import type { ClientVersionPolicy } from "@/src/api/featuresClient";
import { useI18n } from "@/i18n/I18nProvider";

interface Props {
  policy: ClientVersionPolicy;
  currentVersion: string;
}

export function VersionUpdateBanner({ policy, currentVersion }: Props) {
  const { t } = useI18n();
  const [dismissed, setDismissed] = useState(false);

  const storeUrl = useMemo(
    () =>
      Platform.OS === "ios"
        ? policy.update_url_ios
        : policy.update_url_android,
    [policy.update_url_android, policy.update_url_ios],
  );

  if (dismissed) return null;

  const onUpdate = () => {
    if (storeUrl) Linking.openURL(storeUrl).catch(() => {});
  };

  return (
    <View
      style={styles.container}
      accessibilityRole="alert"
      accessibilityLabel={t("version.bannerA11y")}
    >
      <View style={styles.textBlock}>
        <Text style={styles.title}>{t("version.bannerTitle")}</Text>
        <Text style={styles.subtitle}>
          {t("version.bannerSubtitle")
            .replace("{current}", currentVersion)
            .replace("{min}", policy.min)}
        </Text>
      </View>
      <View style={styles.actions}>
        {storeUrl ? (
          <Pressable
            onPress={onUpdate}
            style={styles.primaryBtn}
            accessibilityRole="button"
            accessibilityLabel={t("version.bannerUpdate")}
          >
            <Text style={styles.primaryBtnText}>
              {t("version.bannerUpdate")}
            </Text>
          </Pressable>
        ) : null}
        <Pressable
          onPress={() => setDismissed(true)}
          style={styles.dismissBtn}
          accessibilityRole="button"
          accessibilityLabel={t("version.bannerDismiss")}
        >
          <Text style={styles.dismissBtnText}>
            {t("version.bannerDismiss")}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#FFF4CE", // amber-100
    borderBottomWidth: 1,
    borderBottomColor: "#F2C94C",
    paddingHorizontal: 16,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  textBlock: { flex: 1, minWidth: 0 },
  title: { fontSize: 14, fontWeight: "600", color: "#5A3E00" },
  subtitle: { fontSize: 12, color: "#7A5400", marginTop: 2 },
  actions: { flexDirection: "row", gap: 8 },
  primaryBtn: {
    backgroundColor: "#5A3E00",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
  },
  primaryBtnText: { color: "#FFF", fontSize: 12, fontWeight: "600" },
  dismissBtn: {
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderRadius: 6,
  },
  dismissBtnText: { color: "#5A3E00", fontSize: 12, fontWeight: "500" },
});
