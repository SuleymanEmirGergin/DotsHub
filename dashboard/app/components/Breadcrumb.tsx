"use client";

import Link from "next/link";

export type BreadcrumbItem = { label: string; href?: string };

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  if (items.length === 0) return null;
  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1.5 text-[13px] text-muted-foreground mb-3"
    >
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span aria-hidden className="text-border">/</span>}
          {item.href ? (
            <Link
              href={item.href}
              className="text-primary font-semibold no-underline hover:underline"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-foreground">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
