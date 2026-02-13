"use client";

import Link from "next/link";

export type BreadcrumbItem = { label: string; href?: string };

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  if (items.length === 0) return null;
  return (
    <nav
      aria-label="Breadcrumb"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        fontSize: 13,
        color: "var(--dash-text-muted)",
        marginBottom: 12,
      }}
    >
      {items.map((item, i) => (
        <span key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {i > 0 && <span aria-hidden style={{ color: "var(--dash-border)" }}>/</span>}
          {item.href ? (
            <Link
              href={item.href}
              style={{ color: "var(--dash-accent)", textDecoration: "none", fontWeight: 600 }}
            >
              {item.label}
            </Link>
          ) : (
            <span style={{ color: "var(--dash-text)" }}>{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
