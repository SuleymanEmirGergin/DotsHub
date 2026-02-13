"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

const REFRESH_INTERVAL_MS = 30_000;

export function StatusAutoRefresh({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    const id = setInterval(() => router.refresh(), REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [router]);

  return <>{children}</>;
}
