import { DecisionPill } from "@/components/common/DecisionPill";
import { TierPill } from "@/components/common/TierPill";
import { PdpDecisionExplorer } from "@/components/pdp/PdpDecisionExplorer";
import {
  api,
  pdp,
  type AgentSummary,
  type EffectivePermissions,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function PolicyPage() {
  let agents: AgentSummary[] = [];
  let effective: EffectivePermissions[] = [];
  let error: string | null = null;

  try {
    const agentList = await api.agents({ page_size: 200 });
    agents = agentList.items;
    effective = (
      await Promise.all(
        agents.map(async (a) => {
          try {
            return await pdp.effective(a.villageAgentId);
          } catch {
            return null;
          }
        }),
      )
    ).filter((e): e is EffectivePermissions => e !== null && e.permissions.length > 0);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load policy data";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Policy &amp; Enforcement</h1>
      <p className="mb-8 text-ink-200">
        The PDP resolves each action against the agent&apos;s certs, autonomy level and safe-mode —
        returning allow / deny / step-up / downgrade. PEPs cache decisions and invalidate on
        revocation (ADR-0024).
      </p>

      {error ? (
        <div className="mb-8 rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load policy data: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          <div className="mb-10">
            <PdpDecisionExplorer agents={agents} />
          </div>

          <h2 className="mb-4 text-xl">Effective permissions</h2>
          {effective.length === 0 ? (
            <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
              No agents hold certs yet — the PDP denies every action until a cert is issued.
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {effective.map((ep) => (
                <div
                  key={ep.subject_agent_id}
                  className="overflow-hidden rounded-xl border border-ink-500"
                >
                  <div className="flex items-center justify-between bg-ink-800 px-4 py-3">
                    <span className="font-mono text-sm text-ink-50">{ep.subject_agent_id}</span>
                    <span className="rounded bg-ink-600 px-2 py-0.5 text-xs text-ink-100">
                      autonomy {ep.autonomy_level}
                    </span>
                  </div>
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-ink-900/40 text-ink-300">
                      <tr>
                        <th className="px-4 py-2 font-medium">Action</th>
                        <th className="px-4 py-2 font-medium">Tier</th>
                        <th className="px-4 py-2 font-medium">Cert status</th>
                        <th className="px-4 py-2 font-medium">Decision</th>
                        <th className="px-4 py-2 font-medium">Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-600">
                      {ep.permissions.map((p) => (
                        <tr key={p.action} className="hover:bg-ink-800/60">
                          <td className="px-4 py-2 font-mono text-xs text-gold-400">{p.action}</td>
                          <td className="px-4 py-2">
                            <TierPill tier={p.tier} />
                          </td>
                          <td className="px-4 py-2 text-ink-200">{p.cert_status}</td>
                          <td className="px-4 py-2">
                            <DecisionPill decision={p.decision} />
                          </td>
                          <td className="px-4 py-2 font-mono text-xs text-ink-300">
                            {p.reason_code}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
