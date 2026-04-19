module.exports = {
  testMatch: ["**/__tests__/**/*.test.[jt]s?(x)", "**/*.test.[jt]s?(x)"],
  transform: {
    "^.+\\.m?[jt]sx?$": "babel-jest",
  },
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/$1",
  },
  testEnvironment: "node",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  // MSW v2 pulls in several ESM-only deps (@open-draft/*, rettime, until-async,
  // headers-polyfill, …). Jest ignores node_modules by default, so we whitelist
  // the MSW ecosystem to be passed through babel-jest → CJS for the Node env.
  transformIgnorePatterns: [
    "/node_modules/(?!(msw|@mswjs/interceptors|@bundled-es-modules|@open-draft|headers-polyfill|tough-cookie|universal-user-agent|until-async|rettime|outvariant|strict-event-emitter)/)",
    "\\.pnp\\.[^\\\\/]+$",
  ],
};
