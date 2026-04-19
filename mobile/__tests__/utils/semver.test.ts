/**
 * Coverage for the version-gate comparator. Runs in the node jest
 * environment — no RN surface needed.
 */

import { compareVersions, isBelow } from "../../src/utils/semver";

describe("compareVersions", () => {
  it("returns 0 for equal versions", () => {
    expect(compareVersions("1.2.3", "1.2.3")).toBe(0);
  });

  it("returns positive when first is newer", () => {
    expect(compareVersions("1.3.0", "1.2.0")).toBeGreaterThan(0);
    expect(compareVersions("2.0.0", "1.99.99")).toBeGreaterThan(0);
    expect(compareVersions("1.2.4", "1.2.3")).toBeGreaterThan(0);
  });

  it("returns negative when first is older", () => {
    expect(compareVersions("1.2.3", "1.2.4")).toBeLessThan(0);
    expect(compareVersions("1.99.99", "2.0.0")).toBeLessThan(0);
  });

  it("ignores pre-release suffixes", () => {
    // A dev on 1.2.3-beta shouldn't be treated as behind the
    // published 1.2.3 release — they're the same numeric build.
    expect(compareVersions("1.2.3-beta", "1.2.3")).toBe(0);
    expect(compareVersions("1.2.3", "1.2.3-rc.1")).toBe(0);
  });

  it("treats missing components as zero", () => {
    expect(compareVersions("1.2", "1.2.0")).toBe(0);
    expect(compareVersions("1", "1.0.0")).toBe(0);
  });

  it("defaults garbage input to 0.0.0", () => {
    // Forgiveness matters — a mangled version string should not
    // blow up the startup gate.
    expect(compareVersions("", "0.0.0")).toBe(0);
    expect(compareVersions("garbage", "0.0.0")).toBe(0);
  });
});

describe("isBelow", () => {
  it("is true when current < minimum", () => {
    expect(isBelow("1.2.0", "1.3.0")).toBe(true);
    expect(isBelow("0.0.0", "0.0.1")).toBe(true);
  });

  it("is false when current == minimum", () => {
    expect(isBelow("1.2.3", "1.2.3")).toBe(false);
  });

  it("is false when current > minimum", () => {
    expect(isBelow("2.0.0", "1.9.9")).toBe(false);
  });
});
