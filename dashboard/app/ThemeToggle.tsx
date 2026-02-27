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
  }, []);

  function toggle() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.setAttribute("data-theme", next);
  }

  if (!mounted) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      title={theme === "light" ? "Karanlık mod" : "Aydınlık mod"}
      style={{
        padding: "6px 12px",
        borderRadius: 8,
        border: "1px solid var(--dash-border)",
        background: "var(--dash-bg-card)",
        color: "var(--dash-text)",
        cursor: "pointer",
        fontSize: 14,
        fontWeight: 600,
      }}
    >
      {theme === "light" ? "🌙 Koyu" : "☀️ Açık"}
    </button>
  );
}
