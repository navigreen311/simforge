import { ReadinessMatrix } from "@/components/readiness/ReadinessMatrix";
import { PageMeta } from "@/components/ui/PageMeta";
import {
  api,
  capabilities,
  certs,
  type AgentCert,
  type AgentSummary,
  type CapabilityLabel,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function ReadinessPage() {
  let certList: AgentCert[] = [];
  let agents: AgentSummary[] = [];
  let rosterTotal = 0;
  let capLabels: Record<string, CapabilityLabel> = {};
  let error: string | null = null;
  try {
    const [c, a, caps] = await Promise.all([
      certs.agent(),
      api.agents({ page_size: 500 }),
      capabilities.labels(),
    ]);
    certList = c.items;
    agents = a.items;
    rosterTotal = a.total;
    capLabels = caps.capabilities;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load readiness data";
  }

  return (
    <div className="mx-auto max-w-[95rem]">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Readiness Gate Matrix</h1>
        <PageMeta />
      </div>
      <p className="mb-6 text-ink-200">
        Which agent holds which certification, for which Forge capability — spelled out in plain
        language. Blank cells reveal the coverage story; the header shows the share of agents with an
        active cert per capability.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <ReadinessMatrix
          agents={agents}
          certs={certList}
          capLabels={capLabels}
          rosterTotal={rosterTotal}
        />
      )}
    </div>
  );
}
