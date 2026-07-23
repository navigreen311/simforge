"use client";

import { useEffect, useState } from "react";

import { RefreshButton } from "@/components/ui/RefreshButton";

// "as of {time}" + refresh — the cross-cutting freshness affordance every page needs (P0-B).
// Timestamp is computed client-side (load time) to avoid an SSR/CSR hydration mismatch.
export function PageMeta() {
  const [asOf, setAsOf] = useState<string>("");
  useEffect(() => setAsOf(new Date().toLocaleString()), []);
  return (
    <div className="flex items-center gap-3 text-xs text-ink-400">
      {asOf && <span>as of {asOf}</span>}
      <RefreshButton />
    </div>
  );
}
