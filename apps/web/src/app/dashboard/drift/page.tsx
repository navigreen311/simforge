import Link from "next/link";

import { DriftEnforceButton } from "@/components/drift/DriftEnforceButton";
import { PageMeta } from "@/components/ui/PageMeta";
import { VerifiedState, verdictFor } from "@/components/ui/VerifiedState";
import {
  drift,
  type ConstitutionDriftReport,
  type DriftReport,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function DriftPage() {
  let report: DriftReport | null = null;
  let constitution: ConstitutionDriftReport | null = null;
  let error: string | null = null;
  try {
    [report, constitution] = await Promise.all([drift.status(), drift.constitution()]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load drift status";
  }

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Drift Canary</h1>
        <div className="flex items-center gap-3">
          <PageMeta />
          {report && (
            <DriftEnforceButton wouldSuspend={report.findings} activeCerts={report.scanned} />
          )}
        </div>
      </div>
      <p className="mb-6 text-ink-200">
        A cert pins the exact Forge version its battery ran against. When a Forge upgrades, the
        pinned evidence is stale (ADR-0017). A scan of <strong>zero</strong> certs is inconclusive,
        not an all-clear.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load drift status: <code className="text-danger">{error}</code>
        </div>
      ) : report ? (
        <div className="flex flex-col gap-8">
          {/* Forge drift — the audit's Finding 3: 0 scanned must NOT read green. */}
          <section>
            <h2 className="mb-3 text-xl">Forge version drift</h2>
            <VerifiedState
              verdict={verdictFor(report.scanned, report.drifted_certs)}
              checked={report.scanned}
              passText={`No Forge drift across ${report.scanned} active certs.`}
              failText={`${report.drifted_certs} of ${report.scanned} active certs have drifted.`}
            >
              {report.scanned === 0 && (
                <p className="text-xs text-ink-200">
                  0 active certs to scan (all current certs are suspended/revoked). This is why the
                  scan is inconclusive — there is nothing to check, so it cannot be a pass.
                </p>
              )}
            </VerifiedState>
            {report.findings.length > 0 && (
              <div className="mt-3 overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">Agent</th>
                      <th className="px-4 py-2 font-medium">Forge cap</th>
                      <th className="px-4 py-2 font-medium">Pinned</th>
                      <th className="px-4 py-2 font-medium">Current</th>
                      <th className="px-4 py-2 font-medium">Would suspend</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {report.findings.map((f) => (
                      <tr key={f.cert_id}>
                        <td className="px-4 py-2 font-mono text-xs text-ink-100">{f.agent_village_id}</td>
                        <td className="px-4 py-2 font-mono text-xs text-gold-400">{f.forge_cap}</td>
                        <td className="px-4 py-2 font-mono text-xs">{f.pinned_version}</td>
                        <td className="px-4 py-2 font-mono text-xs">{f.current_version ?? "unreachable"}</td>
                        <td className="px-4 py-2">
                          {f.status === "drift" ? (
                            <span className="text-danger">yes</span>
                          ) : (
                            <span className="text-warning">{f.status}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Constitution drift — detection only (Finding 2). */}
          {constitution && (
            <section>
              <div className="mb-3 flex items-center gap-3">
                <h2 className="text-xl">Constitution version drift</h2>
                <span className="rounded bg-info/15 px-2 py-0.5 text-xs text-info">
                  detection only — not yet enforced
                </span>
              </div>
              <VerifiedState
                verdict={constitution.stale_certs > 0 ? "fail" : verdictFor(constitution.scanned, 0)}
                checked={constitution.scanned}
                failText={`${constitution.stale_certs} of ${constitution.scanned} certs are pinned to a superseded constitution (current: ${constitution.current_constitution}).`}
                passText={`All ${constitution.scanned} certs pin the current constitution ${constitution.current_constitution}.`}
              >
                <p className="text-xs text-ink-200">
                  Enforcement (auto-suspend / flag-and-grace / amendment-scoped) is a pending owner
                  policy decision. This surface detects and displays only — it never suspends on
                  constitution drift.
                </p>
              </VerifiedState>

              {/* Advisory next-step (STEP 3) — what to do about the FAIL. Advisory only; no policy. */}
              {constitution.stale_certs > 0 && (
                <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm text-ink-100">
                  <p>
                    All {constitution.stale_certs} certificate
                    {constitution.stale_certs === 1 ? " was" : "s were"} certified against
                    constitution {constitution.findings.find((f) => f.stale)?.pinned_constitution ?? "v1.0.0"},
                    which has been superseded by {constitution.current_constitution}. Until an
                    enforcement policy is chosen, these remain valid but flagged. Deciding the policy
                    (auto-suspend / flag-and-grace / amendment-scoped) is a governance decision —{" "}
                    <Link href="/dashboard/constitution" className="text-gold-400 underline hover:text-gold-300">
                      see the Constitution page
                    </Link>
                    .
                  </p>
                </div>
              )}

              {constitution.findings.length > 0 && (
                <div className="mt-3 overflow-x-auto rounded-xl border border-ink-500">
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-ink-800 text-ink-200">
                      <tr>
                        <th className="px-4 py-2 font-medium">Agent</th>
                        <th className="px-4 py-2 font-medium">Capability</th>
                        <th className="px-4 py-2 font-medium">Cert status</th>
                        <th className="px-4 py-2 font-medium">Pinned constitution</th>
                        <th className="px-4 py-2 font-medium">Current</th>
                        <th className="px-4 py-2 font-medium">Stale</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-600">
                      {constitution.findings.map((f) => {
                        const cap = constitution.cap_labels[f.capability];
                        const agentName = constitution.agent_names[f.agent] ?? f.agent;
                        return (
                          <tr key={f.cert_id} className={f.stale ? "bg-danger/5" : ""}>
                            <td className="px-4 py-2 text-xs text-ink-100">
                              <Link
                                href={`/dashboard/runs?agent=${f.agent}`}
                                title={f.agent}
                                className="hover:text-gold-300 hover:underline"
                              >
                                {agentName}
                              </Link>
                            </td>
                            <td className="px-4 py-2 text-xs text-gold-400" title={f.capability}>
                              <Link
                                href={`/dashboard/lineage?root=urn:gc:village:cert:${f.cert_id}`}
                                className="hover:text-gold-300 hover:underline"
                              >
                                {cap?.label ?? f.capability}
                              </Link>
                            </td>
                            <td className="px-4 py-2 text-xs text-ink-200">{f.cert_status}</td>
                            <td className="px-4 py-2 font-mono text-xs">{f.pinned_constitution ?? "—"}</td>
                            <td className="px-4 py-2 font-mono text-xs">{f.current_constitution ?? "—"}</td>
                            <td className="px-4 py-2">
                              {f.stale ? <span className="text-danger">stale</span> : <span className="text-success">ok</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </div>
      ) : null}
    </div>
  );
}
