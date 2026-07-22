"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { replayRun, type ReplayComparison } from "@/lib/api/client";

export function ReplayRunButton({ runId }: { runId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReplayComparison | null>(null);

  async function onClick() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await replayRun(runId));
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Replay failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        onClick={onClick}
        disabled={busy}
        className="rounded bg-ink-700 px-3 py-1.5 text-xs font-semibold text-ink-50 transition-colors hover:bg-ink-600 disabled:opacity-50"
        title="Re-execute this run's scenario and diff against the original (sandboxed)"
      >
        {busy ? "Replaying…" : "↺ Replay"}
      </button>
      {error && <span className="max-w-[16rem] text-[10px] text-danger">{error}</span>}
      {result && (
        <div className="w-72 rounded-lg border border-ink-600 bg-ink-900/70 p-3 text-xs">
          <div className="flex items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 font-semibold ${
                result.deterministic
                  ? "bg-success/15 text-success"
                  : "bg-warning/20 text-warning"
              }`}
            >
              {result.deterministic ? "Deterministic" : "Diverged"}
            </span>
            <a href={`/dashboard/runs/${result.replay_run_id}`} className="text-gold-400 hover:underline">
              replay run →
            </a>
          </div>
          <div className="mt-2 text-ink-300">
            transcript {result.transcript_identical ? "identical" : "differs"} · gate{" "}
            {String(result.original_gate_passed)}→{String(result.replay_gate_passed)}
          </div>
          {result.scorecard_diffs.length > 0 && (
            <ul className="mt-2 flex flex-col gap-0.5">
              {result.scorecard_diffs.map((d) => (
                <li key={d.dim} className="font-mono text-[10px] text-ink-200">
                  {d.dim}: {String(d.original)} → {String(d.replay)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
