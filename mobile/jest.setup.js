/**
 * Global Jest setup — runs after each test file is loaded.
 *
 * Wires MSW into the test process: start once per file, reset
 * handlers between tests (per-test overrides don't leak), stop
 * at the end. `onUnhandledRequest: "error"` catches forgotten
 * endpoints before they silently hit the network.
 */

const { server } = require("./__tests__/mocks/server");

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
