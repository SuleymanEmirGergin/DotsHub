/**
 * Jest config for mobile test suites.
 *
 * We do NOT use `preset: "jest-expo"` because it loads a full RN
 * environment (mocks every native module) that breaks for node-level
 * tests of our API clients and utility modules. The preset is aimed
 * at component tests with @testing-library/react-native; adopting it
 * would require rewriting pushClient.test.ts, deviceId.test.ts, and
 * the new API client tests to work under its setup.
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
    // The MSW handlers module is a helper, not a test.
    "/__tests__/mocks/",
  ],
  transform: {
    // `.mjs` must be matched too — MSW v2 and several of its deps
    // (rettime in particular) ship .mjs entry points. Without this,
    // babel-jest skips them and Node's CJS loader chokes on `import`.
    "^.+\\.(m?js|tsx?)$": "babel-jest",
  },
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
  },
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  transformIgnorePatterns: [
    // Transform these ESM-only node_modules. Format is
    // `node_modules/(?!<allow-list>/)` — classic Jest pattern. The
    // trailing slash in the lookahead matters: without it, names
    // like `outvariant` would also match `outvariant-other`.
    "node_modules/(?!(msw|@mswjs|until-async|@bundled-es-modules|@open-draft|strict-event-emitter|headers-polyfill|outvariant|rettime|is-node-process|path-to-regexp|cookie|statuses|graphql)/)",
  ],
};
