"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  api,
  type AgentSummary,
  type PackSummary,
  type RunCounts,
  type RunQuery,
  type RunSummary,
} from "@/lib/api/client";

const PAGE_SIZE = 25;
const TIER_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};
const MODE_TIP: Record<string, string> = {
  sandbox: "ran against mock Forge APIs — no real systems touched",
  integrated: "ran against real Forge endpoints",
};

function relTime(iso: string): string {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function fmtLatency(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms.toLocaleString()} ms`;
  return `${(ms / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 })} s`;
}

function fromDate(range: string): string | undefined {
  if (!range) return undefined;
  const days = range === "24h" ? 1 : range === "7d" ? 7 : range === "30d" ? 30 : 0;
  if (!days) return undefined;
  return new Date(Date.now() - days * 86_400_000).toISOString();
}

export function RunsExplorer({
  agents,
  packs,
  tierByScenario,
  titleByScenario,
  initialAgent,
}: {
  agents: AgentSummary[];
  packs: PackSummary[];
  tierByScenario: Record<string, string>;
  titleByScenario: Record<string, string>;
  initialAgent?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [tier, setTier] = useState("");
  const [execMode, setExecMode] = useState("");
  const [blind, setBlind] = useState("");
  const [agent, setAgent] = useState(initialAgent ?? "");
  const [pack, setPack] = useState("");
  const [range, setRange] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  const [rows, setRows] = useState<RunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<RunCounts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const filters: RunQuery = useMemo(
    () => ({
      status: status || undefined,
      tier: tier || undefined,
      execution_mode: execMode || undefined,
      blind: blind === "" ? undefined : blind === "yes",
      agent: agent || undefined,
      pack: pack || undefined,
      from: fromDate(range),
    }),
    [status, tier, execMode, blind, agent, pack, range],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, c] = await Promise.all([
        api.runs({ ...filters, limit: PAGE_SIZE, offset }),
        api.runCounts(filters),
      ]);
      setRows(list.items);
      setTotal(list.total);
      setCounts(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load runs");
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    load();
  }, [load]);

  // Any filter change resets to the first page.
  useEffect(() => {
    setOffset(0);
  }, [status, tier, execMode, blind, agent, pack, range]);

  // Client-side text search within the loaded page (run id / scenario title + id / agent).
  const shown = search.trim()
    ? rows.filter((r) => {
        const q = search.toLowerCase();
        return (
          r.run_id.toLowerCase().includes(q) ||
          r.scenario_id.toLowerCase().includes(q) ||
          (titleByScenario[r.scenario_id] ?? "").toLowerCase().includes(q) ||
          r.agent_village_id.toLowerCase().includes(q)
        );
      })
    : rows;

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const selectCls =
    "rounded border border-ink-500 bg-ink-800 px-2 py-1.5 text-xs text-ink-100";

  return (
    <div className="flex flex-col gap-3">
      {/* Counts */}
      {counts && (
        <div className="text-sm text-ink-200">
          <span className="font-medium text-ink-50">{counts.total}</span> total ·{" "}
          <span className="text-success">{counts.passed} passed</span> ·{" "}
          <span className="text-danger">{counts.failed} failed</span> ·{" "}
          <span className="text-warning">{counts.errored} errored</span>
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search run / scenario title or id / agent…"
          className="min-w-[14rem] flex-1 rounded border border-ink-500 bg-ink-800 px-3 py-1.5 text-sm text-ink-50 placeholder:text-ink-400"
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={selectCls}>
          <option value="">status: all</option>
          {["passed", "failed", "errored"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={tier} onChange={(e) => setTier(e.target.value)} className={selectCls}>
          <option value="">tier: all</option>
          {["foundational", "intermediate", "advanced_crisis"].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select value={execMode} onChange={(e) => setExecMode(e.target.value)} className={selectCls}>
          <option value="">mode: all</option>
          <option value="sandbox">sandbox</option>
          <option value="integrated">integrated</option>
        </select>
        <select value={blind} onChange={(e) => setBlind(e.target.value)} className={selectCls}>
          <option value="">blind: all</option>
          <option value="yes">blind</option>
          <option value="no">not blind</option>
        </select>
        <select value={agent} onChange={(e) => setAgent(e.target.value)} className={selectCls}>
          <option value="">agent: all</option>
          {agents.map((a) => (
            <option key={a.villageAgentId} value={a.villageAgentId}>
              {a.villageAgentId}
            </option>
          ))}
        </select>
        <select value={pack} onChange={(e) => setPack(e.target.value)} className={selectCls}>
          <option value="">pack: all</option>
          {packs.map((p) => (
            <option key={p.packId} value={p.packId}>
              {p.name}
            </option>
          ))}
        </select>
        <select value={range} onChange={(e) => setRange(e.target.value)} className={selectCls}>
          <option value="">any time</option>
          <option value="24h">last 24h</option>
          <option value="7d">last 7d</option>
          <option value="30d">last 30d</option>
        </select>
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load runs: <code className="text-danger">{error}</code>
        </div>
      ) : loading ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-center text-ink-300">
          Loading…
        </div>
      ) : shown.length === 0 ? (
        <EmptyState
          title="No runs match"
          description="Try widening the filters or clearing the search."
          icon="🗂"
        />
      ) : (
        <div className="max-h-[70vh] overflow-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="sticky top-0 z-10 bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-3 font-medium">Run</th>
                <th className="px-4 py-3 font-medium">Scenario</th>
                <th className="px-4 py-3 font-medium">Agent</th>
                <th className="px-4 py-3 font-medium">Tier</th>
                <th className="px-4 py-3 font-medium">Mode</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Outcome</th>
                <th className="px-4 py-3 text-right font-medium">Latency</th>
                <th className="px-4 py-3 font-medium">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {shown.map((r) => (
                <tr
                  key={r.run_id}
                  onClick={() => router.push(`/dashboard/runs/${r.run_id}`)}
                  className="cursor-pointer hover:bg-ink-800/60"
                >
                  <td className="px-4 py-3 font-mono text-[10px] text-ink-400" title={r.run_id}>
                    {r.run_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-ink-50">
                      {titleByScenario[r.scenario_id] ?? "(untitled scenario)"}
                    </div>
                    <div className="font-mono text-[10px] text-ink-400">{r.scenario_id}</div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-100">{r.agent_village_id}</td>
                  <td className="px-4 py-3">
                    <span
                      className="rounded bg-ink-600 px-2 py-0.5 text-xs text-ink-200"
                      title={tierByScenario[r.scenario_id] ?? "unknown tier"}
                    >
                      {TIER_LABEL[tierByScenario[r.scenario_id]] ?? "—"}
                    </span>
                  </td>
                  <td
                    className="px-4 py-3 text-xs text-ink-300"
                    title={MODE_TIP[r.execution_mode] ?? r.execution_mode}
                  >
                    {r.execution_mode}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-2">
                      <RunStatusBadge status={r.status} />
                      {["queued", "running", "scoring"].includes(r.status) && (
                        <a
                          href={`/dashboard/runs/${r.run_id}/watch`}
                          onClick={(e) => e.stopPropagation()}
                          className="rounded bg-info/15 px-1.5 py-0.5 text-[10px] text-info hover:bg-info/25"
                          title="Watch this in-progress run live"
                        >
                          ● watch
                        </a>
                      )}
                    </span>
                  </td>
                  <td
                    className="px-4 py-3 text-ink-100"
                    title="The scenario reached a terminal 'resolved' state."
                  >
                    {r.outcome ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-ink-200">
                    {fmtLatency(r.latency_ms)}
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-300" title={r.started_at}>
                    {relTime(r.started_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div className="flex items-center gap-3 text-xs text-ink-300">
          <span className="ml-auto">
            Page {currentPage} of {pages} ({total} runs)
          </span>
          <button
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            disabled={offset === 0}
            className="rounded border border-ink-500 px-2 py-1 disabled:opacity-40"
          >
            Prev
          </button>
          <button
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
            disabled={currentPage >= pages}
            className="rounded border border-ink-500 px-2 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
