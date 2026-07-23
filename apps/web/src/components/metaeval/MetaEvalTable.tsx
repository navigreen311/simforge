"use client";

import { useState } from "react";

import type { DimStats } from "@/lib/api/client";

// The three LLM-judge dims (stub-scored when the judge provider is stub). Everything else is a
// deterministic heuristic scorer — so a zero-variance heuristic dim is NOT explained by the stub.
const JUDGE_DIMS = new Set([
  "p7_customer_experience",
  "c1_breath_coherence",
  "c2_soul_stability",
]);

function fmt(v: number | null, digits = 2): string {
  return v === null || v === undefined ? "—" : v.toFixed(digits);
}

function flagPill(flag: string) {
  const styles: Record<string, string> = {
    constant: "bg-danger/15 text-danger",
    non_discriminating: "bg-warning/20 text-warning",
    insufficient_data: "bg-ink-600 text-ink-300",
    no_data: "bg-ink-600 text-ink-300",
  };
  return (
    <span key={flag} className={`rounded px-2 py-0.5 text-[11px] ${styles[flag] ?? "bg-ink-600 text-ink-100"}`}>
      {flag}
    </span>
  );
}

export function MetaEvalTable({ dimensions }: { dimensions: DimStats[] }) {
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const isFlagged = (d: DimStats) => d.flags.some((f) => f === "constant" || f === "non_discriminating");
  const rows = flaggedOnly ? dimensions.filter(isFlagged) : dimensions;

  return (
    <div className="flex flex-col gap-2">
      <label className="flex items-center gap-2 self-end text-xs text-ink-300">
        <input type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} />
        Show only flagged
      </label>
      <div className="overflow-x-auto rounded-xl border border-ink-500">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-ink-800 text-ink-200">
            <tr>
              <th className="px-4 py-3 font-medium">Dimension</th>
              <th className="px-4 py-3 font-medium">Scorer</th>
              <th className="px-4 py-3 font-medium">n</th>
              <th className="px-4 py-3 font-medium">Mean</th>
              <th className="px-4 py-3 font-medium">Std</th>
              <th className="px-4 py-3 font-medium">Passed</th>
              <th className="px-4 py-3 font-medium">Failed</th>
              <th className="px-4 py-3 font-medium">Discrimination</th>
              <th className="px-4 py-3 font-medium">Flags</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-600">
            {rows.map((d) => {
              const noSignal = isFlagged(d);
              const inverted = d.discrimination !== null && d.discrimination < -0.02;
              const isStub = JUDGE_DIMS.has(d.dim);
              return (
                <tr key={d.dim} className={noSignal ? "bg-danger/5" : "hover:bg-ink-800/60"}>
                  <td className="px-4 py-3 font-mono text-xs text-gold-400">{d.dim}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] ${
                        isStub ? "bg-warning/20 text-warning" : "bg-ink-600 text-ink-200"
                      }`}
                    >
                      {isStub ? "stub-judge" : "heuristic"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink-200">{d.n}</td>
                  <td className="px-4 py-3 text-ink-100">{fmt(d.mean)}</td>
                  <td className={`px-4 py-3 ${d.stddev !== null && d.stddev < 0.001 ? "text-danger" : "text-ink-100"}`}>
                    {fmt(d.stddev, 3)}
                  </td>
                  <td className="px-4 py-3 text-ink-200">{fmt(d.mean_passed)}</td>
                  <td className="px-4 py-3 text-ink-200">{fmt(d.mean_failed)}</td>
                  <td
                    className={`px-4 py-3 font-medium ${
                      inverted
                        ? "text-danger"
                        : d.discrimination !== null && Math.abs(d.discrimination) < 0.05
                          ? "text-warning"
                          : "text-ink-50"
                    }`}
                    title={inverted ? "Inverted — scores worse when the run passes (a different, worse defect than a dead dim)" : undefined}
                  >
                    {fmt(d.discrimination)}
                    {inverted && " ⚠"}
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex flex-wrap gap-1">{d.flags.map(flagPill)}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
