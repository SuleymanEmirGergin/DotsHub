/**
 * MSW Node server — used by Jest (testEnvironment: "node").
 *
 * Lifecycle wiring lives in `jest.setup.ts`:
 *   - beforeAll  → server.listen({ onUnhandledRequest: "error" })
 *   - afterEach  → server.resetHandlers()
 *   - afterAll   → server.close()
 *
 * Tests can override a handler for a single case via:
 *   server.use(http.get("*.../endpoint", () => HttpResponse.json({...})))
 */
import { setupServer } from "msw/node";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);
