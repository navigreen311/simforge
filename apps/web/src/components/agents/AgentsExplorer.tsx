"use client";

import { useRouter } from "next/navigation";

import { AutonomyLadderIndicator } from "@/components/agents/AutonomyLadderIndicator";
import { Column, DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import type { AgentCertRollup, AgentSummary, DepartmentSummary } from "@/lib/api/client";

function relTime(iso: string | null): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  const days = Math.floor((Date.now() - then) / 86_400_000);
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
}: {
  agents: AgentSummary[];
  departments: DepartmentSummary[];
  rollup: AgentCertRollup[];
  total: number;
}) {
  const router = useRouter();
  const deptName = new Map(departments.map((d) => [d.id, d.name]));
  const certByAgent = new Map(rollup.map((r) => [r.agent_village_id, r]));

  const columns: Column<AgentSummary>[] = [
    {
      key: "agent",
      header: "Agent",
      searchText: (a) => `${a.name} ${a.villageAgentId} ${a.role}`,
      sortValue: (a) => a.name,
      cell: (a) => (
        <div>
          <div className="font-medium text-ink-50">{a.name}</div>
          <div className="font-mono text-xs text-ink-300">{a.villageAgentId}</div>
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
      align: "right",
      sortValue: (a) => certByAgent.get(a.villageAgentId)?.active_certs ?? 0,
      cell: (a) => {
        const r = certByAgent.get(a.villageAgentId);
        const active = r?.active_certs ?? 0;
        return (
          <span
            className={`rounded px-2 py-0.5 text-xs ${
              active > 0 ? "bg-success/15 text-success" : "bg-ink-600 text-ink-300"
            }`}
          >
            {active}/{r?.total_certs ?? 0}
          </span>
        );
      },
    },
    {
      key: "autonomy",
      header: "Autonomy",
      sortValue: (a) => a.currentAutonomyLevel,
      filter: {
        label: "Level",
        options: ["L1", "L2", "L3", "L4", "L5"].map((l) => ({ label: l, value: l })),
        match: (a, v) => a.currentAutonomyLevel === v,
      },
      cell: (a) => <AutonomyLadderIndicator level={a.currentAutonomyLevel} />,
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
            <span className="mr-1 rounded bg-gold-600/20 px-2 py-0.5 text-xs text-gold-300">
              Gardner
            </span>
          )}
          {a.level10Enabled && (
            <span className="rounded bg-info/20 px-2 py-0.5 text-xs text-info">L10</span>
          )}
        </>
      ),
    },
    {
      key: "last",
      header: "Last certified",
      sortValue: (a) => certByAgent.get(a.villageAgentId)?.last_certified_at ?? "",
      cell: (a) => (
        <span className="text-xs text-ink-300">
          {relTime(certByAgent.get(a.villageAgentId)?.last_certified_at ?? null)}
        </span>
      ),
    },
  ];

  return (
    <>
      <p className="mb-4 text-xs text-ink-400">
        Showing {agents.length} of {total} tracked agents. Row → this agent&apos;s runs.
      </p>
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
    </>
  );
}
