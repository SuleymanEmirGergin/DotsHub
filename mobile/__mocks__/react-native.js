/**
 * Minimal React Native shim for Jest render tests.
 *
 * We run tests in `testEnvironment: "node"` — the real `react-native`
 * package bootstraps native modules, Flow-typed imports, and Metro-
 * specific resolution that all blow up in plain Node. For pure-markup
 * leaf components (RiskBadge, EmergencyBanner, …) we only need the
 * primitive types and a `StyleSheet.create` no-op.
 *
 * Tests that need richer behaviour (Platform.OS, specific native
 * modules) still override via `jest.mock("react-native", …)` in the
 * test file itself — a file-level mock beats this module-name map.
 */
const React = require("react");

// Render as Fragments — lowercase host-tag shims are treated as
// invalid DOM by react-test-renderer and serialize to null. A
// Fragment just lets children bubble up into the tree directly,
// which is all our text-extractor needs.
const passThrough = (props) =>
  React.createElement(React.Fragment, null, props?.children);

module.exports = {
  View: passThrough,
  Text: passThrough,
  ScrollView: passThrough,
  TouchableOpacity: passThrough,
  Pressable: passThrough,
  SafeAreaView: passThrough,
  TextInput: passThrough,
  ActivityIndicator: passThrough,

  // Style helpers — tests almost never assert on styles.
  StyleSheet: { create: (obj) => obj, flatten: (x) => x },

  // Platform — defaults to iOS. Override per-test if you need Android.
  Platform: { OS: "ios", select: (obj) => obj?.ios ?? obj?.default ?? undefined },

  // Commonly-imported noop APIs.
  Share: { share: () => Promise.resolve({ action: "shared" }) },
  Alert: { alert: () => undefined },
  Linking: { openURL: () => Promise.resolve() },
};
