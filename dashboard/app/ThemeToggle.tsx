"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "pretriage-dashboard-theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem(STORAGE_KEY) as "light" | "dark" | null;
    const preferred = stored ?? (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    setTheme(preferred);
    document.documentElement.setAttribute("data-theme", preferred);
    document.documentElement.classList.toggle("dark", preferred === "dark");
  }, []);

  function toggle() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.setAttribute("data-theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  }

  if (!mounted) return null;

  // aria-pressed advertises the current state to screen readers so a
  // user can perceive "dark mode is active" / "light mode is active"
  // without relying on the visible text. The visible label remains
  // localised; aria-label is bilingual so the EN reader still gets a
  // sensible announcement when the dashboard is in TR mode.
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={theme === "dark"}
      aria-label={theme === "light" ? "Karanlık moda geç / Switch to dark mode" : "Aydınlık moda geç / Switch to light mode"}
      title={theme === "light" ? "Karanlık mod" : "Aydınlık mod"}
      className="px-3 py-1.5 rounded-lg border border-border bg-card text-foreground cursor-pointer text-sm font-semibold hover:bg-accent hover:text-accent-foreground transition-colors"
    >
      <span aria-hidden="true">{theme === "light" ? "🌙 Koyu" : "☀️ Açık"}</span>
    </button>
  );
}
