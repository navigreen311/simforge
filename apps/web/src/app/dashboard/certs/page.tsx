import { StatusDot } from "@/components/common/StatusDot";
import { TierPill } from "@/components/common/TierPill";
import { api, certs, type AgentCert, type AgentSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function CertsPage() {
  let items: AgentCert[] = [];
  let agents: AgentSummary[] = [];
  let error: string | null = null;
  try {
    const [certList, agentList] = await Promise.all([certs.agent(), api.agents({ page_size: 200 })]);
    items = certList.items;
    agents = agentList.items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load certifications";
  }
  const nameById = new Map(agents.map((a) => [a.id, a.villageAgentId]));

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl">Certification Registry</h1>
      <p className="mb-8 text-ink-200">
        Signed, version-pinned agent capability certificates. Append-only lifecycle.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load certs: <code className="text-danger">{error}</code>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No certificates issued yet. Pass a scenario battery, then issue one via{" "}
          <code>POST /api/certs/agent/issue</code>.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-3 font-medium">Agent</th>
                <th className="px-4 py-3 font-medium">Forge capability</th>
                <th className="px-4 py-3 font-medium">Tier</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Expires</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {items.map((c) => (
                <tr key={c.id} className="hover:bg-ink-800/60">
                  <td className="px-4 py-3 font-mono text-xs text-ink-100">
                    {nameById.get(c.agentId) ?? c.agentId}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gold-400">{c.forgeCap}</td>
                  <td className="px-4 py-3">
                    <TierPill tier={c.tier} />
                  </td>
                  <td className="px-4 py-3">
                    <StatusDot status={c.status} label={c.status} />
                  </td>
                  <td className="px-4 py-3 text-ink-100">
                    {new Date(c.expiresAt).toLocaleDateString()}
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
