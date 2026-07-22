"use client";

import { useState } from "react";

import { runGoldenSuite, type GoldenReport } from "@/lib/api/client";

export function GoldenRunButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<GoldenReport | null>(null);

  async function onClick() {
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      setReport(await runGoldenSuite());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Golden run failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <button
          onClick={onClick}
          disabled={busy}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:bg-gold-400 disabled:opacity-50"
        >
          {busy ? "Running suite…" : "Run golden suite"}
        </button>
        {report && (
          <span
            className={`rounded px-2 py-0.5 text-xs font-semibold ${
              report.passed ? "bg-success/15 text-success" : "bg-danger/15 text-danger"
            }`}
          >
            {report.passed
              ? `No regression · ${report.matched}/${report.total} match`
              : `${report.regressions} regression(s)`}
          </span>
        )}
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {report && (
        <div className="flex flex-col gap-2">
          {report.results.map((r) => (
            <div key={r.scenario_id} className="rounded-lg border border-ink-500 bg-ink-800 px-4 py-3 text-sm">
              <div className="flex items-center gap-3">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    r.status === "match" ? "bg-success" : "bg-danger"
                  }`}
                  aria-hidden
                />
                <span className="font-mono text-xs text-gold-400">{r.scenario_id}</span>
                <span className="ml-auto text-xs text-ink-300">{r.status}</span>
              </div>
              {r.diffs.length > 0 && (
                <ul className="mt-2 flex flex-col gap-0.5">
                  {r.diffs.map((d) => (
                    <li key={d.dim} className="font-mono text-[11px] text-danger">
                      {d.dim}: {String(d.expected)} → {String(d.actual)}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
