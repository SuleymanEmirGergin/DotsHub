/**
 * Küçük banner: internet yokken (NetInfo) ekranın üstünde gösterilir.
 */

import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useNetInfo } from "@react-native-community/netinfo";
import { getText, getLocale } from "@/i18n/index";
import { tokens } from "@/src/ui/designTokens";

export function OfflineBanner(): React.ReactElement | null {
  const netInfo = useNetInfo();

  // isConnected === false -> offline; null/undefined -> henüz bilinmiyor, banner gösterme
  if (netInfo.isConnected !== false) return null;

  const locale = getLocale();
  const message = getText(locale, "common.offline");

  return (
    <View style={styles.banner}>
      <Text style={styles.text}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: tokens.colors.warning,
    paddingVertical: 6,
    paddingHorizontal: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  text: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "500",
  },
});
