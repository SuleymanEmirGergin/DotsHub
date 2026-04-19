/**
 * Jest setup — wired via `setupFilesAfterEnv` in jest.config.js.
 *
 * Registers MSW lifecycle hooks so every test file gets:
 *   - a fresh intercepting server before tests run
 *   - handler reset after each test (server.use overrides don't leak)
 *   - clean shutdown after the suite
 *
 * `onUnhandledRequest: "error"` makes missing handlers fail loudly —
 * we want any unmocked network call to be visible, not silently fall
 * through to a real request.
 */
import { server } from "./mocks/server";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});
