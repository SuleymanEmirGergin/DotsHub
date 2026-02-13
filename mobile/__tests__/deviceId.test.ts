/**
 * Unit test for getDeviceId (deviceId utility).
 * Mocks expo-constants to test fallback and caching.
 */

jest.mock("expo-constants", () => ({
  __esModule: true,
  default: {
    sessionId: undefined,
    installationId: undefined,
  },
}));

// Reset module cache so getDeviceId picks up the mock
jest.resetModules();

describe("getDeviceId", () => {
  it("returns fallback when Constants.sessionId and installationId are empty", () => {
    const { getDeviceId } = require("../utils/deviceId");
    const id = getDeviceId();
    expect(id).toMatch(/^fallback-[a-z0-9]+$/);
    expect(id.length).toBeGreaterThan(10);
  });

  it("returns same value on second call (cached)", () => {
    const { getDeviceId } = require("../utils/deviceId");
    const id1 = getDeviceId();
    const id2 = getDeviceId();
    expect(id1).toBe(id2);
  });
});
