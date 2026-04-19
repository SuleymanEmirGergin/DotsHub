/**
 * useVersionGate — startup hook that fetches /v1/config/features and
 * decides whether this build needs a warning banner or a hard block.
 *
 * Result states:
 *   { state: "loading" }                — initial fetch in flight
 *   { state: "ok" }                     — version is current or enforcement off
 *   { state: "warn", policy, current }  — behind `min`, show banner
 *   { state: "block", policy, current } — behind `min` and mode=block
 *
 * Non-blocking by design: network failures resolve to "ok" (the
 * featuresClient defaults enforcement to "off" when the backend is
 * unreachable). The only reason a user ever sees "block" is if the
 * backend explicitly returned that policy AND their build is
 * genuinely below `min`.
 */

import { useEffect, useState } from "react";
import Constants from "expo-constants";

import { fetchFeatures, type ClientVersionPolicy } from "../api/featuresClient";
import { isBelow } from "../utils/semver";

export type VersionGateState =
  | { state: "loading" }
  | { state: "ok" }
  | { state: "warn"; policy: ClientVersionPolicy; current: string }
  | { state: "block"; policy: ClientVersionPolicy; current: string };

function getCurrentAppVersion(): string {
  // expo-constants surfaces the app version from app.json / app.config.
  // In Expo Go / dev client this can be undefined — fall back to "0.0.0"
  // so the gate treats dev builds as out-of-date only if the server
  // explicitly says so (min = "0.0.0" by default, so dev passes).
  return Constants.expoConfig?.version ?? "0.0.0";
}

export function useVersionGate(): VersionGateState {
  const [state, setState] = useState<VersionGateState>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const features = await fetchFeatures();
      if (cancelled) return;

      const current = getCurrentAppVersion();
      const policy = features.client_version;

      // Enforcement off → always pass.
      if (policy.mode === "off") {
        setState({ state: "ok" });
        return;
      }

      // Below min → warn or block based on mode.
      if (isBelow(current, policy.min)) {
        setState({
          state: policy.mode === "block" ? "block" : "warn",
          policy,
          current,
        });
        return;
      }

      setState({ state: "ok" });
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
