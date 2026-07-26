"use client";

import { useMemo, useState } from "react";

import { SeverityPill } from "@/components/gaps/SeverityPill";
import { Column, DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import type { SoftwareGap } from "@/lib/api/client";

// Normalize a summary so near-identical defects across forges cluster (e.g. "X degrades under
// crisis load" for X in {voiceforge, cre-forge, …}).
function clusterKey(summary: string): string {
  return summary
    .toLowerCase()
    .replace(/\b(voiceforge|cre-forge|vaf|medlink-pro|capitalforge|funnelforge)\b/g, "{forge}")
    .replace(/\b[a-z0-9_]+\.[a-z0-9_.]+\b/g, "{module}")
    .replace(/["'`]/g, "")
    .trim();
}

export function GapsExplorer({ gaps }: { gaps: SoftwareGap[] }) {
  const [clustered, setClustered] = useState(false);
  const forges = Array.from(new Set(gaps.map((g) => g.forge))).sort();

  const clusters = useMemo(() => {
    const map = new Map<string, SoftwareGap[]>();
    for (const g of gaps) {
      // Cluster on the machine string (so "degrades under crisis load" groups across forges)…
      const k = clusterKey(g.summary_technical ?? g.summary);
      (map.get(k) ?? map.set(k, []).get(k)!).push(g);
    }
    return Array.from(map.entries())
      .map(([key, items]) => ({ key, items }))
      .sort((a, b) => b.items.length - a.items.length);
  }, [gaps]);

  const dupClusters = clusters.filter((c) => c.items.length > 1);

  const columns: Column<SoftwareGap>[] = [
    {
      key: "ticket",
      header: "Ticket",
      sortValue: (g) => g.ticketId,
      searchText: (g) => `${g.ticketId} ${g.summary} ${g.module}`,
      cell: (g) => <span className="font-mono text-xs text-gold-400">{g.ticketId}</span>,
    },
    {
      key: "forge",
      header: "Forge / module",
      sortValue: (g) => g.forge,
      filter: { label: "Forge", options: forges.map((f) => ({ label: f, value: f })), match: (g, v) => g.forge === v },
      cell: (g) => (
        <span>
          <span className="font-mono text-xs text-ink-100">{g.forge}</span>
          <span className="text-ink-400"> / {g.module}</span>
        </span>
      ),
    },
    {
      key: "sev",
      header: "Sev",
      sortValue: (g) => g.severity,
      filter: {
        label: "Severity",
        options: ["P0", "P1", "P2"].map((s) => ({ label: s, value: s })),
        match: (g, v) => g.severity === v,
      },
      cell: (g) => <SeverityPill severity={g.severity} />,
    },
    {
      key: "summary",
      header: "Summary",
      searchText: (g) =>
        `${g.summary_plain?.what ?? ""} ${g.summary_plain?.why ?? ""} ${g.summary_technical ?? g.summary}`,
      cell: (g) => {
        const p = g.summary_plain;
        return (
          <div className="max-w-xl">
            <div className="flex items-start gap-2">
              <span className="text-ink-50">{p?.what ?? g.summary}</span>
              <code
                className="mt-0.5 shrink-0 rounded bg-ink-700 px-1.5 py-0.5 font-mono text-[10px] text-ink-300"
                title={g.summary_technical || g.summary}
              >
                {p?.code ?? "raw"}
              </code>
            </div>
            {p?.why && <div className="mt-1 text-xs text-ink-400">{p.why}</div>}
            {p?.action && (
              <details className="mt-1">
                <summary className="cursor-pointer text-xs text-gold-400 hover:underline">
                  What to do
                </summary>
                <div className="mt-1 rounded border border-ink-600 bg-ink-900/50 p-2 text-xs text-ink-200">
                  {p.action}
                </div>
              </details>
            )}
          </div>
        );
      },
    },
    {
      key: "seen",
      header: "Seen",
      align: "right",
      sortValue: (g) => g.occurrenceCount,
      cell: (g) => <span className="text-ink-100" title="Occurrences (run drill-down needs the run link exposed in the API)">×{g.occurrenceCount}</span>,
    },
    {
      key: "status",
      header: "Status",
      filter: { label: "Status", options: [{ label: "open", value: "open" }, { label: "resolved", value: "resolved" }], match: (g, v) => g.status === v },
      cell: (g) => <span className="text-ink-100">{g.status}</span>,
    },
    {
      key: "linear",
      header: "Linear",
      cell: (g) =>
        g.linearUrl ? (
          <a href={g.linearUrl} target="_blank" rel="noreferrer" className="text-gold-400 hover:underline">
            open ↗
          </a>
        ) : (
          <span className="text-[10px] text-ink-500" title="Linear integration not wired in dev">not routed</span>
        ),
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-ink-300">
          <input type="checkbox" checked={clustered} onChange={(e) => setClustered(e.target.checked)} />
          Cluster likely duplicates
        </label>
        {dupClusters.length > 0 && (
          <span className="text-xs text-warning">
            {dupClusters.length} likely-duplicate cluster(s) detected
          </span>
        )}
      </div>

      {clustered ? (
        <div className="flex flex-col gap-2">
          {clusters.map((c) => (
            <div key={c.key} className="rounded-lg border border-ink-500 bg-ink-800 p-3">
              <div className="flex items-center gap-2 text-sm">
                {c.items.length > 1 && <span className="rounded bg-warning/20 px-2 py-0.5 text-xs text-warning">×{c.items.length} duplicates</span>}
                {/* …but display the plain-language 'what' for the (shared) fault code. */}
                <span className="text-ink-50">
                  {c.items[0].summary_plain?.what ?? c.items[0].summary}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-1 text-[11px] text-ink-400">
                {c.items.map((g) => (
                  <span key={g.ticketId} className="font-mono">
                    {g.ticketId} ({g.forge})
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={gaps}
          getRowKey={(g) => g.ticketId}
          searchPlaceholder="Search ticket / summary / module…"
          emptyState={<EmptyState title="No gaps match" description="Adjust the forge/severity/status filters." icon="🐛" />}
        />
      )}
      <p className="text-xs text-ink-400">
        owner / first-seen / last-seen are not in the gap API response — rendered as absent; exposing
        them (and a run link for &ldquo;Seen ×N&rdquo;) needs an API change.
      </p>
    </div>
  );
}
