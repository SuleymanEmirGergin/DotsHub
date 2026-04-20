/**
 * Jest config for mobile test suites.
 *
 * We do NOT use `preset: "jest-expo"` because it loads a full RN
 * environment (mocks every native module) that breaks for node-level
 * tests of our API clients and utility modules. The preset is aimed
 * at component tests with @testing-library/react-native; adopting it
 * would require rewriting pushClient.test.ts and the API client tests
 * to work under its setup.
 *
 * Instead: `testEnvironment: "node"` with plain babel-jest and a
 * narrow transformIgnorePatterns that lets MSW (and its ESM-only
 * dependency tree) transpile. Works with MSW v2's msw/node server.
 */

module.exports = {
  testEnvironment: "node",
  testMatch: ["**/__tests__/**/*.test.[jt]s?(x)", "**/*.test.[jt]s?(x)"],
  testPathIgnorePatterns: [
    "/node_modules/",
    // Helper modules in __tests__/mocks/ are support code, not tests.
    "/__tests__/mocks/",
  ],
  transform: {
    // `.mjs` must match too — MSW v2 and several of its deps (rettime
    // in particular) ship .mjs entry points. Without this, babel-jest
    // skips them and Node's CJS loader chokes on `import`.
    "^.+\\.m?[jt]sx?$": "babel-jest",
  },
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
    // Render tests pull in real React Native under a node environment,
    // which can't load native modules. Redirect imports to a tiny JS
    // shim that covers View/Text/StyleSheet/Platform — enough for
    // pure-markup leaf components (RiskBadge, EmergencyBanner, …).
    "^react-native$": "<rootDir>/__mocks__/react-native.js",
  },
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  // MSW v2 pulls in several ESM-only deps (@open-draft/*, rettime,
  // until-async, headers-polyfill, …) plus its own runtime graph
  // (is-node-process, path-to-regexp, cookie, statuses, graphql).
  // Jest ignores node_modules by default, so we whitelist the MSW
  // ecosystem to be passed through babel-jest → CJS for the Node env.
  //
  // Pattern matches the package name ANYWHERE after a `node_modules/`
  // segment so it works for:
  //   - npm/yarn flat: `node_modules/rettime/...`
  //   - pnpm nested:   `node_modules/.pnpm/rettime@x.y.z_hash/node_modules/rettime/...`
  transformIgnorePatterns: [
    "node_modules/(?!.*(?:msw|@mswjs/interceptors|@bundled-es-modules|@open-draft|headers-polyfill|tough-cookie|universal-user-agent|until-async|rettime|outvariant|strict-event-emitter|is-node-process|path-to-regexp|cookie|statuses|graphql|expo|@sentry))",
    "\\.pnp\\.[^\\\\/]+$",
  ],
};
