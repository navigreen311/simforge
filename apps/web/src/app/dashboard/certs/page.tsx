import { CertsExplorer } from "@/components/certs/CertsExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import { api, certs, type AgentCert, type AgentSummary, type DeptCert } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const DEPT_STATUS: Record<string, string> = {
  active: "bg-success/15 text-success",
  suspended: "bg-warning/20 text-warning",
  revoked: "bg-danger/15 text-danger",
  expired: "bg-ink-600 text-ink-300",
};

export default async function CertsPage() {
  let items: AgentCert[] = [];
  let deptCerts: DeptCert[] = [];
  let agents: AgentSummary[] = [];
  let error: string | null = null;
  try {
    const [certList, deptList, agentList] = await Promise.all([
      certs.agent(),
      certs.dept(),
      api.agents({ page_size: 500 }),
    ]);
    items = certList.items;
    deptCerts = deptList.items;
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
        Certification is <strong>dual</strong> (decision D2): individual <em>AgentCerts</em> plus
        composite <em>DeptCerts</em> (department × Forge-context), which roll up from AgentCerts.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load certs: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          {items.length === 0 ? (
            <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
              No agent certificates issued yet. Pass a scenario battery, then issue one via{" "}
              <code>POST /api/certs/agent/issue</code>.
            </div>
          ) : (
            <CertsExplorer certs={items} nameById={nameById} />
          )}

          {/* Department certifications (composite; D2) */}
          <section className="mt-10">
            <h2 className="mb-1 text-xl">Department certifications (composite)</h2>
            <p className="mb-4 max-w-prose text-sm text-ink-300">
              A DeptCert certifies a whole department for a Forge-context. It requires a minimum
              number of covering AgentCerts plus passed department-wide (Intermediate+) scenarios,
              and auto-suspends if AgentCert coverage drops below that minimum.
            </p>
            {deptCerts.length === 0 ? (
              <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-sm text-ink-300">
                No department certifications yet. Once ≥N agents in a department are certified for a
                context&apos;s capabilities and dept-wide scenarios pass, issue one via{" "}
                <code>POST /api/certs/dept/issue</code>.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">Department</th>
                      <th className="px-4 py-2 font-medium">Forge context</th>
                      <th className="px-4 py-2 font-medium">Tier</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                      <th className="px-4 py-2 font-medium">Covering certs</th>
                      <th className="px-4 py-2 font-medium">Expires</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {deptCerts.map((d) => (
                      <tr key={d.id} className="hover:bg-ink-800/60">
                        <td className="px-4 py-2 text-ink-50">{d.departmentKey || d.departmentId}</td>
                        <td className="px-4 py-2 font-mono text-xs text-gold-400">{d.forgeContext}</td>
                        <td className="px-4 py-2 text-ink-200">{d.tier}</td>
                        <td className="px-4 py-2">
                          <span className={`rounded px-2 py-0.5 text-xs font-semibold ${DEPT_STATUS[d.status] ?? "bg-ink-600"}`}>
                            {d.status}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-center text-ink-200">
                          {d.prerequisiteAgentCertIds.length}
                        </td>
                        <td className="px-4 py-2 text-xs text-ink-300">
                          {new Date(d.expiresAt).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
