"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { FlagCatalog, Venture } from "@/lib/api/client";

// Venture Registry list (Part A). Cards with status, counts, and self-explaining compliance-flag
// chips (reusing the Packs flag catalog tooltips). Search + status/has-packs filters.

const STATUS_STYLE: Record<string, string> = {
  active: "bg-success/15 text-success",
  in_development: "bg-warning/20 text-warning",
  archived: "bg-ink-600 text-ink-300",
};
const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  in_development: "In development",
  archived: "Archived",
};

const selectCls =
  "rounded border border-ink-500 bg-ink-800 px-2 py-1.5 text-xs text-ink-100 focus:border-gold-500 focus:outline-none";

export function VenturesExplorer({
  ventures,
  catalog,
}: {
  ventures: Venture[];
  catalog: FlagCatalog;
}) {
  const [q, setQ] = useState("");
  const [statusF, setStatusF] = useState("");
  const [hasPacks, setHasPacks] = useState("");

  const statuses = useMemo(
    () => Array.from(new Set(ventures.map((v) => v.status))).sort(),
    [ventures],
  );

  const filtered = ventures.filter((v) => {
    if (statusF && v.status !== statusF) return false;
    if (hasPacks === "yes" && v.packCount === 0) return false;
    if (hasPacks === "no" && v.packCount > 0) return false;
    if (q.trim()) {
      const hay = `${v.name} ${v.slug} ${v.description}`.toLowerCase();
      if (!hay.includes(q.trim().toLowerCase())) return false;
    }
    return true;
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          className={`${selectCls} min-w-[220px] flex-1`}
          placeholder="Search ventures by name or description…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className={selectCls} value={statusF} onChange={(e) => setStatusF(e.target.value)}>
          <option value="">All statuses</option>
          {statuses.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s] ?? s}
            </option>
          ))}
        </select>
        <select className={selectCls} value={hasPacks} onChange={(e) => setHasPacks(e.target.value)}>
          <option value="">Packs: any</option>
          <option value="yes">Has packs</option>
          <option value="no">No packs</option>
        </select>
        <span className="text-xs text-ink-400">
          {filtered.length} of {ventures.length}
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-8 text-center text-ink-300">
          No ventures match these filters.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {filtered.map((v) => (
            <Link
              key={v.id}
              href={`/dashboard/ventures/${v.slug}`}
              className="block rounded-xl border border-ink-500 bg-ink-800 p-5 transition-colors hover:border-gold-600"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-display text-xl text-gold-500">{v.name}</span>
                <span
                  className={`shrink-0 rounded px-2 py-0.5 text-xs ${STATUS_STYLE[v.status] ?? "bg-ink-600 text-ink-200"}`}
                >
                  {STATUS_LABEL[v.status] ?? v.status}
                </span>
              </div>
              <div className="mt-0.5 font-mono text-[11px] text-ink-400">{v.slug}</div>
              <p className="mt-2 min-h-[1.25rem] text-sm text-ink-200">
                {v.description || <span className="text-ink-500">No description yet.</span>}
              </p>
              <div className="mt-3 flex flex-wrap gap-3 text-xs text-ink-300">
                <span>{v.packCount} pack{v.packCount === 1 ? "" : "s"}</span>
                <span>{v.committedScenarioCount} committed scenario{v.committedScenarioCount === 1 ? "" : "s"}</span>
                <span>{v.capabilityCount} capabilit{v.capabilityCount === 1 ? "y" : "ies"}</span>
              </div>
              {v.defaultComplianceFlags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  {v.defaultComplianceFlags.map((f) => {
                    const info = catalog.flags[f];
                    return (
                      <span
                        key={f}
                        title={info?.tooltip}
                        className={`cursor-help rounded px-2 py-0.5 ${
                          info?.phi ? "bg-danger/15 text-danger" : "bg-ink-600 text-ink-100"
                        }`}
                      >
                        {info?.label ?? f}
                      </span>
                    );
                  })}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
