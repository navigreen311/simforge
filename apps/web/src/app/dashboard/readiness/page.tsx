import Link from "next/link";

import { api, certs, type AgentCert, type AgentSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const CELL_STYLE: Record<string, string> = {
  active: "bg-success/20 text-success",
  expired: "bg-ink-600 text-ink-300",
  revoked: "bg-danger/20 text-danger",
  suspended: "bg-warning/20 text-warning",
};

const TIER_ABBR: Record<string, string> = {
  foundational: "F",
  intermediate: "I",
  advanced_crisis: "A-C",
};

function Legend() {
  return (
    <div className="mb-6 flex flex-wrap items-center gap-4 rounded-lg border border-ink-500 bg-ink-800 px-4 py-3 text-xs">
      <span className="text-ink-300">Tier:</span>
      <span className="text-ink-100">F Foundational · I Intermediate · A-C Advanced-Crisis</span>
      <span className="ml-4 text-ink-300">Status:</span>
      {[
        ["active", "active"],
        ["suspended", "suspended"],
        ["revoked", "revoked"],
        ["expired", "expired"],
      ].map(([k, label]) => (
        <span key={k} className={`rounded px-2 py-0.5 ${CELL_STYLE[k] ?? "bg-ink-600"}`}>
          {label}
        </span>
      ))}
      <span className="rounded px-2 py-0.5 text-ink-500">— no cert</span>
    </div>
  );
}

export default async function ReadinessPage() {
  let certList: AgentCert[] = [];
  let agents: AgentSummary[] = [];
  let error: string | null = null;
  try {
    const [c, a] = await Promise.all([certs.agent(), api.agents({ page_size: 500 })]);
    certList = c.items;
    agents = a.items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load readiness data";
  }

  const caps = Array.from(new Set(certList.map((c) => c.forgeCap))).sort();
  const cell = new Map<string, AgentCert>();
  for (const c of certList) cell.set(`${c.agentId}::${c.forgeCap}`, c);

  // Aggregate: fraction of agents holding an ACTIVE cert per capability.
  const activePct = (cap: string) => {
    if (agents.length === 0) return 0;
    const n = agents.filter((a) => cell.get(`${a.id}::${cap}`)?.status === "active").length;
    return Math.round((n / agents.length) * 100);
  };

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Readiness Gate Matrix</h1>
      <p className="mb-6 text-ink-200">
        Every agent × Forge-capability. Blank cells reveal the coverage story; the top row is the
        share of agents with an active cert per capability.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load: <code className="text-danger">{error}</code>
        </div>
      ) : caps.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No certifications yet — the matrix populates as agents earn Forge-capability certs.
        </div>
      ) : (
        <>
          <Legend />
          <div className="overflow-x-auto rounded-xl border border-ink-500">
            <table className="min-w-full border-collapse text-left text-sm">
              <thead className="bg-ink-800 text-ink-200">
                <tr>
                  <th className="sticky left-0 z-10 bg-ink-800 px-4 py-3 font-medium">Agent</th>
                  {caps.map((cap) => (
                    <th key={cap} className="px-3 py-3 text-center font-mono text-[11px]">
                      <Link href="/dashboard/certs" className="hover:text-gold-400">
                        {cap.split(".").slice(1).join(".")}
                        <div className="text-ink-400">{cap.split(".")[0]}</div>
                      </Link>
                    </th>
                  ))}
                </tr>
                <tr className="bg-ink-900/50 text-[11px] text-ink-300">
                  <th className="sticky left-0 z-10 bg-ink-900/50 px-4 py-2 font-normal">
                    % agents active
                  </th>
                  {caps.map((cap) => {
                    const pct = activePct(cap);
                    return (
                      <th
                        key={cap}
                        className={`px-3 py-2 text-center font-normal ${
                          pct === 0 ? "text-danger" : "text-success"
                        }`}
                      >
                        {pct}%
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-600">
                {agents.map((a) => (
                  <tr key={a.id}>
                    <td className="sticky left-0 z-10 bg-ink-900/80 px-4 py-3 font-mono text-xs text-ink-100">
                      <Link href={`/dashboard/runs?agent=${a.villageAgentId}`} className="hover:text-gold-400">
                        {a.villageAgentId}
                      </Link>
                    </td>
                    {caps.map((cap) => {
                      const c = cell.get(`${a.id}::${cap}`);
                      return (
                        <td key={cap} className="px-3 py-3 text-center">
                          {c ? (
                            <span
                              className={`inline-block rounded px-2 py-1 text-[11px] font-medium ${
                                CELL_STYLE[c.status] ?? "bg-ink-600"
                              }`}
                            >
                              {TIER_ABBR[c.tier] ?? c.tier[0].toUpperCase()} · {c.status}
                            </span>
                          ) : (
                            <span className="text-ink-500">—</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
