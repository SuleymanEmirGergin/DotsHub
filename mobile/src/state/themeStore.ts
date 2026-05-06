import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";

import type { ThemeName } from "@/src/ui/designTokens";

// Persistence key. Bumping this string invalidates everyone's saved
// preference at once — only do that if the *meaning* of theme names
// changes (e.g. renaming "sade" to "clinical"); colour tweaks within an
// existing theme don't need a reset.
const STORAGE_KEY = "triaige.theme.v1";

interface ThemeStore {
  theme: ThemeName;
  /** True once the persisted theme has been read from AsyncStorage.
   *  Splash / app-init code can gate UI rendering on this so first paint
   *  uses the user's chosen palette rather than the default. */
  loaded: boolean;
  setTheme: (next: ThemeName) => void;
  /** Hydrate from AsyncStorage. Safe to call multiple times — subsequent
   *  calls are no-ops once `loaded` is true. */
  hydrate: () => Promise<void>;
}

export const useThemeStore = create<ThemeStore>((set, get) => ({
  // Default — Modern Friendly. Matches `tokens` in designTokens.ts so
  // components that haven't been migrated to `useTokens()` still render
  // in the same palette as ones that have, before hydration completes.
  theme: "modern",
  loaded: false,

  setTheme: (next) => {
    if (get().theme === next) return;
    set({ theme: next });
    // Fire-and-forget: a failed write means the choice doesn't survive a
    // cold start, but the in-memory state is still correct for the
    // current session. We never want a storage hiccup to block the
    // user's tap on the theme switcher.
    AsyncStorage.setItem(STORAGE_KEY, next).catch(() => {});
  },

  hydrate: async () => {
    if (get().loaded) return;
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      if (raw === "modern" || raw === "sade") {
        set({ theme: raw, loaded: true });
        return;
      }
    } catch {
      // ignore — fall through to the default theme + loaded=true so the
      // app doesn't get stuck on a splash waiting for storage to recover.
    }
    set({ loaded: true });
  },
}));
