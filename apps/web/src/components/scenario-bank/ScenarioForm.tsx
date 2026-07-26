"use client";

import { useState } from "react";

import type { BankVocabulary, DraftBody } from "@/lib/api/client";

// Shared authoring / review form. Used by manual authoring (blank) and by extraction review
// (pre-filled from an AI candidate). It NEVER commits — it only saves a human-approved DRAFT.
// List fields (behaviors/tactics/flags) are edited one-per-line: simple, robust, no hidden state.

export interface ScenarioFormValues {
  title: string;
  pack: string;
  family: string;
  tier: string;
  situation: string;
  expectedBehaviors: string[];
  adversarialTactics: string[];
  jurisdictionFlags: string[];
}

const TIER_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};

const input =
  "w-full rounded border border-ink-500 bg-ink-900 px-3 py-2 text-sm text-ink-50 focus:border-gold-500 focus:outline-none";
const labelCls = "mb-1 block text-xs font-semibold text-ink-300";

function lines(v: string): string[] {
  return v
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function ScenarioForm({
  vocab,
  initial,
  aiDrafted,
  sourceType,
  sourceRef,
  sourceExcerpt,
  submitLabel,
  onSaved,
}: {
  vocab: BankVocabulary;
  initial?: Partial<ScenarioFormValues>;
  aiDrafted: boolean;
  sourceType: string;
  sourceRef?: string | null;
  sourceExcerpt?: string | null;
  submitLabel: string;
  // Given a fully-built draft body, persist it (create or edit) and return the new publicId.
  onSaved: (body: DraftBody) => Promise<string>;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [pack, setPack] = useState(initial?.pack ?? vocab.packs[0]);
  const [family, setFamily] = useState(initial?.family ?? vocab.families[0]);
  const [tier, setTier] = useState(initial?.tier ?? vocab.tiers[0]);
  const [situation, setSituation] = useState(initial?.situation ?? "");
  const [behaviors, setBehaviors] = useState((initial?.expectedBehaviors ?? []).join("\n"));
  const [tactics, setTactics] = useState((initial?.adversarialTactics ?? []).join("\n"));
  const [flags, setFlags] = useState((initial?.jurisdictionFlags ?? []).join("\n"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const valid = title.trim() && situation.trim();

  async function save() {
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      const publicId = await onSaved({
        title: title.trim(),
        pack,
        family,
        tier,
        situation: situation.trim(),
        expectedBehaviors: lines(behaviors),
        adversarialTactics: lines(tactics),
        jurisdictionFlags: lines(flags),
        aiDrafted,
        sourceType,
        sourceRef: sourceRef ?? null,
        sourceExcerpt: sourceExcerpt ?? null,
      });
      window.location.href = `/dashboard/scenario-bank/${publicId}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {aiDrafted && (
        <div className="rounded-lg border border-info/40 bg-info/10 p-3 text-xs text-info">
          <strong>AI-drafted candidate — unverified.</strong> Review and correct every field. Saving
          stores it as a <strong>draft</strong> for your records; it only enters the bank when you
          later click <em>Commit</em>. Nothing here auto-commits.
        </div>
      )}

      <div>
        <label className={labelCls}>Title</label>
        <input className={input} value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className={labelCls}>Pack</label>
          <select className={input} value={pack} onChange={(e) => setPack(e.target.value)}>
            {vocab.packs.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Family</label>
          <select className={input} value={family} onChange={(e) => setFamily(e.target.value)}>
            {vocab.families.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Tier</label>
          <select className={input} value={tier} onChange={(e) => setTier(e.target.value)}>
            {vocab.tiers.map((t) => (
              <option key={t} value={t}>
                {TIER_LABEL[t] ?? t}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className={labelCls}>Situation (what the agent faces)</label>
        <textarea
          className={`${input} min-h-[120px]`}
          value={situation}
          onChange={(e) => setSituation(e.target.value)}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label className={labelCls}>Expected behaviors (one per line)</label>
          <textarea
            className={`${input} min-h-[100px]`}
            value={behaviors}
            onChange={(e) => setBehaviors(e.target.value)}
          />
        </div>
        <div>
          <label className={labelCls}>Adversarial tactics (one per line)</label>
          <textarea
            className={`${input} min-h-[100px]`}
            value={tactics}
            onChange={(e) => setTactics(e.target.value)}
          />
        </div>
        <div>
          <label className={labelCls}>Jurisdiction flags (one per line)</label>
          <textarea
            className={`${input} min-h-[100px]`}
            value={flags}
            onChange={(e) => setFlags(e.target.value)}
          />
        </div>
      </div>

      {error && <div className="rounded border border-danger/40 bg-danger/10 p-2 text-xs text-danger">{error}</div>}

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={!valid || busy}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:bg-gold-400 disabled:opacity-40"
        >
          {busy ? "Saving…" : submitLabel}
        </button>
        <span className="text-xs text-ink-500">Saves as a draft — never commits.</span>
      </div>
    </div>
  );
}
