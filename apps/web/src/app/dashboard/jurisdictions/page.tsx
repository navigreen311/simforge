import { PageMeta } from "@/components/ui/PageMeta";
import { VerifiedState, type Verdict } from "@/components/ui/VerifiedState";
import {
  api,
  jurisdictions as jx,
  type CoverageReport,
  type Jurisdiction,
  type PackSummary,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

type PackCoverage = { pack: PackSummary; report: (CoverageReport & { pack_id: string }) | null };

function coverageVerdict(r: CoverageReport | null): Verdict {
  if (!r) return "indeterminate";
  if (r.required_flags.length === 0) return "indeterminate"; // vacuous — no requirements to satisfy
  return r.missing_flags.length > 0 ? "fail" : "pass";
}

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
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Jurisdiction Engine</h1>
        <PageMeta />
      </div>
      <p className="mb-6 text-ink-200">
        Regulatory requirements per jurisdiction, and each pack&apos;s compliance coverage. A pack
        that declares zero flags where zero are required is <strong>inconclusive</strong>, not a
        compliance pass (ADR-0019/0021).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load jurisdictions: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          <section className="mb-10">
            <h2 className="mb-4 text-xl">Pack coverage — satisfaction proof</h2>
            <div className="flex flex-col gap-3">
              {coverage.map(({ pack, report }) => {
                const verdict = coverageVerdict(report);
                return (
                  <div key={pack.packId}>
                    <VerifiedState
                      verdict={verdict}
                      checked={report ? report.required_flags.length : 0}
                      passText={`${pack.name}: satisfies all ${report?.required_flags.length ?? 0} required flags across [${report?.jurisdictions.join(", ")}].`}
                      failText={`${pack.name}: missing ${report?.missing_flags.length ?? 0} required flag(s): ${report?.missing_flags.join(", ")}.`}
                    >
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="font-mono text-ink-300">{pack.packId}</span>
                        {pack.phiRequired && (
                          <span className="rounded bg-info/15 px-2 py-0.5 text-info">PHI</span>
                        )}
                        {report && report.required_flags.length === 0 && (
                          <span className="text-ink-300">
                            No requirements defined for [{report.jurisdictions.join(", ")}] — not a
                            compliance pass.
                          </span>
                        )}
                      </div>
                      {report && report.required_flags.length > 0 && (
                        <table className="mt-2 w-full text-left text-xs">
                          <thead className="text-ink-400">
                            <tr>
                              <th className="py-1 font-normal">Required flag</th>
                              <th className="py-1 font-normal">Declared?</th>
                            </tr>
                          </thead>
                          <tbody>
                            {report.required_flags.map((f) => {
                              const declared = report.present_flags.includes(f);
                              return (
                                <tr key={f}>
                                  <td className="py-0.5 font-mono text-ink-100">{f}</td>
                                  <td className="py-0.5">
                                    {declared ? (
                                      <span className="text-success">✓ declared</span>
                                    ) : (
                                      <span className="text-danger">✗ missing</span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      )}
                    </VerifiedState>
                  </div>
                );
              })}
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
                    <th className="px-4 py-3 font-medium">Required</th>
                    <th className="px-4 py-3 font-medium">PHI-gated</th>
                    <th className="px-4 py-3 font-medium">Effective</th>
                    <th className="px-4 py-3 font-medium">Citation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-600">
                  {jxList.map((j) => (
                    <tr key={j.code} className="hover:bg-ink-800/60">
                      <td className="px-4 py-3 font-mono text-xs text-gold-400">{j.code}</td>
                      <td className="px-4 py-3 text-ink-50">{j.name}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded px-2 py-0.5 text-xs ${j.level === "federal" ? "bg-gold-600/20 text-gold-300" : "bg-ink-600 text-ink-100"}`}>
                          {j.level}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-200">{j.regulators.join(", ") || "—"}</td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-100">{j.required_flags.join(", ") || "—"}</td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-300">{j.phi_flags.join(", ") || "—"}</td>
                      <td className="px-4 py-3 text-xs text-ink-300">{j.effective_date ?? "—"}</td>
                      <td className="px-4 py-3 text-[11px] text-ink-400">{j.source_citation ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-ink-400">
              UT/ID added for Greenstone Phase-1 coverage visibility; their real regulatory
              requirements are a v2 workstream (currently no required flags).
            </p>
          </section>
        </>
      )}
    </div>
  );
}
