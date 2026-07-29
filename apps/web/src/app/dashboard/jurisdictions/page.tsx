import { PageMeta } from "@/components/ui/PageMeta";
import { VerifiedState, type Verdict } from "@/components/ui/VerifiedState";
import {
  api,
  jurisdictions as jx,
  type CoverageReport,
  type FlagCatalog,
  type Jurisdiction,
  type PackSummary,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

const EMPTY_CATALOG: FlagCatalog = { flags: {}, legend: {} };

type PackCoverage = { pack: PackSummary; report: (CoverageReport & { pack_id: string }) | null };

function coverageVerdict(r: CoverageReport | null): Verdict {
  if (!r) return "indeterminate";
  if (r.required_flags.length === 0) return "indeterminate"; // vacuous — no requirements to satisfy
  return r.missing_flags.length > 0 ? "fail" : "pass";
}

// One authoritative flag label, from the shared catalog (/api/packs/flag-catalog → describe_flag).
// Friendly name primary; raw code kept visible (muted) for the engineer.
function FlagChip({ code, catalog }: { code: string; catalog: FlagCatalog }) {
  const info = catalog.flags[code];
  const label = info?.label ?? code;
  const tip = info?.tooltip ?? `Compliance flag '${code}'.`;
  return (
    <span className="inline-flex items-baseline gap-1.5" title={tip}>
      <span className={info?.phi ? "text-info" : "text-ink-100"}>{label}</span>
      <span className="font-mono text-[10px] text-ink-500">{code}</span>
    </span>
  );
}

function FlagList({ codes, catalog }: { codes: string[]; catalog: FlagCatalog }) {
  if (codes.length === 0) {
    return (
      <span className="text-ink-400" title="No flags of this type for this jurisdiction">
        none
      </span>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      {codes.map((c) => (
        <FlagChip key={c} code={c} catalog={catalog} />
      ))}
    </div>
  );
}

// Header cell with an explanatory tooltip (dotted underline cues that it's hoverable).
function Th({ label, tip }: { label: string; tip: string }) {
  return (
    <th className="px-4 py-3 font-medium">
      <span className="cursor-help decoration-ink-500 decoration-dotted underline-offset-4 [text-decoration-line:underline]" title={tip}>
        {label}
      </span>
    </th>
  );
}

export default async function JurisdictionsPage() {
  let jxList: Jurisdiction[] = [];
  let coverage: PackCoverage[] = [];
  let catalog: FlagCatalog = EMPTY_CATALOG;
  let error: string | null = null;

  try {
    const [jr, packList, flagCatalog] = await Promise.all([
      jx.list(),
      api.packs(),
      api.flagCatalog(),
    ]);
    jxList = jr.jurisdictions;
    catalog = flagCatalog;
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
    <div className="mx-auto max-w-7xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Jurisdiction Engine</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
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
                const indeterminate = verdict === "indeterminate";
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
                        {report && (
                          <span className="text-ink-300">
                            Operates in:{" "}
                            {report.jurisdictions.map((c, i) => (
                              <span key={c}>
                                {i > 0 && ", "}
                                <a href={`#jx-${c}`} className="font-mono text-gold-400 hover:underline">
                                  {c}
                                </a>
                              </span>
                            ))}
                          </span>
                        )}
                      </div>

                      {/* STEP 3 — plain-language explanation of the INDETERMINATE case. */}
                      {indeterminate && report && (
                        <p className="mt-2 max-w-3xl rounded border border-ink-600 bg-ink-800/60 p-3 text-xs text-ink-200">
                          {pack.name}&apos;s pack operates in [{report.jurisdictions.join(", ")}],
                          which defines no required compliance flags. Because there&apos;s nothing to
                          check, this can&apos;t be called a pass — it&apos;s inconclusive. This is
                          expected for a pack with no health/employment compliance surface. If it
                          should operate in a state with requirements (e.g. NV/AZ/UT/ID), add that
                          jurisdiction to the pack.
                        </p>
                      )}

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
                                  <td className="py-1">
                                    <FlagChip code={f} catalog={catalog} />
                                  </td>
                                  <td className="py-1">
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
            <h2 className="mb-1 text-xl">Jurisdiction catalog</h2>
            <p className="mb-4 text-xs text-ink-400">
              Hover a column header or a flag for what it means. Flags show their plain name with the
              raw code beneath.
            </p>
            <div className="overflow-x-auto rounded-xl border border-ink-500">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ink-800 text-ink-200">
                  <tr>
                    <Th label="Code" tip="The jurisdiction's ISO-style code." />
                    <Th label="Name" tip="The jurisdiction's name." />
                    <Th label="Level" tip="Which government level sets this requirement (federal or state)." />
                    <Th label="Regulators" tip="The agencies that enforce it." />
                    <Th label="Required" tip="Flags a pack must declare to operate in this jurisdiction." />
                    <Th label="PHI-gated" tip="Flags required only when the pack handles Protected Health Information." />
                    <Th label="Effective" tip="When this requirement took effect." />
                    <Th label="Citation" tip="The statute/regulation it comes from." />
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-600">
                  {jxList.map((j) => (
                    <tr key={j.code} id={`jx-${j.code}`} className="scroll-mt-20 hover:bg-ink-800/60 target:bg-gold-600/10">
                      <td className="px-4 py-3 font-mono text-xs text-gold-400">{j.code}</td>
                      <td className="px-4 py-3 text-ink-50">{j.name}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded px-2 py-0.5 text-xs ${j.level === "federal" ? "bg-gold-600/20 text-gold-300" : "bg-ink-600 text-ink-100"}`}>
                          {j.level}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink-200">{j.regulators.join(", ") || "—"}</td>
                      <td className="px-4 py-3 text-xs">
                        <FlagList codes={j.required_flags} catalog={catalog} />
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <FlagList codes={j.phi_flags} catalog={catalog} />
                      </td>
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
