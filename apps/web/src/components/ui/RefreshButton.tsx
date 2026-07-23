"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function RefreshButton({ label = "Refresh" }: { label?: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <button
      onClick={() => {
        setBusy(true);
        router.refresh();
        setTimeout(() => setBusy(false), 600);
      }}
      disabled={busy}
      className="rounded border border-ink-500 px-2 py-1 text-xs text-ink-200 transition-colors hover:bg-ink-700 disabled:opacity-50"
    >
      {busy ? "Refreshing…" : `↻ ${label}`}
    </button>
  );
}
