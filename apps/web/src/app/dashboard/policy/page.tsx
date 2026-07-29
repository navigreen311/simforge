import { DecisionPill } from "@/components/common/DecisionPill";
import { TierPill } from "@/components/common/TierPill";
import { PdpDecisionExplorer } from "@/components/pdp/PdpDecisionExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import {
  api,
  capabilities,
  pdp,
  type AgentsLegend,
  type AgentSummary,
  type CapabilityLabel,
  type EffectivePermissions,
} from "@/lib/api/client";
import { DECISION_MEANING, reasonText } from "@/lib/pdp";

export const dynamic = "force-dynamic";

const CERT_DENY = new Set(["cert_revoked", "cert_suspended", "cert_expired", "no_certification"]);
const EMPTY_LEGEND: AgentsLegend = { floor: "L1", levels: [], flags: [] };

const OUTCOMES = ["allow", "deny", "step_up_approval_required", "downgrade_and_retry"];

export default async function PolicyPage() {
  let agents: AgentSummary[] = [];
  let effective: EffectivePermissions[] = [];
  let caps: CapabilityLabel[] = [];
  let legend: AgentsLegend = EMPTY_LEGEND;
  let error: string | null = null;

  try {
    const [agentList, capCatalog, ladder] = await Promise.all([
      api.agents({ page_size: 200 }),
      capabilities.labels().catch(() => ({ capabilities: {} })),
      api.agentsLegend().catch(() => EMPTY_LEGEND),
    ]);
    agents = agentList.items;
    caps = Object.values(capCatalog.capabilities);
    legend = ladder;
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

  const nameByVillage = new Map(agents.map((a) => [a.villageAgentId, a.name]));
  const levelMeaning = new Map(legend.levels.map((l) => [l.level, l.meaning]));

  // Framing: the dominant agent whose actions are mostly denied because of inactive certs.
  let framing: { agent: string; denyCert: number; total: number } | null = null;
  for (const ep of effective) {
    const denyCert = ep.permissions.filter(
      (p) => p.decision === "deny" && CERT_DENY.has(p.reason_code),
    ).length;
    if (denyCert > 0 && (!framing || denyCert > framing.denyCert))
      framing = { agent: ep.subject_agent_id, denyCert, total: ep.permissions.length };
  }
  const showFraming = framing && framing.denyCert >= framing.total * 0.5;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex items-start justify-between">
        <h1 className="text-3xl">Policy &amp; Enforcement</h1>
        <PageMeta />
      </div>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        The PDP resolves each action against the agent&apos;s certs, autonomy level, and safe-mode —
        returning allow / deny / step-up / downgrade. This is the enforcement layer: it is what
        actually stops an uncertified agent from acting. PEPs cache decisions and invalidate on
        revocation (ADR-0024).
      </p>

      {error ? (
        <div className="mb-8 rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load policy data: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          {showFraming && framing && (
            <div className="mb-6 rounded-xl border border-info/40 bg-info/10 p-4 text-sm">
              <h2 className="mb-1 font-semibold text-info">Why you&apos;re seeing a wall of “Deny”</h2>
              <p className="text-ink-100">
                The policy engine is correctly denying these actions because{" "}
                <strong>{nameByVillage.get(framing.agent) ?? framing.agent}</strong>&apos;s
                certificates are revoked or suspended. This is enforcement working as intended — an
                agent cannot perform a capability it isn&apos;t actively certified for. To grant
                access, the underlying certifications must be active. Nothing is broken here; the
                safety layer is doing its job (though the agent currently can&apos;t act).
              </p>
            </div>
          )}

          <div className="mb-8">
            <PdpDecisionExplorer agents={agents} caps={caps} />
          </div>

          <section className="mb-8 rounded-lg border border-ink-500 bg-ink-800 p-4">
            <h2 className="mb-2 text-sm font-semibold text-ink-200">What the four outcomes mean</h2>
            <div className="grid gap-2 sm:grid-cols-2">
              {OUTCOMES.map((o) => (
                <div key={o} className="flex items-start gap-2 text-xs">
                  <DecisionPill decision={o} />
                  <span className="text-ink-300">{DECISION_MEANING[o]}</span>
                </div>
              ))}
            </div>
          </section>

          <h2 className="mb-4 text-xl">Effective permissions</h2>
          {effective.length === 0 ? (
            <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
              No agents hold certs yet — the PDP denies every action until a cert is issued.
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {effective.map((ep) => {
                const denied = ep.permissions.filter((p) => p.decision === "deny");
                const denyCert = denied.filter((p) => CERT_DENY.has(p.reason_code));
                return (
                  <div
                    key={ep.subject_agent_id}
                    className="overflow-hidden rounded-xl border border-ink-500"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 bg-ink-800 px-4 py-3">
                      <span className="text-sm text-ink-50">
                        {nameByVillage.get(ep.subject_agent_id) ?? ep.subject_agent_id}{" "}
                        <span className="font-mono text-xs text-ink-400">
                          {ep.subject_agent_id}
                        </span>
                      </span>
                      <span
                        className="cursor-help rounded bg-ink-600 px-2 py-0.5 text-xs text-ink-100"
                        title={levelMeaning.get(ep.autonomy_level) ?? `Autonomy ${ep.autonomy_level}`}
                      >
                        autonomy {ep.autonomy_level}
                      </span>
                    </div>
                    {denied.length > 0 && (
                      <div className="border-b border-ink-600 bg-ink-900/40 px-4 py-2 text-xs text-ink-300">
                        {denied.length} of {ep.permissions.length} actions are currently{" "}
                        <span className="font-semibold text-danger">DENIED</span> for this agent
                        {denyCert.length === denied.length
                          ? " — all due to inactive certificates."
                          : "."}
                      </div>
                    )}
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-left text-sm">
                        <thead className="sticky top-0 bg-ink-900/60 text-ink-300">
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
                              <td className="px-4 py-2">
                                <div className="text-ink-50">{p.capability_label || p.action}</div>
                                <div className="font-mono text-[10px] text-ink-400">{p.action}</div>
                              </td>
                              <td className="px-4 py-2">
                                <TierPill tier={p.tier} />
                              </td>
                              <td className="px-4 py-2 text-ink-200">{p.cert_status}</td>
                              <td className="px-4 py-2">
                                <span title={DECISION_MEANING[p.decision] ?? p.decision}>
                                  <DecisionPill decision={p.decision} />
                                </span>
                              </td>
                              <td className="px-4 py-2 text-xs text-ink-200" title={p.reason_code}>
                                {reasonText(p.reason_code)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
