import { api, certs, type AgentCert, type AgentSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const CELL_STYLE: Record<string, string> = {
  active: "bg-success/20 text-success",
  expired: "bg-ink-600 text-ink-300",
  revoked: "bg-danger/20 text-danger",
  suspended: "bg-warning/20 text-warning",
};

export default async function ReadinessPage() {
  let certList: AgentCert[] = [];
  let agents: AgentSummary[] = [];
  let error: string | null = null;
  try {
    const [c, a] = await Promise.all([certs.agent(), api.agents({ page_size: 200 })]);
    certList = c.items;
    agents = a.items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load readiness data";
  }

  // Build agent × forge-cap grid from issued certs.
  const nameById = new Map(agents.map((a) => [a.id, a.villageAgentId]));
  const caps = Array.from(new Set(certList.map((c) => c.forgeCap))).sort();
  const agentIds = Array.from(new Set(certList.map((c) => c.agentId)));
  const cell = new Map<string, AgentCert>();
  for (const c of certList) cell.set(`${c.agentId}::${c.forgeCap}`, c);

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Readiness Gate Matrix</h1>
      <p className="mb-8 text-ink-200">Agent × Forge-capability certification status.</p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load: <code className="text-danger">{error}</code>
        </div>
      ) : caps.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No certifications yet — the matrix populates as agents earn Forge-capability certs.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead className="bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-3 font-medium">Agent</th>
                {caps.map((cap) => (
                  <th key={cap} className="px-3 py-3 text-center font-mono text-[11px]">
                    {cap.split(".").slice(1).join(".")}
                    <div className="text-ink-400">{cap.split(".")[0]}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {agentIds.map((aid) => (
                <tr key={aid}>
                  <td className="px-4 py-3 font-mono text-xs text-ink-100">
                    {nameById.get(aid) ?? aid}
                  </td>
                  {caps.map((cap) => {
                    const c = cell.get(`${aid}::${cap}`);
                    return (
                      <td key={cap} className="px-3 py-3 text-center">
                        {c ? (
                          <span
                            className={`inline-block rounded px-2 py-1 text-[11px] font-medium ${
                              CELL_STYLE[c.status] ?? "bg-ink-600"
                            }`}
                          >
                            {c.tier[0].toUpperCase()} · {c.status}
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
      )}
    </div>
  );
}
