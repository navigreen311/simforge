import { CertsExplorer } from "@/components/certs/CertsExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import { api, certs, type AgentCert, type AgentSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function CertsPage() {
  let items: AgentCert[] = [];
  let agents: AgentSummary[] = [];
  let error: string | null = null;
  try {
    const [certList, agentList] = await Promise.all([certs.agent(), api.agents({ page_size: 500 })]);
    items = certList.items;
    agents = agentList.items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load certifications";
  }
  const nameById = Object.fromEntries(agents.map((a) => [a.id, a.villageAgentId]));

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex items-start justify-between">
        <h1 className="text-3xl">Certification Registry</h1>
        <PageMeta />
      </div>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        The signed, append-only record of which agent is certified for which Forge capability, at
        what tier and status — the authoritative &ldquo;who can do what&rdquo; for the Village.
        Filter by status, tier, or forge; click the Agent column to sort/group by agent.
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
        <CertsExplorer certs={items} nameById={nameById} />
      )}
    </div>
  );
}
