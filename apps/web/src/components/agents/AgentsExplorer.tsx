"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AutonomyLadderIndicator } from "@/components/agents/AutonomyLadderIndicator";
import { ScenarioPickerModal } from "@/components/agents/ScenarioPickerModal";
import { Column, DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import type {
  AgentCertRollup,
  AgentsLegend,
  AgentSummary,
  DepartmentSummary,
} from "@/lib/api/client";

function relTime(iso: string | null): string {
  if (!iso) return "never";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

export function AgentsExplorer({
  agents,
  departments,
  rollup,
  total,
  legend,
}: {
  agents: AgentSummary[];
  departments: DepartmentSummary[];
  rollup: AgentCertRollup[];
  total: number;
  legend: AgentsLegend;
}) {
  const router = useRouter();
  const [pickerAgent, setPickerAgent] = useState<AgentSummary | null>(null);
  const deptName = new Map(departments.map((d) => [d.id, d.name]));
  const certByAgent = new Map(rollup.map((r) => [r.agent_village_id, r]));
  const levelMeaning = new Map(legend.levels.map((l) => [l.level, l.meaning]));
  const levelIndex = new Map(legend.levels.map((l) => [l.level, l.index]));
  const floorIndex = levelIndex.get(legend.floor) ?? 1;
  const flagMeaning = new Map(legend.flags.map((f) => [f.key, f.meaning]));

  const rollupFor = (a: AgentSummary) => certByAgent.get(a.villageAgentId);
  const activeOf = (a: AgentSummary) => rollupFor(a)?.active_certs ?? 0;
  const aboveFloor = (a: AgentSummary) => (levelIndex.get(a.currentAutonomyLevel) ?? 1) > floorIndex;
  // Contradiction: authorized above the floor while holding zero active certs.
  const tripsContradiction = (a: AgentSummary) => aboveFloor(a) && activeOf(a) === 0;
  // A level-like flag (L10) that disagrees with the ladder level (e.g. Gardner: L1 + L10).
  const levelMismatch = (a: AgentSummary) => a.level10Enabled && a.currentAutonomyLevel !== "L5";

  const contradictions = agents.filter(tripsContradiction);
  const withActive = agents.filter((a) => activeOf(a) > 0).length;

  const columns: Column<AgentSummary>[] = [
    {
      key: "agent",
      header: "Agent",
      searchText: (a) => `${a.name} ${a.villageAgentId} ${a.role}`,
      sortValue: (a) => a.name,
      cell: (a) => (
        <div className="min-w-[200px]">
          <div className="font-medium text-ink-50">{a.name}</div>
          <div className="font-mono text-xs text-ink-300">{a.villageAgentId}</div>
          <div className="mt-1 flex flex-wrap gap-1">
            {tripsContradiction(a) && (
              <span
                className="rounded bg-danger/20 px-1.5 py-0.5 text-[10px] font-semibold text-danger"
                title={`This agent is authorized at autonomy ${a.currentAutonomyLevel} but holds no active certification. Under the readiness policy, autonomy should not exceed what active certs support. Flagged for review.`}
              >
                ⚠ {a.currentAutonomyLevel} · no active cert
              </span>
            )}
            {levelMismatch(a) && (
              <span
                className="rounded bg-warning/20 px-1.5 py-0.5 text-[10px] font-semibold text-warning"
                title={`This agent carries an 'L10' flag but its ladder level is ${a.currentAutonomyLevel}. The level-like flag and the autonomy ladder disagree.`}
              >
                ⚠ level mismatch
              </span>
            )}
          </div>
        </div>
      ),
    },
    { key: "role", header: "Role", sortValue: (a) => a.role, cell: (a) => a.role },
    {
      key: "dept",
      header: "Department",
      sortValue: (a) => deptName.get(a.departmentId) ?? "",
      filter: {
        label: "Dept",
        options: departments.map((d) => ({ label: d.name, value: d.id })),
        match: (a, v) => a.departmentId === v,
      },
      cell: (a) => (
        <span className="rounded bg-ink-600 px-2 py-0.5 text-xs text-ink-100">
          {deptName.get(a.departmentId) ?? "—"}
        </span>
      ),
    },
    {
      key: "certs",
      header: "Active certs",
      sortValue: (a) => activeOf(a),
      cell: (a) => {
        const r = rollupFor(a);
        const active = r?.active_certs ?? 0;
        const held = r?.total_certs ?? 0;
        if (held === 0) {
          return (
            <span
              className="text-xs italic text-ink-500"
              title="This agent has never been certified for any capability."
            >
              No certifications
            </span>
          );
        }
        if (active === 0) {
          return (
            <span
              className="rounded bg-danger/15 px-2 py-0.5 text-xs font-semibold text-danger"
              title={`This agent holds ${held} certificate${held === 1 ? "" : "s"} but none are currently active (all suspended/revoked/expired).`}
            >
              0 active of {held} held
            </span>
          );
        }
        return (
          <span
            className="rounded bg-success/15 px-2 py-0.5 text-xs text-success"
            title={`${active} of ${held} certificates active.`}
          >
            {active} active of {held} held
          </span>
        );
      },
    },
    {
      key: "autonomy",
      header: "Autonomy",
      sortValue: (a) => levelIndex.get(a.currentAutonomyLevel) ?? 0,
      filter: {
        label: "Level",
        options: legend.levels.map((l) => ({ label: l.level, value: l.level })),
        match: (a, v) => a.currentAutonomyLevel === v,
      },
      cell: (a) => (
        <span
          className={`inline-flex items-center gap-1 ${tripsContradiction(a) ? "rounded px-1 ring-1 ring-danger/40" : ""}`}
          title={levelMeaning.get(a.currentAutonomyLevel) ?? a.currentAutonomyLevel}
        >
          <AutonomyLadderIndicator level={a.currentAutonomyLevel} />
        </span>
      ),
    },
    {
      key: "flags",
      header: "Flags",
      filter: {
        label: "Flag",
        options: [
          { label: "Gardner", value: "gardner" },
          { label: "L10", value: "l10" },
        ],
        match: (a, v) => (v === "gardner" ? a.gardnerFlag : a.level10Enabled),
      },
      cell: (a) => (
        <>
          {a.gardnerFlag && (
            <span
              className="mr-1 cursor-help rounded bg-gold-600/20 px-2 py-0.5 text-xs text-gold-300"
              title={flagMeaning.get("gardner")}
            >
              Gardner
            </span>
          )}
          {a.level10Enabled && (
            <span
              className="cursor-help rounded bg-info/20 px-2 py-0.5 text-xs text-info"
              title={flagMeaning.get("l10")}
            >
              L10
            </span>
          )}
        </>
      ),
    },
    {
      key: "last",
      header: "Last certified",
      align: "right",
      sortValue: (a) => rollupFor(a)?.last_certified_at ?? "",
      cell: (a) => {
        const at = rollupFor(a)?.last_certified_at ?? null;
        if (!at) return <span className="text-xs italic text-ink-500">never</span>;
        return (
          <a
            href="/dashboard/certs"
            onClick={(e) => e.stopPropagation()}
            className="text-xs text-gold-400 hover:underline"
            title="Open the Certification Registry"
          >
            {relTime(at)}
          </a>
        );
      },
    },
    {
      key: "run",
      header: "",
      align: "right",
      cell: (a) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setPickerAgent(a);
          }}
          className="rounded border border-ink-500 px-2 py-1 text-xs text-ink-100 hover:bg-ink-700"
          title="Run a scenario for this agent and watch it execute live"
        >
          ▶ Run
        </button>
      ),
    },
  ];

  return (
    <div>
      <Summary
        total={total}
        withActive={withActive}
        contradictions={contradictions.length}
      />
      <Legend legend={legend} />

      <DataTable
        columns={columns}
        data={agents}
        getRowKey={(a) => a.id}
        onRowClick={(a) => router.push(`/dashboard/runs?agent=${a.villageAgentId}`)}
        searchPlaceholder="Search name / id / role…"
        emptyState={
          <EmptyState
            title="No agents match"
            description="Clear filters or search to see the full roster."
            icon="👥"
          />
        }
      />
      {pickerAgent && (
        <ScenarioPickerModal
          agentVillageId={pickerAgent.villageAgentId}
          agentAutonomy={pickerAgent.currentAutonomyLevel}
          onClose={() => setPickerAgent(null)}
        />
      )}
    </div>
  );
}

function Summary({
  total,
  withActive,
  contradictions,
}: {
  total: number;
  withActive: number;
  contradictions: number;
}) {
  const warn = withActive === 0 || contradictions > 0;
  return (
    <div
      className={`mb-4 rounded-xl border p-4 text-sm ${
        warn ? "border-warning/50 bg-warning/10" : "border-success/40 bg-success/10"
      }`}
    >
      <p className={warn ? "font-semibold text-warning" : "font-semibold text-success"}>
        {withActive} of {total} tracked agent{total === 1 ? "" : "s"} hold any active certification.
      </p>
      <p className="mt-1 text-xs text-ink-200">
        Tracking {total} agent{total === 1 ? "" : "s"}. This may be a partial roster — the full
        Village is larger, and the rest are not yet in SimForge.
      </p>
      {contradictions > 0 && (
        <p className="mt-1 text-xs text-warning">
          {contradictions} agent{contradictions === 1 ? " is" : "s are"} authorized above the floor
          while holding no active certification (see the ⚠ rows). Detection only — nothing is changed.
        </p>
      )}
    </div>
  );
}

function Legend({ legend }: { legend: AgentsLegend }) {
  return (
    <details className="mb-4 rounded-lg border border-ink-500 bg-ink-800 p-3 text-xs">
      <summary className="cursor-pointer font-semibold text-ink-200">
        What the autonomy levels and flags mean
      </summary>
      <div className="mt-2 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-1 font-semibold text-ink-300">Autonomy ladder</div>
          <ul className="flex flex-col gap-1">
            {legend.levels.map((l) => (
              <li key={l.level}>
                <span className="font-mono text-ink-100">{l.level}</span>
                {l.is_floor && <span className="ml-1 text-ink-500">(floor)</span>}
                <span className="text-ink-400"> — {l.meaning}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="mb-1 font-semibold text-ink-300">Flags</div>
          <ul className="flex flex-col gap-1">
            {legend.flags.map((f) => (
              <li key={f.key}>
                <span className="text-ink-100">{f.label}</span>
                {!f.defined && <span className="ml-1 text-warning">(no formal definition)</span>}
                <span className="text-ink-400"> — {f.meaning}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}
