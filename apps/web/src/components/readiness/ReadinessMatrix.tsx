"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import type { AgentCert, AgentSummary, CapabilityLabel } from "@/lib/api/client";

const LEVEL_RANK: Record<string, number> = { L1: 1, L2: 2, L3: 3, L4: 4, L5: 5 };
const FLOOR = "L1";

const TIER_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};

const STATUS_TEXT: Record<string, string> = {
  active: "text-success",
  suspended: "text-warning",
  revoked: "text-danger",
  expired: "text-ink-300",
};
const STATUS_CELL: Record<string, string> = {
  active: "bg-success/15",
  suspended: "bg-warning/15",
  revoked: "bg-danger/15",
  expired: "bg-ink-600/40",
};

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-ink-500 bg-ink-800 px-4 py-3 text-xs">
      <div className="flex items-center gap-2">
        <span className="text-ink-400">Tiers:</span>
        <span className="text-ink-100">Foundational · Intermediate · Advanced-Crisis</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-ink-400">Status:</span>
        {[
          ["active", "active"],
          ["suspended", "suspended"],
          ["revoked", "revoked"],
          ["expired", "expired"],
        ].map(([k, label]) => (
          <span key={k} className="flex items-center gap-1">
            <span className={`h-2.5 w-2.5 rounded-full ${STATUS_CELL[k]} ${STATUS_TEXT[k]}`} />
            <span className={STATUS_TEXT[k]}>{label}</span>
          </span>
        ))}
        <span className="text-ink-500">— = no certification</span>
      </div>
    </div>
  );
}

export function ReadinessMatrix({
  agents,
  certs,
  capLabels,
  rosterTotal,
}: {
  agents: AgentSummary[];
  certs: AgentCert[];
  capLabels: Record<string, CapabilityLabel>;
  rosterTotal: number;
}) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [problemsOnly, setProblemsOnly] = useState(false);

  const caps = useMemo(
    () => Array.from(new Set(certs.map((c) => c.forgeCap))).sort(),
    [certs],
  );
  const cell = useMemo(() => {
    const m = new Map<string, AgentCert>();
    for (const c of certs) m.set(`${c.agentId}::${c.forgeCap}`, c);
    return m;
  }, [certs]);

  const activeByAgent = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of certs)
      if (c.status === "active") m.set(c.agentId, (m.get(c.agentId) ?? 0) + 1);
    return m;
  }, [certs]);
  const certCountByAgent = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of certs) m.set(c.agentId, (m.get(c.agentId) ?? 0) + 1);
    return m;
  }, [certs]);

  const isContradiction = (a: AgentSummary) =>
    (LEVEL_RANK[a.currentAutonomyLevel] ?? 1) > (LEVEL_RANK[FLOOR] ?? 1) &&
    (activeByAgent.get(a.id) ?? 0) === 0;

  const agentHasProblem = (a: AgentSummary) => {
    if (isContradiction(a)) return true;
    return caps.some((cap) => {
      const c = cell.get(`${a.id}::${cap}`);
      return c && ["suspended", "revoked", "expired"].includes(c.status);
    });
  };

  // --- summary rollups (over the FULL set, not the filtered view) ---
  const rollup = { active: 0, suspended: 0, revoked: 0, expired: 0, no_cert: 0 };
  for (const a of agents)
    for (const cap of caps) {
      const c = cell.get(`${a.id}::${cap}`);
      if (!c) rollup.no_cert++;
      else if (c.status in rollup) (rollup as Record<string, number>)[c.status]++;
      else rollup.no_cert++;
    }
  const agentsWithActive = agents.filter((a) => (activeByAgent.get(a.id) ?? 0) > 0).length;
  const contradictions = agents.filter(isContradiction);
  const warn = agentsWithActive === 0 || contradictions.length > 0;

  // --- filtered rows ---
  const rows = agents.filter((a) => {
    if (search.trim()) {
      const q = search.toLowerCase();
      if (!`${a.name} ${a.villageAgentId} ${a.role}`.toLowerCase().includes(q)) return false;
    }
    if (problemsOnly && !agentHasProblem(a)) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-4">
      {/* Summary panel — informational when healthy, amber when 0% active or a contradiction. */}
      <div
        className={`rounded-xl border p-4 text-sm ${
          warn ? "border-warning/50 bg-warning/10" : "border-ink-500 bg-ink-800"
        }`}
      >
        <div className="flex items-center gap-2">
          {warn && <span className="text-warning">⚠</span>}
          <span className="font-semibold text-ink-50">
            {agentsWithActive} of {agents.length} agents hold an active certification for any
            capability.
          </span>
          <span className="ml-auto text-xs text-ink-400">
            Showing {agents.length} of {rosterTotal} agents
          </span>
        </div>
        {agentsWithActive === 0 && (
          <p className="mt-2 text-ink-100">
            No agent currently holds an active certification. Every capability shows 0% active
            coverage. Until certifications are issued and active, no agent should be operating at an
            autonomy level above the minimum.
          </p>
        )}
        {contradictions.length > 0 && (
          <p className="mt-2 text-warning">
            {contradictions.length} agent(s) authorized above the minimum autonomy with zero active
            certs: {contradictions.map((a) => `${a.villageAgentId} (${a.currentAutonomyLevel})`).join(", ")}.
          </p>
        )}
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-ink-300">
          <span className={STATUS_TEXT.active}>{rollup.active} active</span>
          <span className={STATUS_TEXT.suspended}>{rollup.suspended} suspended</span>
          <span className={STATUS_TEXT.revoked}>{rollup.revoked} revoked</span>
          <span className={STATUS_TEXT.expired}>{rollup.expired} expired</span>
          <span className="text-ink-400">{rollup.no_cert} no-cert cells</span>
        </div>
      </div>

      <Legend />

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search agents…"
          className="min-w-[14rem] rounded border border-ink-500 bg-ink-800 px-3 py-1.5 text-sm text-ink-50 placeholder:text-ink-400"
        />
        <label className="flex items-center gap-2 text-xs text-ink-300">
          <input type="checkbox" checked={problemsOnly} onChange={(e) => setProblemsOnly(e.target.checked)} />
          Problems only (suspended / revoked / expired / autonomy contradiction)
        </label>
        <span className="ml-auto text-xs text-ink-400">
          {rows.length} of {agents.length} agents shown
        </span>
      </div>

      {caps.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No certifications yet — the matrix populates as agents earn Forge-capability certs.
        </div>
      ) : (
        <div className="max-h-[70vh] overflow-auto rounded-xl border border-ink-500">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 top-0 z-30 border-b border-ink-600 bg-ink-900 px-4 py-3 font-medium text-ink-200">
                  Agent
                </th>
                {caps.map((cap) => {
                  const info = capLabels[cap];
                  const activeN = agents.filter(
                    (a) => cell.get(`${a.id}::${cap}`)?.status === "active",
                  ).length;
                  const pct = agents.length ? Math.round((activeN / agents.length) * 100) : 0;
                  return (
                    <th
                      key={cap}
                      title={cap}
                      className="sticky top-0 z-20 min-w-[10rem] border-b border-ink-600 bg-ink-900 px-3 py-2 text-center align-bottom font-medium"
                    >
                      <div className="text-[11px] leading-tight text-ink-50">
                        {info?.label ?? cap}
                      </div>
                      <div className="text-[10px] text-ink-400">{info?.forge ?? cap.split(".")[0]}</div>
                      <div className={`mt-1 text-[10px] ${pct === 0 ? "text-danger" : "text-success"}`}>
                        {pct}% active
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {rows.map((a) => {
                const contradiction = isContradiction(a);
                const noCerts = (certCountByAgent.get(a.id) ?? 0) === 0;
                return (
                  <tr key={a.id}>
                    <th
                      className="sticky left-0 z-10 border-r border-ink-600 bg-ink-900/95 px-4 py-3 text-left font-normal"
                      scope="row"
                    >
                      <button
                        onClick={() => router.push(`/dashboard/runs?agent=${a.villageAgentId}`)}
                        className="font-mono text-xs text-ink-100 hover:text-gold-400"
                      >
                        {a.villageAgentId}
                      </button>
                      <div className="mt-0.5 flex items-center gap-1">
                        {contradiction ? (
                          <span
                            className="rounded bg-danger/20 px-1.5 py-0.5 text-[10px] text-danger"
                            title="This agent is authorized at a high autonomy level but holds no active certification. Under the readiness policy, autonomy should not exceed what active certs support. Flagged for review."
                          >
                            ⚠ {a.currentAutonomyLevel} · no active cert
                          </span>
                        ) : (
                          <span className="text-[10px] text-ink-400">{a.currentAutonomyLevel}</span>
                        )}
                        {noCerts && !contradiction && (
                          <span className="rounded bg-ink-700 px-1.5 py-0.5 text-[10px] text-ink-400">
                            no certifications
                          </span>
                        )}
                      </div>
                    </th>
                    {caps.map((cap) => {
                      const c = cell.get(`${a.id}::${cap}`);
                      if (!c)
                        return (
                          <td
                            key={cap}
                            title="No certification for this capability."
                            className="px-3 py-3 text-center text-ink-600"
                          >
                            —
                          </td>
                        );
                      return (
                        <td key={cap} className="px-2 py-2 text-center">
                          <button
                            onClick={() =>
                              router.push(`/dashboard/lineage?root=urn:gc:village:cert:${c.id}`)
                            }
                            title={`${cap} — view provenance`}
                            className={`w-full rounded px-2 py-1 text-[11px] hover:ring-1 hover:ring-gold-500 ${STATUS_CELL[c.status] ?? "bg-ink-600"}`}
                          >
                            <div className="text-ink-100">{TIER_LABEL[c.tier] ?? c.tier}</div>
                            <div className={STATUS_TEXT[c.status] ?? "text-ink-200"}>{c.status}</div>
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
