import Link from "next/link";

import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { api, type RunSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  let runs: RunSummary[] = [];
  let error: string | null = null;
  try {
    runs = (await api.runs()).items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load runs";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl">Runs</h1>
      <p className="mb-8 text-ink-200">Scenario executions, newest first.</p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load runs: <code className="text-danger">{error}</code>
        </div>
      ) : runs.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No runs yet. Open a Pack, pick a scenario, and hit <strong>Run</strong>.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-3 font-medium">Scenario</th>
                <th className="px-4 py-3 font-medium">Agent</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Outcome</th>
                <th className="px-4 py-3 font-medium">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {runs.map((r) => (
                <tr key={r.run_id} className="hover:bg-ink-800/60">
                  <td className="px-4 py-3">
                    <Link
                      href={`/dashboard/runs/${r.run_id}`}
                      className="font-mono text-xs text-gold-400 hover:underline"
                    >
                      {r.scenario_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-100">{r.agent_village_id}</td>
                  <td className="px-4 py-3">
                    <RunStatusBadge status={r.status} />
                  </td>
                  <td className="px-4 py-3 text-ink-100">{r.outcome ?? "—"}</td>
                  <td className="px-4 py-3 text-ink-100">
                    {r.latency_ms != null ? `${r.latency_ms}ms` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
