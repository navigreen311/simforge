"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { FlagCatalog, PackCard } from "@/lib/api/client";

// Readable Packs list (Part A). Cards (a pack is richer than a table row) with the shared filter/
// search conventions, self-explaining chips (native `title` tooltips + a persistent legend), and a
// per-pack plain-language summary. Presentation only — no data or certification change.

const TIER_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};
const TIER_ORDER = ["foundational", "intermediate", "advanced_crisis"];

const selectCls =
  "rounded border border-ink-500 bg-ink-800 px-2 py-1.5 text-xs text-ink-100 focus:border-gold-500 focus:outline-none";

function tierSpread(tierCounts: Record<string, number>): string {
  const parts = TIER_ORDER.filter((t) => (tierCounts[t] ?? 0) > 0).map(
    (t) => `${tierCounts[t]} ${TIER_LABEL[t]}`,
  );
  return parts.join(", ");
}

export function PacksExplorer({ packs, catalog }: { packs: PackCard[]; catalog: FlagCatalog }) {
  const [q, setQ] = useState("");
  const [venture, setVenture] = useState("");
  const [phi, setPhi] = useState("");
  const [golden, setGolden] = useState("");

  const ventures = useMemo(
    () => Array.from(new Set(packs.map((p) => p.ownerVenture))).sort(),
    [packs],
  );

  const filtered = packs.filter((p) => {
    if (venture && p.ownerVenture !== venture) return false;
    if (phi === "yes" && !p.phiRequired) return false;
    if (phi === "no" && p.phiRequired) return false;
    if (golden === "yes" && p.goldenCount === 0) return false;
    if (golden === "no" && p.goldenCount > 0) return false;
    if (q.trim()) {
      const hay = `${p.name} ${p.packId}`.toLowerCase();
      if (!hay.includes(q.trim().toLowerCase())) return false;
    }
    return true;
  });

  return (
    <div>
      <Legend catalog={catalog} />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          className={`${selectCls} min-w-[220px] flex-1`}
          placeholder="Search packs by title or id…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className={selectCls} value={venture} onChange={(e) => setVenture(e.target.value)}>
          <option value="">All ventures</option>
          {ventures.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
        <select className={selectCls} value={phi} onChange={(e) => setPhi(e.target.value)}>
          <option value="">PHI: any</option>
          <option value="yes">PHI only</option>
          <option value="no">Non-PHI only</option>
        </select>
        <select className={selectCls} value={golden} onChange={(e) => setGolden(e.target.value)}>
          <option value="">Golden: any</option>
          <option value="yes">Has golden</option>
          <option value="no">No golden</option>
        </select>
        <span className="text-xs text-ink-400">
          {filtered.length} of {packs.length}
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-8 text-center text-ink-300">
          No packs match these filters.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {filtered.map((p) => (
            <PackCardView key={p.id} pack={p} catalog={catalog} />
          ))}
        </div>
      )}
    </div>
  );
}

function Legend({ catalog }: { catalog: FlagCatalog }) {
  const items: [string, string][] = [
    ["Venture", catalog.legend.venture ?? ""],
    ["PHI", catalog.legend.phi ?? ""],
    ["sandbox", catalog.legend.sandbox ?? ""],
  ];
  return (
    <details className="mb-4 rounded-lg border border-ink-500 bg-ink-800 p-3 text-xs" open>
      <summary className="cursor-pointer font-semibold text-ink-200">What the chips mean</summary>
      <dl className="mt-2 grid gap-2 sm:grid-cols-3">
        {items.map(([k, v]) => (
          <div key={k}>
            <dt className="font-mono text-ink-100">{k}</dt>
            <dd className="text-ink-400">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-ink-500">
        Hover any compliance flag chip (e.g. HIPAA, I-9) for a plain-language explanation.
      </p>
    </details>
  );
}

function Chip({
  text,
  tip,
  tone = "neutral",
}: {
  text: string;
  tip?: string;
  tone?: "neutral" | "phi" | "mode" | "signed" | "locale";
}) {
  const cls = {
    neutral: "bg-ink-600 text-ink-100",
    phi: "bg-danger/15 text-danger",
    mode: "bg-ink-600 text-ink-200",
    signed: "bg-success/15 text-success",
    locale: "bg-info/15 text-info uppercase",
  }[tone];
  return (
    <span
      className={`rounded px-2 py-0.5 ${cls} ${tip ? "cursor-help" : ""}`}
      title={tip}
    >
      {text}
    </span>
  );
}

function PackCardView({ pack, catalog }: { pack: PackCard; catalog: FlagCatalog }) {
  const mode = pack.executionModeDefault;
  return (
    <Link
      href={`/dashboard/packs/${pack.packId}`}
      className="block rounded-xl border border-ink-500 bg-ink-800 p-5 transition-colors hover:border-gold-600"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-display text-xl text-gold-500">{pack.name}</span>
        <span className="shrink-0 font-mono text-xs text-ink-400">v{pack.version}</span>
      </div>
      <div className="mt-0.5 font-mono text-[11px] text-ink-400">{pack.packId}</div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <Chip text={pack.ownerVenture} tip={catalog.legend.venture} />
        {pack.phiRequired && <Chip text="PHI" tip={catalog.legend.phi} tone="phi" />}
        <Chip
          text={mode}
          tip={mode === "sandbox" ? catalog.legend.sandbox : catalog.legend.integrated}
          tone="mode"
        />
        {pack.locale && pack.locale !== "en" && <Chip text={pack.locale} tone="locale" />}
        {pack.signedBy && <Chip text="signed" tip={catalog.legend.signed} tone="signed" />}
        {pack.complianceFlags.map((f) => {
          const info = catalog.flags[f];
          return (
            <Chip
              key={f}
              text={info?.label ?? f}
              tip={info?.tooltip}
              tone={info?.phi ? "phi" : "neutral"}
            />
          );
        })}
      </div>

      <div className="mt-3 text-sm text-ink-200">
        {pack.scenarioCount} scenario{pack.scenarioCount === 1 ? "" : "s"}
        {tierSpread(pack.tierCounts) ? ` · ${tierSpread(pack.tierCounts)}.` : "."}
      </div>
      {pack.goldenCount > 0 && (
        <div className="mt-1 text-xs text-gold-300" title={catalog.legend.golden}>
          Includes {pack.goldenCount} golden benchmark scenario{pack.goldenCount === 1 ? "" : "s"}.
        </div>
      )}
      {pack.scenarioCount < 5 && (
        <div className="mt-1 text-xs text-ink-500">Thin coverage — few scenarios.</div>
      )}
    </Link>
  );
}
