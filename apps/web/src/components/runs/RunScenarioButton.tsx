"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { runScenario } from "@/lib/api/client";

export function RunScenarioButton({ scenarioId }: { scenarioId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setBusy(true);
    setError(null);
    try {
      const run = await runScenario(scenarioId);
      router.push(`/dashboard/runs/${run.run_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end gap-1">
      <button
        onClick={onClick}
        disabled={busy}
        className="rounded bg-gold-500 px-3 py-1 text-xs font-semibold text-ink-900 transition-colors hover:bg-gold-400 disabled:opacity-50"
      >
        {busy ? "Running…" : "Run"}
      </button>
      {error && <span className="max-w-[12rem] text-[10px] text-danger">{error}</span>}
    </span>
  );
}
