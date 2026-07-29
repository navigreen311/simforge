"use client";

import { useRouter } from "next/navigation";
import { Fragment, useState } from "react";

import type { DimStats, MetaVerdict, RemediationIntent } from "@/lib/api/client";
import { metaEval } from "@/lib/api/client";
import { describeDimension, scorerFor } from "@/lib/dimensions";

function fmt(v: number | null, digits = 2): string {
  return v === null || v === undefined ? "—" : v.toFixed(digits);
}

// Verdict presentation. INVERTED is styled distinctly from DEAD — they are different defects
// (rewards-the-wrong-thing vs no-signal), so they must not read the same.
const VERDICT: Record<MetaVerdict, { badge: string; cls: string }> = {
  dead: { badge: "DEAD", cls: "bg-danger/20 text-danger" },
  inverted: { badge: "▲ INVERTED", cls: "bg-warning/25 text-warning ring-1 ring-warning/40" },
  weak: { badge: "WEAK", cls: "bg-ink-600 text-ink-200" },
  working: { badge: "WORKING", cls: "bg-success/15 text-success" },
  insufficient: { badge: "—", cls: "bg-ink-700 text-ink-400" },
};

// Plain recommendation, derived from the verdict + stats (never invented).
function recommendation(d: DimStats): string {
  switch (d.verdict) {
    case "dead":
      return `DEAD — every agent gets ${fmt(d.mean)}. This dimension adds nothing to certification. Recommend: retire it, or re-implement the scorer so it actually varies.`;
    case "inverted":
      return `INVERTED — agents who FAIL score higher here than agents who pass. This dimension may be rewarding the wrong behavior. Recommend: investigate the scorer; do not weight this dimension until it is fixed.`;
    case "weak":
      return `WEAK — varies but doesn't predict pass/fail. Recommend: review whether it belongs in the rubric.`;
    case "working":
      return `WORKING — separates passing from failing agents. Keep.`;
    default:
      return `Not enough scorecards to judge this dimension.`;
  }
}

function flagPill(flag: string) {
  const styles: Record<string, string> = {
    constant: "bg-danger/15 text-danger",
    non_discriminating: "bg-warning/20 text-warning",
    insufficient_data: "bg-ink-600 text-ink-300",
    no_data: "bg-ink-600 text-ink-300",
  };
  return (
    <span key={flag} className={`rounded px-2 py-0.5 text-[11px] ${styles[flag] ?? "bg-ink-600 text-ink-100"}`}>
      {flag}
    </span>
  );
}

const INTENT_OPTIONS = [
  { value: "", label: "— set intent —" },
  { value: "keep", label: "Keep" },
  { value: "retire", label: "Retire" },
  { value: "reimplement", label: "Re-implement scorer" },
  { value: "investigate", label: "Investigate" },
];

function IntentControl({ dim, current }: { dim: string; current?: RemediationIntent }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [value, setValue] = useState(current?.intent ?? "");

  async function onChange(next: string) {
    setValue(next);
    if (!next) return;
    setBusy(true);
    try {
      await metaEval.setIntent(dim, next);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <select
      value={value}
      disabled={busy}
      onChange={(e) => onChange(e.target.value)}
      title="Advisory triage note — does NOT change scoring. Records what you intend to do about this dimension."
      className="rounded border border-ink-500 bg-ink-800 px-1.5 py-1 text-[11px] text-ink-100 disabled:opacity-50"
    >
      {INTENT_OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function Th({ label, tip }: { label: string; tip: string }) {
  return (
    <th className="px-3 py-3 font-medium">
      <span className="cursor-help decoration-ink-500 decoration-dotted underline-offset-4 [text-decoration-line:underline]" title={tip}>
        {label}
      </span>
    </th>
  );
}

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function MetaEvalTable({
  dimensions,
  intents,
}: {
  dimensions: DimStats[];
  intents: Record<string, RemediationIntent>;
}) {
  const [filter, setFilter] = useState<"all" | "flagged" | "working">("all");
  const [openRow, setOpenRow] = useState<string | null>(null);

  const isFlagged = (d: DimStats) => d.verdict === "dead" || d.verdict === "inverted" || d.verdict === "weak";
  const rows = dimensions.filter((d) =>
    filter === "flagged" ? isFlagged(d) : filter === "working" ? d.verdict === "working" : true,
  );

  function exportRows(kind: "csv" | "json") {
    const enriched = dimensions.map((d) => ({
      dimension: d.dim,
      name: describeDimension(d.dim).name,
      scorer: scorerFor(d.dim),
      n: d.n,
      mean: d.mean,
      stddev: d.stddev,
      mean_passed: d.mean_passed,
      mean_failed: d.mean_failed,
      discrimination: d.discrimination,
      verdict: d.verdict,
      flags: d.flags.join("|"),
      recommendation: recommendation(d),
      remediation_intent: intents[d.dim]?.intent ?? "",
    }));
    if (kind === "json") {
      download("meta-eval-dimensions.json", JSON.stringify(enriched, null, 2), "application/json");
      return;
    }
    const cols = Object.keys(enriched[0] ?? { dimension: "" });
    const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [cols.join(","), ...enriched.map((r) => cols.map((c) => esc((r as Record<string, unknown>)[c])).join(","))].join("\n");
    download("meta-eval-dimensions.csv", csv, "text/csv");
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1 text-xs">
          {(["all", "flagged", "working"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full px-3 py-1 ${filter === f ? "bg-gold-500 text-ink-900" : "bg-ink-700 text-ink-100 hover:bg-ink-600"}`}
            >
              {f === "all" ? "All" : f === "flagged" ? "Only flagged" : "Only working"}
            </button>
          ))}
        </div>
        <div className="flex gap-2 text-xs">
          <button onClick={() => exportRows("csv")} className="rounded border border-ink-500 px-2 py-1 text-ink-200 hover:bg-ink-700">
            Export CSV
          </button>
          <button onClick={() => exportRows("json")} className="rounded border border-ink-500 px-2 py-1 text-ink-200 hover:bg-ink-700">
            Export JSON
          </button>
        </div>
      </div>

      <div className="max-h-[70vh] overflow-auto rounded-xl border border-ink-500">
        <table className="min-w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-ink-800 text-ink-200">
            <tr>
              <Th label="Dimension" tip="One thing agents are scored on." />
              <Th label="Scorer" tip="How this dimension is scored — 'heuristic' = a rule/formula; 'stub-judge' = placeholder LLM judge not yet using real signal." />
              <Th label="n" tip="How many scorecards this is based on." />
              <Th label="Mean" tip="Average score on this dimension." />
              <Th label="Std" tip="How much the score varies. 0.000 = every agent got the same score — the dimension isn't distinguishing anyone." />
              <Th label="Passed" tip="Average score on this dimension among agents who passed overall." />
              <Th label="Failed" tip="Average score on this dimension among agents who failed overall." />
              <Th label="Discrimination" tip="Passed-mean minus failed-mean. Positive = passing agents score higher (good). ~0 = no signal. Negative = failing agents score HIGHER (broken)." />
              <Th label="Verdict" tip="Plain reading: DEAD (no signal), INVERTED (rewards wrong), WEAK (no separation), WORKING (separates pass/fail)." />
              <Th label="Flags" tip="constant = same score for everyone; non_discriminating = doesn't separate pass from fail." />
              <Th label="Intent" tip="Owner triage note (advisory — does NOT change scoring)." />
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-600">
            {rows.map((d) => {
              const info = describeDimension(d.dim);
              const inverted = d.verdict === "inverted";
              const v = VERDICT[d.verdict];
              const open = openRow === d.dim;
              return (
                <Fragment key={d.dim}>
                  <tr
                    className={`cursor-pointer ${d.verdict === "dead" || inverted ? "bg-danger/5" : "hover:bg-ink-800/60"}`}
                    onClick={() => setOpenRow(open ? null : d.dim)}
                  >
                    <td className="px-3 py-3">
                      <div className="text-ink-50">{info.name}</div>
                      <div className="font-mono text-[10px] text-ink-500">{d.dim}</div>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`rounded px-2 py-0.5 text-[10px] ${scorerFor(d.dim) === "stub-judge" ? "bg-warning/20 text-warning" : "bg-ink-600 text-ink-200"}`}>
                        {scorerFor(d.dim)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-ink-200">{d.n}</td>
                    <td className="px-3 py-3 text-ink-100">{fmt(d.mean)}</td>
                    <td className={`px-3 py-3 ${d.stddev !== null && d.stddev < 0.001 ? "text-danger" : "text-ink-100"}`}>
                      {fmt(d.stddev, 3)}
                    </td>
                    <td className="px-3 py-3 text-ink-200">{fmt(d.mean_passed)}</td>
                    <td className="px-3 py-3 text-ink-200">{fmt(d.mean_failed)}</td>
                    <td className={`px-3 py-3 font-medium ${inverted ? "text-danger" : d.discrimination !== null && Math.abs(d.discrimination) < 0.05 ? "text-warning" : "text-ink-50"}`}>
                      {fmt(d.discrimination)}
                      {inverted && " ▲"}
                    </td>
                    <td className="px-3 py-3">
                      <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ${v.cls}`}>{v.badge}</span>
                    </td>
                    <td className="px-3 py-3">
                      <span className="flex flex-wrap gap-1">{d.flags.map(flagPill)}</span>
                    </td>
                    <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                      <IntentControl dim={d.dim} current={intents[d.dim]} />
                    </td>
                  </tr>
                  {open && (
                    <tr className="bg-ink-900/40">
                      <td colSpan={11} className="px-4 py-3 text-xs text-ink-200">
                        {recommendation(d)}
                        {intents[d.dim] && (
                          <span className="ml-2 text-ink-400">
                            · current intent: <strong className="text-ink-100">{intents[d.dim].intent}</strong>
                          </span>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-ink-400">Click a row for its plain verdict + recommendation.</p>
    </div>
  );
}
