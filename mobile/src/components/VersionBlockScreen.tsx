/**
 * Full-screen wall shown when enforcement_mode is "block" and this
 * build is below MIN_CLIENT_VERSION. No dismiss path — the user has
 * to install the new version or uninstall. Rendered above the Stack
 * so the triage flow can't be reached.
 *
 * Design intent: this is the last-resort safety valve. Ops only
 * flips "block" when the running client version has a known-bad
 * medical-logic bug (e.g. wrong EMERGENCY routing) that we can't
 * hot-fix server-side. Treat the UI as a dead-end by design.
 */

import { useMemo } from "react";
import {
  Linking,
  Platform,
  Pressable,
  SafeAreaView,
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

export function VersionBlockScreen({ policy, currentVersion }: Props) {
  const { t } = useI18n();

  const storeUrl = useMemo(
    () =>
      Platform.OS === "ios"
        ? policy.update_url_ios
        : policy.update_url_android,
    [policy.update_url_android, policy.update_url_ios],
  );

  const onUpdate = () => {
    if (storeUrl) Linking.openURL(storeUrl).catch(() => {});
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content} accessibilityRole="summary">
        <Text style={styles.emoji} accessibilityElementsHidden>
          ⛔
        </Text>
        <Text style={styles.title}>{t("version.blockTitle")}</Text>
        <Text style={styles.body}>
          {t("version.blockBody")
            .replace("{current}", currentVersion)
            .replace("{min}", policy.min)}
        </Text>

        {storeUrl ? (
          <Pressable
            onPress={onUpdate}
            style={styles.primaryBtn}
            accessibilityRole="button"
            accessibilityLabel={t("version.blockUpdate")}
          >
            <Text style={styles.primaryBtnText}>
              {t("version.blockUpdate")}
            </Text>
          </Pressable>
        ) : (
          <Text style={styles.noLinkHint}>
            {t("version.blockNoLinkHint")}
          </Text>
        )}

        <Text style={styles.footerHint}>
          {t("version.blockFooterHint")}
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#FAFAFA" },
  content: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    gap: 16,
  },
  emoji: { fontSize: 48 },
  title: {
    fontSize: 22,
    fontWeight: "700",
    color: "#111",
    textAlign: "center",
  },
  body: {
    fontSize: 15,
    color: "#444",
    textAlign: "center",
    lineHeight: 22,
    marginHorizontal: 8,
  },
  primaryBtn: {
    backgroundColor: "#111",
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 10,
    marginTop: 12,
  },
  primaryBtnText: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "600",
  },
  noLinkHint: {
    fontSize: 13,
    color: "#666",
    textAlign: "center",
    fontStyle: "italic",
    marginTop: 8,
  },
  footerHint: {
    fontSize: 12,
    color: "#888",
    textAlign: "center",
    marginTop: 16,
  },
});
