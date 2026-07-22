import {
  api,
  jurisdictions as jx,
  type CoverageReport,
  type Jurisdiction,
  type PackSummary,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

type PackCoverage = { pack: PackSummary; report: (CoverageReport & { pack_id: string }) | null };

export default async function JurisdictionsPage() {
  let jxList: Jurisdiction[] = [];
  let coverage: PackCoverage[] = [];
  let error: string | null = null;

  try {
    const [jr, packList] = await Promise.all([jx.list(), api.packs()]);
    jxList = jr.jurisdictions;
    coverage = await Promise.all(
      packList.items.map(async (pack) => {
        try {
          return { pack, report: await jx.packCoverage(pack.packId) };
        } catch {
          return { pack, report: null };
        }
      }),
    );
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load jurisdictions";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Jurisdiction Engine</h1>
      <p className="mb-8 text-ink-200">
        Regulatory requirements per jurisdiction, and each pack&apos;s compliance coverage. Missing
        flags fail pack validation (ADR-0019/0021).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load jurisdictions: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          <section className="mb-10">
            <h2 className="mb-4 text-xl">Pack coverage</h2>
            <div className="flex flex-col gap-2">
              {coverage.map(({ pack, report }) => (
                <div
                  key={pack.packId}
                  className="flex flex-wrap items-center gap-3 rounded-lg border border-ink-500 bg-ink-800 px-4 py-3 text-sm"
                >
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      report?.satisfied ? "bg-success" : "bg-danger"
                    }`}
                    aria-hidden
                  />
                  <span className="font-medium text-ink-50">{pack.name}</span>
                  <span className="font-mono text-xs text-ink-300">{pack.packId}</span>
                  {pack.phiRequired && (
                    <span className="rounded bg-info/15 px-2 py-0.5 text-xs text-info">PHI</span>
                  )}
                  <span className="ml-auto flex flex-wrap gap-1">
                    {(report?.jurisdictions ?? []).map((code) => (
                      <span
                        key={code}
                        className="rounded bg-ink-600 px-2 py-0.5 font-mono text-xs text-ink-100"
                      >
                        {code}
                      </span>
                    ))}
                  </span>
                  {report && report.missing_flags.length > 0 ? (
                    <span className="w-full text-xs text-danger">
                      Missing: {report.missing_flags.join(", ")}
                    </span>
                  ) : report ? (
                    <span className="w-full text-xs text-success">
                      Satisfied · {report.present_flags.length} flags declared
                    </span>
                  ) : (
                    <span className="w-full text-xs text-ink-400">coverage unavailable</span>
                  )}
                </div>
              ))}
              {coverage.length === 0 && (
                <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
                  No packs registered.
                </div>
              )}
            </div>
          </section>

          <section>
            <h2 className="mb-4 text-xl">Jurisdiction catalog</h2>
            <div className="overflow-x-auto rounded-xl border border-ink-500">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ink-800 text-ink-200">
                  <tr>
                    <th className="px-4 py-3 font-medium">Code</th>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Level</th>
                    <th className="px-4 py-3 font-medium">Regulators</th>
                    <th className="px-4 py-3 font-medium">Required flags</th>
                    <th className="px-4 py-3 font-medium">PHI-gated flags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-600">
                  {jxList.map((j) => (
                    <tr key={j.code} className="hover:bg-ink-800/60">
                      <td className="px-4 py-3 font-mono text-xs text-gold-400">{j.code}</td>
                      <td className="px-4 py-3 text-ink-50">{j.name}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded px-2 py-0.5 text-xs ${
                            j.level === "federal"
                              ? "bg-gold-600/20 text-gold-300"
                              : "bg-ink-600 text-ink-100"
                          }`}
                        >
                          {j.level}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-200">
                        {j.regulators.join(", ") || "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-100">
                        {j.required_flags.join(", ") || "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-300">
                        {j.phi_flags.join(", ") || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
