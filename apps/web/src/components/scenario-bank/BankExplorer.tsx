"use client";

import { useRouter } from "next/navigation";

import { Column, DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import type { BankScenario } from "@/lib/api/client";

const TIER_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};

const STATUS_STYLE: Record<string, string> = {
  committed: "bg-success/15 text-success",
  draft: "bg-warning/20 text-warning",
  in_review: "bg-info/15 text-info",
  rejected: "bg-danger/15 text-danger",
  archived: "bg-ink-600 text-ink-300",
};

function opts(values: string[]) {
  return values.map((v) => ({ label: v, value: v }));
}

export function BankExplorer({ scenarios }: { scenarios: BankScenario[] }) {
  const router = useRouter();
  const packs = Array.from(new Set(scenarios.map((s) => s.pack))).sort();
  const families = Array.from(new Set(scenarios.map((s) => s.family))).sort();
  const sources = Array.from(new Set(scenarios.map((s) => s.sourceType))).sort();

  const columns: Column<BankScenario>[] = [
    {
      key: "title",
      header: "Title",
      sortValue: (s) => s.title,
      searchText: (s) => `${s.title} ${s.publicId} ${s.scenarioId ?? ""} ${s.situation}`,
      filter: {
        label: "AI-drafted",
        options: [
          { label: "yes", value: "yes" },
          { label: "no", value: "no" },
        ],
        match: (s, v) => (v === "yes" ? s.aiDrafted : !s.aiDrafted),
      },
      cell: (s) => (
        <div className="max-w-md">
          <div className="flex items-center gap-2">
            <span className="text-ink-50">{s.title}</span>
            {s.aiDrafted && (
              <span
                className="rounded bg-info/20 px-1.5 py-0.5 text-[10px] text-info"
                title="AI-drafted from a source — unverified until a human approves"
              >
                AI-drafted
              </span>
            )}
          </div>
          <div className="font-mono text-[10px] text-ink-400">{s.scenarioId ?? s.publicId}</div>
        </div>
      ),
    },
    {
      key: "pack",
      header: "Pack",
      sortValue: (s) => s.pack,
      filter: { label: "Pack", options: opts(packs), match: (s, v) => s.pack === v },
      cell: (s) => <span className="capitalize text-ink-100">{s.pack}</span>,
    },
    {
      key: "family",
      header: "Family",
      sortValue: (s) => s.family,
      filter: { label: "Family", options: opts(families), match: (s, v) => s.family === v },
      cell: (s) => <span className="font-mono text-xs text-ink-300">{s.family}</span>,
    },
    {
      key: "tier",
      header: "Tier",
      sortValue: (s) => s.tier,
      filter: {
        label: "Tier",
        options: opts(["foundational", "intermediate", "advanced_crisis"]),
        match: (s, v) => s.tier === v,
      },
      cell: (s) => (
        <span className="rounded bg-ink-600 px-2 py-0.5 text-xs text-ink-200">
          {TIER_LABEL[s.tier] ?? s.tier}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (s) => s.status,
      filter: {
        label: "Status",
        options: opts(["draft", "in_review", "committed", "rejected", "archived"]),
        match: (s, v) => s.status === v,
      },
      cell: (s) => (
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[s.status] ?? "bg-ink-600"}`}>
          {s.status}
        </span>
      ),
    },
    {
      key: "source",
      header: "Source",
      sortValue: (s) => s.sourceType,
      filter: { label: "Source", options: opts(sources), match: (s, v) => s.sourceType === v },
      cell: (s) => <span className="text-xs text-ink-300">{s.sourceType}</span>,
    },
    {
      key: "created",
      header: "Created",
      sortValue: (s) => s.createdAt,
      cell: (s) => (
        <span className="text-xs text-ink-400">{new Date(s.createdAt).toLocaleDateString()}</span>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={scenarios}
      getRowKey={(s) => s.publicId}
      onRowClick={(s) => router.push(`/dashboard/scenario-bank/${s.publicId}`)}
      searchPlaceholder="Search title / situation / id…"
      emptyState={
        <EmptyState
          title="No scenarios match"
          description="Adjust the filters, or add a new scenario via ingestion."
          icon="📚"
        />
      }
    />
  );
}
