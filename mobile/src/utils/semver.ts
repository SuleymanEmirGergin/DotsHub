/**
 * Minimal semver comparison — good enough for the version gate.
 *
 * Parses "X.Y.Z" into a numeric tuple and compares field-by-field.
 * Pre-release suffixes ("1.2.3-beta") are stripped — they compare
 * equal to their release counterpart. This is deliberate: the
 * enforcement server carries "min: 1.2.3", and a dev on 1.2.3-beta
 * should not be blocked when they're running the same numeric
 * release that ships to the store.
 *
 * Returns:
 *   >0 if a > b,  0 if equal,  <0 if a < b.
 */

export function compareVersions(a: string, b: string): number {
  const pa = parseVersion(a);
  const pb = parseVersion(b);
  for (let i = 0; i < 3; i++) {
    if (pa[i] !== pb[i]) return pa[i] - pb[i];
  }
  return 0;
}

function parseVersion(v: string): [number, number, number] {
  const clean = String(v || "").split("-")[0].split("+")[0];
  const parts = clean.split(".").map((x) => parseInt(x, 10));
  return [
    Number.isFinite(parts[0]) ? parts[0] : 0,
    Number.isFinite(parts[1]) ? parts[1] : 0,
    Number.isFinite(parts[2]) ? parts[2] : 0,
  ];
}

/**
 * Convenience wrapper — returns true when `current` is older than
 * `minimum`. Used by the version-gate hook to decide whether to
 * surface the banner / block screen.
 */
export function isBelow(current: string, minimum: string): boolean {
  return compareVersions(current, minimum) < 0;
}
