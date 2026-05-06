import { useThemeStore } from "@/src/state/themeStore";
import { palettes, type Tokens } from "@/src/ui/designTokens";

/**
 * Live-themed token accessor.
 *
 * Replaces `import { tokens } from "@/src/ui/designTokens"` for any
 * component that needs to react to theme switches. Returns the full
 * `Tokens` object (colours, spacing, typography, …) for the currently
 * active palette. Subscribes via Zustand so toggling the theme in
 * Settings re-renders every consuming component.
 *
 * Static `tokens` from designTokens.ts continues to work for legacy
 * code; both expose the same shape. The static export resolves to
 * Modern Friendly at module-load time and never changes.
 *
 * Usage inside a component:
 *
 *   function Card() {
 *     const t = useTokens();
 *     return <View style={{ backgroundColor: t.colors.surface }} />;
 *   }
 *
 * For StyleSheet.create-style configurations, build the styles inside
 * the component body via `useMemo` so they recompute on theme change:
 *
 *   const t = useTokens();
 *   const styles = useMemo(() => StyleSheet.create({
 *     row: { backgroundColor: t.colors.surfaceAlt },
 *   }), [t]);
 */
export function useTokens(): Tokens {
  const theme = useThemeStore((s) => s.theme);
  return palettes[theme];
}
