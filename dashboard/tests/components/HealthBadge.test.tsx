import { describe, it, expect } from "vitest";
import { pillClass, riskBadge, fmtPct } from "@/components/ui/health-badge";
import type { HealthStatus } from "@/lib/types/admin";

describe("pillClass", () => {
  it("returns red classes for CRIT status", () => {
    const cls = pillClass("CRIT");
    expect(cls).toContain("border-red-500");
    expect(cls).toContain("text-red-600");
  });

  it("returns amber classes for WARN status", () => {
    const cls = pillClass("WARN");
    expect(cls).toContain("border-amber-500");
    expect(cls).toContain("text-amber-600");
  });

  it("returns emerald classes for OK status", () => {
    const cls = pillClass("OK");
    expect(cls).toContain("border-emerald-500");
    expect(cls).toContain("text-emerald-600");
  });

  it("returns slate classes for INFO status (fallback)", () => {
    const cls = pillClass("INFO");
    expect(cls).toContain("border-slate-400");
    expect(cls).toContain("text-slate-500");
  });

  it("includes base inline-flex classes for all statuses", () => {
    const statuses: HealthStatus[] = ["CRIT", "WARN", "OK", "INFO"];
    for (const s of statuses) {
      const cls = pillClass(s);
      expect(cls).toContain("inline-flex");
      expect(cls).toContain("rounded-full");
    }
  });
});

describe("riskBadge", () => {
  it("returns red classes for HIGH risk", () => {
    const cls = riskBadge("HIGH");
    expect(cls).toContain("border-red-500");
    expect(cls).toContain("text-red-600");
  });

  it("returns amber classes for MEDIUM risk", () => {
    const cls = riskBadge("MEDIUM");
    expect(cls).toContain("border-amber-500");
    expect(cls).toContain("text-amber-600");
  });

  it("returns emerald classes for LOW risk", () => {
    const cls = riskBadge("LOW");
    expect(cls).toContain("border-emerald-500");
    expect(cls).toContain("text-emerald-600");
  });

  it("returns slate classes for unknown risk level", () => {
    const cls = riskBadge("UNKNOWN");
    expect(cls).toContain("border-slate-300");
    expect(cls).toContain("text-slate-500");
  });

  it("returns slate classes when level is undefined", () => {
    const cls = riskBadge(undefined);
    expect(cls).toContain("border-slate-300");
  });

  it("is case-insensitive (lowercase input)", () => {
    const cls = riskBadge("high");
    expect(cls).toContain("border-red-500");
  });
});

describe("fmtPct", () => {
  it("formats 0 as 0%", () => {
    expect(fmtPct(0)).toBe("0%");
  });

  it("formats 1 as 100%", () => {
    expect(fmtPct(1)).toBe("100%");
  });

  it("formats 0.5 as 50%", () => {
    expect(fmtPct(0.5)).toBe("50%");
  });

  it("rounds fractional percentages", () => {
    expect(fmtPct(0.123)).toBe("12%");
    expect(fmtPct(0.999)).toBe("100%");
  });
});
