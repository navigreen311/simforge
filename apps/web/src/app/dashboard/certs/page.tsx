import { CertsExplorer } from "@/components/certs/CertsExplorer";
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
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Certification Registry</h1>
      <p className="mb-6 text-ink-200">
        Signed, version-pinned agent capability certificates — append-only lifecycle. Filter by
        status, tier, or forge; sort by agent to group.
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
