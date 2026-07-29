"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { runGoldenSuite } from "@/lib/api/client";

// Triggers the REAL golden suite, then refreshes so the persisted last-run result + history
// re-render from the server (the result panel is server-rendered, so it survives a reload).
export function GoldenRunButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setBusy(true);
    setError(null);
    try {
      await runGoldenSuite();
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Golden run failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <button
          onClick={onClick}
          disabled={busy}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:bg-gold-400 disabled:opacity-50"
        >
          {busy ? "Running suite…" : "Run golden suite"}
        </button>
        {busy && (
          <span className="text-xs text-ink-300">
            Running every golden scenario through the real evaluator and comparing to baseline…
          </span>
        )}
      </div>
      {error && (
        <p className="rounded border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
          Run failed: {error}
        </p>
      )}
    </div>
  );
}
