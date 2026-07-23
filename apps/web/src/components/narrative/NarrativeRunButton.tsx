"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { runNarrativeScenario } from "@/lib/api/client";

export function NarrativeRunButton({
  scenarios,
}: {
  scenarios: { scenarioId: string; title: string }[];
}) {
  const router = useRouter();
  const [scenarioId, setScenarioId] = useState(scenarios[0]?.scenarioId ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onRun() {
    setBusy(true);
    setError(null);
    try {
      await runNarrativeScenario(scenarioId);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setBusy(false);
    }
  }

  if (scenarios.length === 0) return null;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1 text-xs text-ink-300">
        Scenario
        <select
          value={scenarioId}
          onChange={(e) => setScenarioId(e.target.value)}
          className="min-w-[18rem] rounded border border-ink-500 bg-ink-800 px-3 py-2 text-sm text-ink-50"
        >
          {scenarios.map((s) => (
            <option key={s.scenarioId} value={s.scenarioId}>
              {s.title} ({s.scenarioId})
            </option>
          ))}
        </select>
      </label>
      <button
        onClick={onRun}
        disabled={busy || !scenarioId}
        className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:bg-gold-400 disabled:opacity-50"
      >
        {busy ? "Running…" : "Run narrative scenario"}
      </button>
      {error && <span className="text-xs text-danger">{error}</span>}
    </div>
  );
}
