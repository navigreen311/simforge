"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { lineage, type LineageSubgraph } from "@/lib/api/client";

export type LineageEntity = { urn: string; label: string; kind: string };

const RELATION_STYLE: Record<string, string> = {
  produced_by: "bg-info/15 text-info",
  derived_from: "bg-gold-600/20 text-gold-300",
  pinned_to: "bg-warning/20 text-warning",
  evidenced_by: "bg-success/15 text-success",
};

function shortUrn(urn: string): string {
  const parts = urn.split(":");
  return parts.length >= 5 ? `${parts[3]}:${parts.slice(4).join(":")}` : urn;
}

export function LineageExplorer({ entities }: { entities: LineageEntity[] }) {
  const [root, setRoot] = useState(entities[0]?.urn ?? "");
  const [depth, setDepth] = useState(1);
  const [direction, setDirection] = useState<"all" | "out" | "in">("all");
  const [query, setQuery] = useState("");
  const [graph, setGraph] = useState<LineageSubgraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!root) return;
    setLoading(true);
    setError(null);
    try {
      setGraph(await lineage.subgraph(root, depth));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load lineage");
    } finally {
      setLoading(false);
    }
  }, [root, depth]);

  useEffect(() => {
    load();
  }, [load]);

  const filteredEntities = query.trim()
    ? entities.filter((e) => `${e.label} ${e.urn}`.toLowerCase().includes(query.toLowerCase()))
    : entities;

  const edges = useMemo(() => {
    if (!graph) return [];
    return graph.edges.filter((e) => {
      if (direction === "out") return e.from === root;
      if (direction === "in") return e.to === root;
      return true;
    });
  }, [graph, direction, root]);

  const grouped = useMemo(() => {
    const g: Record<string, typeof edges> = {};
    for (const e of edges) (g[e.relation] ??= []).push(e);
    return g;
  }, [edges]);

  return (
    <div className="flex flex-col gap-4">
      {/* Controls */}
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-ink-500 bg-ink-800 p-4">
        <label className="flex flex-1 flex-col gap-1 text-xs text-ink-300">
          Root entity
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="filter entities…"
            className="rounded border border-ink-500 bg-ink-900 px-2 py-1.5 text-xs text-ink-50"
          />
          <select
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            className="min-w-[18rem] rounded border border-ink-500 bg-ink-900 px-2 py-1.5 text-sm text-ink-50"
            size={1}
          >
            {filteredEntities.map((e) => (
              <option key={e.urn} value={e.urn}>
                [{e.kind}] {e.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-ink-300">
          Depth
          <select value={depth} onChange={(e) => setDepth(Number(e.target.value))} className="rounded border border-ink-500 bg-ink-900 px-2 py-1.5 text-sm text-ink-100">
            {[1, 2, 3].map((d) => (
              <option key={d} value={d}>
                {d} hop{d > 1 ? "s" : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-ink-300">
          Direction
          <select value={direction} onChange={(e) => setDirection(e.target.value as "all" | "out" | "in")} className="rounded border border-ink-500 bg-ink-900 px-2 py-1.5 text-sm text-ink-100">
            <option value="all">both</option>
            <option value="out">outgoing (root → …)</option>
            <option value="in">incoming (… → root, reverse)</option>
          </select>
        </label>
      </div>

      <div className="text-sm text-ink-300">
        Root: <span className="font-mono text-gold-400">{shortUrn(root)}</span>
        {graph && (
          <span className="ml-3 text-xs text-ink-400">
            {edges.length} edges · {graph.nodes.length} nodes in {depth}-hop neighborhood
          </span>
        )}
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">{error}</div>
      ) : loading ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-center text-ink-300">Loading…</div>
      ) : edges.length === 0 ? (
        <EmptyState title="No edges" description="No provenance edges in this direction/depth for the selected root." icon="🕸" />
      ) : (
        <div className="flex flex-col gap-4">
          {Object.entries(grouped).map(([relation, es]) => (
            <div key={relation}>
              <div className="mb-2 flex items-center gap-2">
                <span className={`rounded px-2 py-0.5 text-xs ${RELATION_STYLE[relation] ?? "bg-ink-600 text-ink-100"}`}>
                  {relation}
                </span>
                <span className="text-xs text-ink-400">{es.length}</span>
              </div>
              <div className="flex flex-col gap-1.5">
                {es.map((e, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg border border-ink-500 bg-ink-800 px-4 py-2 text-sm">
                    <span className="font-mono text-xs text-ink-100">{shortUrn(e.from)}</span>
                    <span className="text-ink-400">→</span>
                    <span className="font-mono text-xs text-ink-100">{shortUrn(e.to)}</span>
                    {e.to.includes(":evidence:") || e.to.includes("certsnap") ? (
                      <span className="ml-auto text-[10px] text-ink-500">evidence artifact</span>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
