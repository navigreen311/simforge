import { OperationCertCard } from "@/components/operation/OperationCertCard";
import { StateChip, StateLegend } from "@/components/operation/StateChip";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageMeta } from "@/components/ui/PageMeta";
import {
  operation,
  type AgentCapabilityCerts,
  type DepartmentContextCert,
  type OperationCapacityReport,
  type OperationCertsResponse,
  type OperationCoverageReport,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

// Each section loads independently so one dead endpoint doesn't blank the page
// (the operation endpoints are the assumed Stream-B contract and may not be live).
async function settle<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch {
    return null;
  }
}

export default async function OperationCertsPage() {
  const [certsRes, coverage, capacity, deptRes] = await Promise.all([
    settle(operation.certs()),
    settle(operation.coverage()),
    settle(operation.capacity()),
    settle(operation.deptContext()),
  ]);

  const anyLive = certsRes || coverage || capacity || deptRes;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Operation Certifications</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        Domain certs answer <em>what</em> an agent does; these answer whether it can{" "}
        <strong>operate the Forge software</strong> it does that work in. It is a separate unit with
        its own rubric and its own version stamp. The two are shown{" "}
        <strong>side by side and never merged into one number</strong> — a strong domain score must
        never hide an operation failure. &ldquo;Domain-certified, operation-uncertified&rdquo; is a
        normal, common state, not an error. Every result carries its denominator — always{" "}
        <em>&ldquo;N of M functions in {`{module}`}&rdquo;</em>, never &ldquo;certified on the
        module&rdquo;.
      </p>

      {!anyLive && (
        <div className="mb-6 rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
          The operation-certification endpoints aren&apos;t responding yet. This surface is built to
          the Batch-4 payload contract and the assumed{" "}
          <code className="text-ink-200">/api/operation/…</code> routes (Stream B); it will populate
          once those are live.
        </div>
      )}

      {/* 1 — Side-by-side certs, grouped per agent. */}
      <SideBySideSection data={certsRes} />

      {/* 2 — Coverage (honest denominators; thin flagged). */}
      <CoverageSection data={coverage} />

      {/* 3 — Capacity (the three numbers, ownership labelled). */}
      <CapacitySection data={capacity} />

      {/* 4 — Unit B: department-context certs. */}
      <DeptContextSection data={deptRes} />

      {/* 5 — State legend: the distinct states, once. */}
      <section className="mt-10">
        <StateLegend />
      </section>
    </div>
  );
}

function SectionHeading({ title, blurb }: { title: string; blurb: string }) {
  return (
    <>
      <h2 className="mb-1 text-lg">{title}</h2>
      <p className="mb-4 max-w-4xl text-xs text-ink-400">{blurb}</p>
    </>
  );
}

// ---------------------------------------------------------------------------
// 1 — Side-by-side certs, grouped per agent (per-agent operation view, item 6).
// ---------------------------------------------------------------------------
function SideBySideSection({ data }: { data: OperationCertsResponse | null }) {
  if (!data) return null;

  // Group by agent so each agent's modules (certified / stale / never) read
  // together, under the version stamps carried on each record.
  const byAgent = new Map<string, { name: string; rows: AgentCapabilityCerts[] }>();
  for (const row of data.items) {
    const entry = byAgent.get(row.agent_village_id) ?? { name: row.agent_name, rows: [] };
    entry.rows.push(row);
    byAgent.set(row.agent_village_id, entry);
  }

  return (
    <section className="mb-12">
      <SectionHeading
        title="Domain + operation certs, side by side"
        blurb="Two records per capability — each with its own denominator and its own version stamp. They are never averaged or rolled into a single agent score."
      />
      <div className="mb-4 flex flex-wrap gap-x-6 gap-y-1 rounded-lg border border-ink-500 bg-ink-800 px-4 py-2 text-xs text-ink-300">
        <span>
          domain rubric:{" "}
          <span className="font-mono text-gold-400">{data.domain_rubric_version}</span>
        </span>
        <span>
          operation rubric:{" "}
          <span className="font-mono text-gold-400">{data.operation_rubric_version}</span>
        </span>
        <span className="text-ink-500">two stamps — a change to either re-certs its own unit only</span>
      </div>

      {byAgent.size === 0 ? (
        <EmptyState
          title="No operation certifications yet"
          description="Once The Office submits a Forge operation curriculum and agents run the operation scenarios, their certs appear here alongside their domain certs."
        />
      ) : (
        <div className="flex flex-col gap-8">
          {Array.from(byAgent.entries()).map(([agentId, { name, rows }]) => (
            <div key={agentId}>
              <div className="mb-2 flex items-baseline gap-2">
                <h3 className="text-base text-ink-50">{name}</h3>
                <span className="font-mono text-xs text-ink-400">{agentId}</span>
                <span className="text-xs text-ink-500">
                  · {rows.length} {rows.length === 1 ? "capability" : "capabilities"}
                </span>
              </div>
              <div className="flex flex-col gap-4">
                {rows.map((row) => (
                  <OperationCertCard key={`${agentId}-${row.module_id}`} row={row} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// 2 — Coverage. modules_covered/modules_in_forge + functions_covered/in_module.
// ---------------------------------------------------------------------------
function CoverageSection({ data }: { data: OperationCoverageReport | null }) {
  if (!data) return null;
  return (
    <section className="mb-12">
      <SectionHeading
        title="Operation coverage"
        blurb="Module-level coverage — distinct from the per-agent denominator on each card above. 'Best single-agent' is the most any one agent has certified (a lower bound on the module's union), NOT the module's own coverage and NOT one agent's number. Thin coverage is flagged, not hidden."
      />
      {data.forges.length === 0 ? (
        <EmptyState
          title="No coverage declared"
          description="Coverage populates from the curriculum's coverage_declaration once a Forge operation curriculum is submitted."
        />
      ) : (
        <div className="flex flex-col gap-6">
          {data.forges.map((forge) => (
            <div key={forge.forge_id} className="rounded-xl border border-ink-500 bg-ink-800">
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ink-600 px-5 py-3">
                <div>
                  <span className="text-base text-ink-50">{forge.forge_label}</span>
                  <span className="ml-2 text-sm text-ink-300">
                    <span className="font-mono text-gold-400">
                      {forge.modules_covered} of {forge.modules_in_forge}
                    </span>{" "}
                    modules covered
                  </span>
                </div>
                <span className="font-mono text-[10px] text-ink-400">
                  operation rubric {forge.operation_rubric_version}
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-900/40 text-ink-200">
                    <tr>
                      <th className="px-5 py-2 font-medium">Module</th>
                      <th className="px-4 py-2 font-medium">Functions in module</th>
                      <th className="px-4 py-2 font-medium">Certified agents</th>
                      <th className="px-4 py-2 font-medium">
                        Best single-agent
                        <div className="text-[10px] font-normal text-ink-500">union lower bound</div>
                      </th>
                      <th className="px-4 py-2 font-medium">Coverage</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {forge.modules.map((m) => (
                      <tr key={m.module_id}>
                        <td className="px-5 py-2">
                          <span className="text-ink-100">{m.module_label}</span>
                          <span className="ml-2 font-mono text-[10px] text-ink-500">
                            {m.module_id}
                          </span>
                        </td>
                        <td className="px-4 py-2 font-mono text-gold-400">
                          {m.functions_in_module}
                        </td>
                        <td className="px-4 py-2 font-mono text-ink-100">{m.certified_agents}</td>
                        <td className="px-4 py-2 font-mono text-ink-200">
                          {m.best_single_agent_functions} of {m.functions_in_module}
                        </td>
                        <td className="px-4 py-2">
                          {m.thin ? (
                            <span className="rounded bg-warning/15 px-2 py-0.5 text-xs font-semibold text-warning">
                              ⚠ thin coverage
                            </span>
                          ) : (
                            <span className="text-xs text-success">adequate</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {forge.modules_uncovered.length > 0 && (
                <div className="border-t border-ink-600 px-5 py-2 text-xs text-ink-400">
                  <span className="text-ink-300">Uncovered modules (named, not hidden):</span>{" "}
                  <span className="font-mono text-ink-200">
                    {forge.modules_uncovered.join(", ")}
                  </span>
                </div>
              )}
            </div>
          ))}
          <p className="rounded-lg border border-ink-600 bg-ink-900/40 px-4 py-2 text-xs text-ink-400">
            {data.coverage_note}
          </p>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// 3 — Capacity. The three §8 numbers, with ownership labelled.
// ---------------------------------------------------------------------------
function CapacitySection({ data }: { data: OperationCapacityReport | null }) {
  if (!data) return null;
  return (
    <section className="mb-12">
      <SectionHeading
        title="Operation capacity"
        blurb="How many agents can drive each module. SimForge owns 'produced-but-not-certified' (never_certified + in_training + provisional). A provisional cert passed the bar but is WITHHELD — it is NOT in the certified·free pool. The certified pools are The Office's allocator concern — labelled Office-owned."
      />

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <CapacityTotal
          label="Certified · free"
          value={data.totals.certified_free}
          owner="Office-owned (allocator)"
        />
        <CapacityTotal
          label="Certified · allocated"
          value={data.totals.certified_allocated}
          owner="Office-owned"
        />
        <CapacityTotal
          label="Produced · not certified"
          value={data.totals.produced_not_certified}
          owner="SimForge-owned"
          simforge
        />
      </div>

      {data.modules.length === 0 ? (
        <EmptyState
          title="No capacity to report"
          description="Capacity accrues as agents are produced into departments and earn (or don't yet earn) operation certs per module."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-2 font-medium">Module</th>
                <th className="px-3 py-2 text-center font-medium">
                  Certified · free
                  <div className="text-[10px] font-normal text-ink-500">Office</div>
                </th>
                <th className="px-3 py-2 text-center font-medium">
                  Certified · allocated
                  <div className="text-[10px] font-normal text-ink-500">Office</div>
                </th>
                <th className="px-3 py-2 text-center font-medium">
                  Produced · not certified
                  <div className="text-[10px] font-normal text-ink-500">SimForge</div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {data.modules.map((m) => (
                <tr key={`${m.forge_label}-${m.module_id}`}>
                  <td className="px-4 py-2">
                    <span className="text-ink-100">{m.module_label}</span>
                    <span className="ml-2 text-[10px] text-ink-500">{m.forge_label}</span>
                  </td>
                  <td className="px-3 py-2 text-center font-mono text-success">
                    {m.certified_free}
                  </td>
                  <td className="px-3 py-2 text-center font-mono text-ink-200">
                    {m.certified_allocated}
                  </td>
                  <td className="px-3 py-2 text-center font-mono text-info">
                    {m.produced_not_certified}
                    <div className="text-[10px] text-ink-500">
                      {m.never_certified} never · {m.in_training} training ·{" "}
                      <span className="text-accent">{m.provisional} provisional</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function CapacityTotal({
  label,
  value,
  owner,
  simforge,
}: {
  label: string;
  value: number;
  owner: string;
  simforge?: boolean;
}) {
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-4">
      <div className="text-sm text-ink-200">{label}</div>
      <div className={`mt-1 font-display text-3xl ${simforge ? "text-info" : "text-gold-500"}`}>
        {value}
      </div>
      <div className="mt-1 text-[10px] uppercase tracking-wider text-ink-400">{owner}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4 — Unit B: department-context certs.
// ---------------------------------------------------------------------------
function DeptContextSection({
  data,
}: {
  data: { items: DepartmentContextCert[]; total: number } | null;
}) {
  if (!data) return null;
  return (
    <section className="mb-12">
      <SectionHeading
        title="Department-context certs (Unit B)"
        blurb="A department is cleared for a Forge in a venture's context. Necessary but not sufficient — an agent also needs its own Unit-A cert to be assignable. Competence without context is not clearance."
      />
      {data.items.length === 0 ? (
        <EmptyState
          title="No department-context certs yet"
          description="Unit-B certs are issued once a department's escalation path and compliance coupling are verified for a Forge context."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-2 font-medium">Department</th>
                <th className="px-4 py-2 font-medium">Forge · context</th>
                <th className="px-4 py-2 font-medium">Venture</th>
                <th className="px-4 py-2 font-medium">State</th>
                <th className="px-3 py-2 text-center font-medium">Escalation path</th>
                <th className="px-3 py-2 text-center font-medium">Compliance coupling</th>
                <th className="px-4 py-2 font-medium">Operation rubric</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {data.items.map((d, i) => (
                <tr key={`${d.department_key}-${d.forge_context}-${i}`}>
                  <td className="px-4 py-2 text-ink-50">{d.department_key}</td>
                  <td className="px-4 py-2">
                    <span className="text-ink-100">{d.forge_label}</span>
                    <span className="ml-1 font-mono text-[10px] text-ink-400">
                      {d.forge_context}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-ink-200">{d.venture_context}</td>
                  <td className="px-4 py-2">
                    <StateChip state={d.state} />
                  </td>
                  <td className="px-3 py-2 text-center">
                    <VerifiedBool ok={d.escalation_path_verified} />
                  </td>
                  <td className="px-3 py-2 text-center">
                    <VerifiedBool ok={d.compliance_coupling_verified} />
                  </td>
                  <td className="px-4 py-2 font-mono text-[10px] text-ink-400">
                    {d.operation_rubric_version}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function VerifiedBool({ ok }: { ok: boolean }) {
  return ok ? (
    <span className="text-success">✓ verified</span>
  ) : (
    <span className="text-warning">not verified</span>
  );
}
