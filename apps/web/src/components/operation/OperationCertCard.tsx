import type { AgentCapabilityCerts, AgentOperationCert } from "@/lib/api/client";
import {
  dimensionLabel,
  isSpreadCollapsed,
  OPERATION_STATE_META,
  scenarioClassLabel,
  trustTierLabel,
  verdictMeta,
} from "@/lib/operation";
import { StateChip } from "@/components/operation/StateChip";

// One agent × capability, showing BOTH certifications side by side (spec Batch 6,
// item 3). Two records, each with its OWN denominator and its OWN version stamp.
// They are NEVER averaged or merged into one number — a strong domain score must
// never mask an operation failure. "Domain-certified, operation-uncertified" is a
// normal, common state and is rendered calmly, not as an error.
export function OperationCertCard({ row }: { row: AgentCapabilityCerts }) {
  return (
    <article className="rounded-xl border border-ink-500 bg-ink-800">
      {/* Header — the capability, in plain language, with the raw id small. */}
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ink-600 px-5 py-3">
        <div>
          <span className="text-base text-ink-50">{row.capability_label}</span>
          <span className="ml-2 font-mono text-xs text-ink-400">
            {row.forge_label} · {row.module_id}
          </span>
        </div>
        <span className="text-xs text-ink-200">{row.agent_name}</span>
      </div>

      <p className="px-5 pt-3 text-xs text-ink-400">
        Two certifications, measured on different scales and{" "}
        <strong className="text-ink-200">never merged into one number</strong>.
      </p>

      {/* The two records, literally side by side. */}
      <div className="grid gap-4 p-5 md:grid-cols-2">
        <DomainPanel domain={row.domain} />
        <OperationPanel op={row.operation} moduleId={row.module_id} />
      </div>
    </article>
  );
}

function Panel({
  title,
  versionStamp,
  children,
}: {
  title: string;
  versionStamp: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-ink-600 bg-ink-900/40 p-4">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-300">{title}</h4>
        {versionStamp}
      </div>
      {children}
    </section>
  );
}

function VersionBadge({ label, version }: { label: string; version: string | null }) {
  return (
    <span className="rounded bg-ink-700 px-1.5 py-0.5 font-mono text-[10px] text-ink-200">
      {label} {version ?? "—"}
    </span>
  );
}

// Record 1 — DOMAIN cert. Its own denominator (rubric dimensions) + its own
// version stamp (domain rubric_version). Independent of the operation record.
function DomainPanel({ domain }: { domain: AgentCapabilityCerts["domain"] }) {
  return (
    <Panel
      title="Domain certification"
      versionStamp={<VersionBadge label="domain rubric" version={domain.rubric_version} />}
    >
      {domain.present ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded px-2 py-0.5 text-xs font-semibold ${
                domain.state === "certified"
                  ? "bg-success/15 text-success"
                  : domain.state === "revoked"
                    ? "bg-danger/15 text-danger"
                    : "bg-warning/15 text-warning"
              }`}
            >
              {domain.state ?? "—"}
            </span>
            {domain.tier && <span className="text-xs text-ink-300">tier: {domain.tier}</span>}
          </div>
          <div className="text-sm text-ink-100">
            {domain.dimensions_passed != null && domain.dimensions_total != null ? (
              <>
                <span className="font-mono text-gold-400">
                  {domain.dimensions_passed} of {domain.dimensions_total}
                </span>{" "}
                domain dimensions passed
              </>
            ) : (
              <span className="text-ink-400">denominator unavailable</span>
            )}
          </div>
          {domain.expires_at && (
            <div className="text-xs text-ink-400">
              expires {new Date(domain.expires_at).toLocaleDateString()}
            </div>
          )}
        </>
      ) : (
        <div className="text-sm text-ink-300">No domain certification on record.</div>
      )}
    </Panel>
  );
}

// Record 2 — OPERATION cert. Its own denominator (module functions) + its own
// version stamp (operation_rubric_version). Named-list dimensions, per-scenario
// verdicts, collapse warning, failure modes. Absent = calm "not certified" note.
function OperationPanel({
  op,
  moduleId,
}: {
  op: AgentOperationCert | null;
  moduleId: string;
}) {
  if (!op) {
    // Domain-certified, operation-uncertified is NORMAL — render calmly, not red.
    return (
      <Panel
        title="Operation certification"
        versionStamp={<VersionBadge label="operation rubric" version={null} />}
      >
        <div className="flex flex-wrap items-center gap-2">
          <StateChip state="never_certified" />
        </div>
        <p className="text-sm text-ink-300">
          No operation certification for this module yet. This is a normal state — the agent is
          not cleared for shifts requiring <span className="font-mono text-ink-200">{moduleId}</span>{" "}
          until it earns one. It is <strong>not</strong> an error and does not reflect on the
          domain cert.
        </p>
      </Panel>
    );
  }

  const numericDims = op.operation_rubric_results.filter(
    (r) => r.verdict === "PASS" || r.verdict === "FAIL",
  ).length;
  const collapsed = isSpreadCollapsed(op.state, op.rubric_dimension_spread, numericDims);

  return (
    <Panel
      title="Operation certification"
      versionStamp={
        <VersionBadge label="operation rubric" version={op.operation_rubric_version} />
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <StateChip state={op.state} />
        <span className="text-xs text-ink-300">
          trust tier: {trustTierLabel(op.max_certified_trust_tier)}
        </span>
      </div>

      {/* DENOMINATOR — always "N of M functions in {module}", never bare. */}
      <div className="text-sm text-ink-100">
        <span className="font-mono text-gold-400">
          {op.functions_certified} of {op.functions_in_module}
        </span>{" "}
        functions in <span className="font-mono text-ink-200">{op.module_id}</span>
      </div>

      {/* Low-information collapse warning beside the PASS (non-blocking). */}
      {collapsed && (
        <div className="rounded border border-warning/40 bg-warning/10 px-2 py-1 text-[11px] text-warning">
          ⚠ Low-information PASS — rubric dimensions collapsed (spread{" "}
          <span className="font-mono">{op.rubric_dimension_spread?.toFixed(3)}</span>). The five
          dimensions returned near-identical results, so this may be measuring one thing five
          times. Advisory only; does not change the verdict.
        </div>
      )}

      {/* Named-list dimensions — NOT fixed columns. */}
      {op.operation_rubric_results.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wider text-ink-400">
            Rubric dimensions
          </div>
          <ul className="flex flex-col gap-1">
            {op.operation_rubric_results.map((r) => (
              <li key={r.dimension} className="flex items-center justify-between gap-2 text-xs">
                <span className="text-ink-200">{dimensionLabel(r.dimension)}</span>
                <span className="flex items-center gap-2">
                  {r.score != null && (
                    <span className="font-mono text-[10px] text-ink-400">
                      {r.score.toFixed(2)}
                      {r.threshold != null ? ` / ${r.threshold.toFixed(2)}` : ""}
                    </span>
                  )}
                  <span
                    className={`rounded px-1.5 py-0.5 font-semibold ${verdictMeta(r.verdict).chip}`}
                  >
                    {verdictMeta(r.verdict).label}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Per-scenario-class results. */}
      {op.per_scenario_class_results.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {op.per_scenario_class_results.map((s) => (
            <span
              key={s.scenario_class}
              className={`rounded px-1.5 py-0.5 text-[10px] ${verdictMeta(s.verdict).chip}`}
              title={`${scenarioClassLabel(s.scenario_class)}: ${verdictMeta(s.verdict).label}`}
            >
              {scenarioClassLabel(s.scenario_class)}
            </span>
          ))}
        </div>
      )}

      {op.failure_modes_observed.length > 0 && (
        <div className="text-[11px] text-ink-400">
          <span className="text-ink-300">Failure modes observed:</span>{" "}
          {op.failure_modes_observed.join(", ")}
        </div>
      )}

      {/* What it was earned under — the re-cert triggers. */}
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[10px] text-ink-500">
        <span>instr {op.instruction_version}</span>
        <span>forge-api {op.forge_api_version}</span>
        <span title={op.instruction_content_hash}>
          hash {op.instruction_content_hash.slice(0, 10)}
        </span>
        {op.expires_at && <span>expires {new Date(op.expires_at).toLocaleDateString()}</span>}
      </div>
    </Panel>
  );
}
