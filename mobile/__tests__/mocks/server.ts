/**
 * Shared MSW server for all mobile tests.
 *
 * Lives in __tests__/mocks/ so jest.config.js's testPathIgnorePatterns
 * skips it — this file is support code, not a test. Individual test
 * files override handlers via server.use(...) for per-test scenarios;
 * jest.setup.js resets handlers after each test so one flaky suite
 * can't taint the next.
 */

import { setupServer } from "msw/node";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);
