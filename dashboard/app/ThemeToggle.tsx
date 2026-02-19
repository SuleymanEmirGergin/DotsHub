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

  return (
    <button
      type="button"
      onClick={toggle}
      title={theme === "light" ? "Karanlık mod" : "Aydınlık mod"}
      className="px-3 py-1.5 rounded-lg border border-border bg-card text-foreground cursor-pointer text-sm font-semibold hover:bg-accent hover:text-accent-foreground transition-colors"
    >
      {theme === "light" ? "🌙 Koyu" : "☀️ Açık"}
    </button>
  );
}
