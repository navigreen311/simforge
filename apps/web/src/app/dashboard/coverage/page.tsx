import { PageMeta } from "@/components/ui/PageMeta";
import {
  dashboard,
  type CertTimelineEvent,
  type CoverageHeatmap,
  type DeptContextMatrix,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

// Event → color, so the lifecycle timeline reads at a glance.
const EVENT_TONE: Record<string, string> = {
  issued: "bg-success/15 text-success",
  renewed: "bg-success/15 text-success",
  reinstated: "bg-success/15 text-success",
  suspended: "bg-warning/15 text-warning",
  expired: "bg-warning/15 text-warning",
  revoked: "bg-danger/15 text-danger",
  demoted: "bg-danger/15 text-danger",
};

export default async function CoveragePage() {
  let heatmap: CoverageHeatmap | null = null;
  let matrix: DeptContextMatrix | null = null;
  let timeline: CertTimelineEvent[] = [];
  let error: string | null = null;
  try {
    const [h, m, t] = await Promise.all([
      dashboard.coverageHeatmap(),
      dashboard.deptContextMatrix(),
      dashboard.certTimeline(50),
    ]);
    heatmap = h;
    matrix = m;
    timeline = t.events;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load coverage data";
  }

  // Pivot the flat heatmap cells into a role × tier grid, per pack.
  const roles = Array.from(new Set((heatmap?.cells ?? []).map((c) => c.role))).sort();
  const tiers = Array.from(new Set((heatmap?.cells ?? []).map((c) => c.tier))).sort();
  const cellAt = new Map(
    (heatmap?.cells ?? []).map((c) => [`${c.role}::${c.tier}`, c] as const),
  );

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Coverage &amp; Lifecycle</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        Where certification effort is — and isn&apos;t — concentrated. The heatmap shows how many
        scenarios exercise each agent role at each tier; the department matrix shows composite
        (department × forge-context) certifications; the timeline is the raw certification lifecycle
        ledger. Thin cells are honest gaps, not hidden (§10.4).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load coverage data: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          {/* Coverage heatmap — role × tier. */}
          <section className="mb-10">
            <h2 className="mb-1 text-lg">Scenario coverage — role × tier</h2>
            <p className="mb-3 text-xs text-ink-400">
              A cell counts scenarios testing that role at that tier. Cells below the minimum of{" "}
              {heatmap?.min_per_cell ?? 3} are flagged — those role/tier combinations are
              under-tested.
            </p>
            {roles.length === 0 ? (
              <EmptyNote>
                No scenarios ingested yet. Import a pack from the Packs page to populate coverage.
              </EmptyNote>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">Role</th>
                      {tiers.map((t) => (
                        <th key={t} className="px-3 py-2 text-center font-medium">
                          {t}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {roles.map((role) => (
                      <tr key={role}>
                        <td className="px-4 py-2 font-mono text-xs text-ink-100">{role}</td>
                        {tiers.map((t) => {
                          const cell = cellAt.get(`${role}::${t}`);
                          const n = cell?.count ?? 0;
                          const tone =
                            n === 0
                              ? "text-ink-600"
                              : cell?.meets_min
                                ? "text-success"
                                : "text-warning";
                          return (
                            <td
                              key={t}
                              className={`px-3 py-2 text-center font-mono ${tone}`}
                              title={
                                n === 0
                                  ? "No scenarios — untested"
                                  : cell?.meets_min
                                    ? "Meets minimum coverage"
                                    : "Below minimum coverage"
                              }
                            >
                              {n === 0 ? "·" : n}
                              {n > 0 && !cell?.meets_min ? " ⚠" : ""}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Department × forge-context matrix. */}
          <section className="mb-10">
            <h2 className="mb-1 text-lg">Department certifications — department × forge-context</h2>
            <p className="mb-3 text-xs text-ink-400">
              A department cert composes its agents&apos; certs for a forge context. The count is how
              many agent certs back it.
            </p>
            {matrix && matrix.cells.length > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">Department</th>
                      <th className="px-4 py-2 font-medium">Forge context</th>
                      <th className="px-4 py-2 font-medium">Tier</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                      <th className="px-4 py-2 text-center font-medium">Backing certs</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {matrix.cells.map((c, i) => (
                      <tr key={`${c.department}-${c.forge_context}-${i}`}>
                        <td className="px-4 py-2 text-ink-50">{c.department}</td>
                        <td className="px-4 py-2 font-mono text-xs text-ink-200">
                          {c.forge_context}
                        </td>
                        <td className="px-4 py-2 text-ink-200">{c.tier}</td>
                        <td className="px-4 py-2">
                          <span
                            className={
                              c.status === "active"
                                ? "text-success"
                                : c.status === "suspended"
                                  ? "text-warning"
                                  : "text-danger"
                            }
                          >
                            {c.status}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-center font-mono text-ink-200">
                          {c.covering_certs}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyNote>
                No department certifications issued yet. They&apos;re minted once enough member agents
                are certified for a forge context.
              </EmptyNote>
            )}
          </section>

          {/* Certification lifecycle timeline. */}
          <section>
            <h2 className="mb-1 text-lg">Certification lifecycle</h2>
            <p className="mb-3 text-xs text-ink-400">
              Every issue / renew / suspend / revoke event, newest first — the audit trail behind the
              matrices above.
            </p>
            {timeline.length > 0 ? (
              <ul className="flex flex-col gap-1 text-sm">
                {timeline.map((e, i) => (
                  <li
                    key={i}
                    className="flex flex-wrap items-center gap-3 rounded-lg border border-ink-600 bg-ink-800 px-3 py-2"
                  >
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-semibold ${
                        EVENT_TONE[e.event] ?? "bg-ink-600 text-ink-100"
                      }`}
                    >
                      {e.event}
                    </span>
                    <span className="font-mono text-[10px] text-ink-400">
                      {e.agent_cert_id ? `agent:${e.agent_cert_id}` : `dept:${e.dept_cert_id}`}
                    </span>
                    <span className="text-ink-200">by {e.actor}</span>
                    {e.reason && <span className="text-ink-400">— {e.reason}</span>}
                    <span className="ml-auto text-xs text-ink-500">
                      {e.timestamp ? new Date(e.timestamp).toLocaleString() : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyNote>
                No lifecycle events recorded yet. They accrue as certs are issued and change state.
              </EmptyNote>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function EmptyNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
      {children}
    </div>
  );
}
