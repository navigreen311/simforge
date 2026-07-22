import { DriftScanButton } from "@/components/drift/DriftScanButton";
import { drift, type DriftReport } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function DriftPage() {
  let report: DriftReport | null = null;
  let error: string | null = null;

  try {
    report = await drift.status();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load drift status";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Drift Canary</h1>
        <DriftScanButton />
      </div>
      <p className="mb-8 text-ink-200">
        Each cert pins the exact Forge version its battery ran against. When a Forge upgrades, the
        pinned evidence is stale — the canary auto-suspends drifted certs (ADR-0017). The view below
        is a dry run; the button enforces.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load drift status: <code className="text-danger">{error}</code>
        </div>
      ) : report ? (
        <>
          <div className="mb-8 grid grid-cols-3 gap-4">
            <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="text-sm text-ink-200">Active certs scanned</div>
              <div className="mt-2 font-display text-3xl text-gold-500">{report.scanned}</div>
            </div>
            <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="text-sm text-ink-200">Drifted certs</div>
              <div
                className={`mt-2 font-display text-3xl ${
                  report.drifted_certs > 0 ? "text-danger" : "text-success"
                }`}
              >
                {report.drifted_certs}
              </div>
            </div>
            <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="text-sm text-ink-200">Mode</div>
              <div className="mt-2 font-display text-3xl text-info">
                {report.dry_run ? "Dry run" : "Enforced"}
              </div>
            </div>
          </div>

          {report.findings.length === 0 ? (
            <div className="rounded-lg border border-success/30 bg-success/5 p-6 text-ink-100">
              No drift detected — every active cert&apos;s pinned Forge version matches the Forge&apos;s
              current version.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-ink-500">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ink-800 text-ink-200">
                  <tr>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium">Forge capability</th>
                    <th className="px-4 py-3 font-medium">Pinned</th>
                    <th className="px-4 py-3 font-medium">Current</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-600">
                  {report.findings.map((f) => (
                    <tr key={f.cert_id} className="hover:bg-ink-800/60">
                      <td className="px-4 py-3 font-mono text-xs text-ink-100">
                        {f.agent_village_id}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-gold-400">{f.forge_cap}</td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-200">
                        {f.pinned_version}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-100">
                        {f.current_version ?? "unreachable"}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-semibold ${
                            f.status === "drift"
                              ? "bg-danger/15 text-danger"
                              : "bg-warning/20 text-warning"
                          }`}
                        >
                          {f.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
