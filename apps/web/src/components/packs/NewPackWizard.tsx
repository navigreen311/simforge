"use client";

import { useEffect, useMemo, useState } from "react";

import { ConfirmModal } from "@/components/ui/ConfirmModal";
import {
  api,
  scenarioBank,
  type AuthoringOptions,
  type BankScenario,
  type PackCreateRequest,
  type PackCreateResponse,
  type PackDetail,
} from "@/lib/api/client";

// New-Pack wizard (Part B). Assembles a Pack from COMMITTED Scenario-Bank scenarios + venture /
// compliance / rubric metadata. Creating (or editing → new version) does NOT certify or run
// anything — it defines the certification library. Staged reveal mirrors IngestionPanel; form
// styling matches ScenarioForm.

const input =
  "w-full rounded border border-ink-500 bg-ink-900 px-3 py-2 text-sm text-ink-50 focus:border-gold-500 focus:outline-none";
const label = "mb-1 block text-xs font-semibold text-ink-300";
const TIER_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};

function slug(v: string): string {
  return v.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
}

interface Picked {
  s: BankScenario;
  agent: string;
  slo: number;
  golden: boolean;
}

const STEPS = ["Identity", "Compliance", "Rubric", "Scenarios", "Review"];

export function NewPackWizard({ base }: { base?: PackDetail }) {
  const editing = !!base;
  const [step, setStep] = useState(0);
  const [options, setOptions] = useState<AuthoringOptions | null>(null);
  const [committed, setCommitted] = useState<BankScenario[]>([]);
  const [agents, setAgents] = useState<string[]>([]);

  // identity
  const [title, setTitle] = useState(base?.name ?? "");
  const [venture, setVenture] = useState(base?.ownerVenture ?? "");
  // compliance
  const [phi, setPhi] = useState(base?.phiRequired ?? false);
  const [flags, setFlags] = useState<string[]>(base?.complianceFlags ?? []);
  const [mode, setMode] = useState(base?.executionModeDefault ?? "sandbox");
  // rubric
  const [rubric, setRubric] = useState(base?.rubricProfile ?? "");
  // scenarios
  const [picked, setPicked] = useState<Picked[]>([]);
  const [scenarioQ, setScenarioQ] = useState("");
  const [includeOtherVentures, setIncludeOtherVentures] = useState(false);
  // submit
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PackCreateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.authoringOptions().then(setOptions).catch(() => setOptions(null));
    scenarioBank.list({ status: "committed" }).then((r) => setCommitted(r.items)).catch(() => {});
    api.agents().then((r) => setAgents(r.items.map((a) => a.villageAgentId))).catch(() => {});
  }, []);

  const targetPackId = useMemo(() => {
    if (editing && base) {
      const m = base.packId.match(/\.v(\d+)$/);
      const next = m ? Number(m[1]) + 1 : 2;
      return `pack.${slug(venture)}.v${next}`;
    }
    return `pack.${slug(venture) || "venture"}.v1`;
  }, [editing, base, venture]);

  function applyVentureDefaults(v: string) {
    const s = options?.venture_suggestions[v];
    if (s) {
      setPhi(s.phiRequired);
      setFlags(s.complianceFlags);
      if (!rubric) setRubric(s.rubricProfile);
    }
  }

  function toggleFlag(f: string) {
    setFlags((cur) => (cur.includes(f) ? cur.filter((x) => x !== f) : [...cur, f]));
  }

  const ventureSlug = slug(venture);
  // Committed scenarios tagged to the selected venture (the pack-create scope).
  const ventureCommitted = committed.filter((c) => c.scenarioId && c.pack === ventureSlug);
  const pickedIds = new Set(picked.map((p) => p.s.scenarioId));
  const pool = includeOtherVentures ? committed : ventureCommitted;
  const available = pool.filter(
    (c) =>
      c.scenarioId &&
      !pickedIds.has(c.scenarioId) &&
      `${c.title} ${c.scenarioId}`.toLowerCase().includes(scenarioQ.trim().toLowerCase()),
  );

  function addScenario(c: BankScenario) {
    setPicked((cur) => [...cur, { s: c, agent: agents[0] ?? "", slo: 300, golden: false }]);
  }
  function updatePicked(id: string, patch: Partial<Picked>) {
    setPicked((cur) => cur.map((p) => (p.s.scenarioId === id ? { ...p, ...patch } : p)));
  }

  const stepValid = [
    title.trim() !== "" && slug(venture) !== "",
    true, // flags optional
    rubric.trim() !== "",
    picked.length >= 1 && picked.every((p) => p.agent.trim() !== "" && p.slo > 0),
    true,
  ];

  const goldenCount = picked.filter((p) => p.golden).length;

  async function submit() {
    setBusy(true);
    setError(null);
    setResult(null);
    const body: PackCreateRequest = {
      title: title.trim(),
      ownerVenture: slug(venture),
      version: "1.0.0",
      phiRequired: phi,
      complianceFlags: flags,
      executionModeDefault: mode,
      rubricProfile: rubric.trim(),
      scenarios: picked.map((p) => ({
        scenarioId: p.s.scenarioId as string,
        testedAgentVillageId: p.agent.trim(),
        sloSeconds: p.slo,
        testedForgeCaps: [],
        trainingDomains: [],
        isGolden: p.golden,
        seed: 0,
      })),
    };
    try {
      const res =
        editing && base
          ? await api.newPackVersion(base.packId, body)
          : await api.createPack(body);
      setResult(res);
      if (res.ok) {
        window.location.href = `/dashboard/packs/${res.packId}`;
        return;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
    } finally {
      setBusy(false);
      setConfirm(false);
    }
  }

  return (
    <div>
      <ol className="mb-6 flex flex-wrap gap-2 text-xs">
        {STEPS.map((s, i) => (
          <li
            key={s}
            className={`rounded-full px-3 py-1 ${
              i === step
                ? "bg-gold-500 text-ink-900"
                : i < step
                  ? "bg-ink-600 text-ink-100"
                  : "border border-ink-500 text-ink-400"
            }`}
          >
            {i + 1}. {s}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div className="flex flex-col gap-4">
          <div>
            <label className={label}>Pack title</label>
            <input
              className={input}
              placeholder="e.g. Argus Security Triage"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div>
            <label className={label}>Venture</label>
            <input
              className={input}
              list="ventures"
              disabled={editing}
              value={venture}
              onChange={(e) => setVenture(e.target.value)}
              onBlur={(e) => applyVentureDefaults(e.target.value)}
            />
            <datalist id="ventures">
              {options?.ventures.map((v) => <option key={v} value={v} />)}
            </datalist>
          </div>
          <div className="text-xs text-ink-400">
            Machine id: <span className="font-mono text-ink-200">{targetPackId}</span>
            {editing && " (new version — the current version is preserved)"}
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="flex flex-col gap-4">
          <label className="flex items-center gap-2 text-sm text-ink-100">
            <input type="checkbox" checked={phi} onChange={(e) => setPhi(e.target.checked)} />
            This Pack involves Protected Health Information (PHI)
          </label>
          <div>
            <label className={label}>Compliance flags (from the Jurisdiction engine)</label>
            <div className="flex flex-wrap gap-2">
              {(options?.jurisdiction_flags ?? []).map((f) => (
                <button
                  key={f}
                  onClick={() => toggleFlag(f)}
                  className={`rounded px-2 py-1 text-xs ${
                    flags.includes(f)
                      ? "bg-gold-500 text-ink-900"
                      : "border border-ink-500 text-ink-200 hover:bg-ink-700"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
            {phi && flags.length === 0 && (
              <p className="mt-2 text-xs text-warning">
                PHI packs should declare at least one compliance flag.
              </p>
            )}
            <p className="mt-2 text-xs text-ink-500">
              Suggested by venture — adjust as needed. The validator will confirm coverage on create.
            </p>
          </div>
          <div>
            <label className={label}>Execution mode</label>
            <select className={input} value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="sandbox">sandbox (mock Forge APIs)</option>
              <option value="integrated">integrated (real systems)</option>
            </select>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="flex flex-col gap-4">
          <div>
            <label className={label}>Rubric</label>
            <input
              className={input}
              list="rubrics"
              placeholder="e.g. medlink.default"
              value={rubric}
              onChange={(e) => setRubric(e.target.value)}
            />
            <datalist id="rubrics">
              {options?.rubrics.map((r) => <option key={r} value={r} />)}
            </datalist>
          </div>
          <p className="text-xs text-ink-500">
            Pick an existing rubric. Authoring a brand-new rubric is a separate task — it is not
            created here.
          </p>
        </div>
      )}

      {step === 3 && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-300">
            Add committed scenarios tagged to <strong>{ventureSlug}</strong>. Only{" "}
            <strong>committed</strong> scenarios can enter a Pack (reviewed material only).
          </p>

          {ventureCommitted.length === 0 && (
            <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-xs text-warning">
              <strong>{ventureSlug} has no committed scenarios yet.</strong> A pack can&apos;t be
              empty. Upload a spec to this venture or author scenarios in the{" "}
              <a href="/dashboard/scenario-bank/new" className="underline">
                Scenario Bank
              </a>{" "}
              and commit them first
              {committed.length > 0 && ", or include committed scenarios from other ventures below"}.
            </div>
          )}

          {picked.length > 0 && (
            <div className="rounded-lg border border-ink-500 bg-ink-800 p-3">
              <div className="mb-2 text-xs font-semibold text-ink-200">
                In this pack ({picked.length})
              </div>
              <div className="flex flex-col gap-2">
                {picked.map((p) => (
                  <div key={p.s.scenarioId} className="rounded border border-ink-600 p-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-ink-100">{p.s.title}</span>
                      <button
                        onClick={() =>
                          setPicked((cur) => cur.filter((x) => x.s.scenarioId !== p.s.scenarioId))
                        }
                        className="text-danger hover:underline"
                      >
                        remove
                      </button>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <span className="rounded bg-ink-600 px-1.5 py-0.5">
                        {TIER_LABEL[p.s.tier] ?? p.s.tier}
                      </span>
                      <input
                        className="w-40 rounded border border-ink-500 bg-ink-900 px-2 py-1 text-xs"
                        list="agents"
                        placeholder="tested agent"
                        value={p.agent}
                        onChange={(e) => updatePicked(p.s.scenarioId!, { agent: e.target.value })}
                      />
                      <label className="flex items-center gap-1 text-ink-400">
                        SLO
                        <input
                          type="number"
                          className="w-20 rounded border border-ink-500 bg-ink-900 px-2 py-1 text-xs"
                          value={p.slo}
                          onChange={(e) =>
                            updatePicked(p.s.scenarioId!, { slo: Number(e.target.value) })
                          }
                        />
                        s
                      </label>
                      <label className="flex items-center gap-1 text-ink-400">
                        <input
                          type="checkbox"
                          checked={p.golden}
                          onChange={(e) =>
                            updatePicked(p.s.scenarioId!, { golden: e.target.checked })
                          }
                        />
                        golden
                      </label>
                    </div>
                  </div>
                ))}
              </div>
              <datalist id="agents">
                {agents.map((a) => <option key={a} value={a} />)}
              </datalist>
              {(picked.length < 5 || goldenCount === 0) && (
                <div className="mt-2 text-xs text-warning">
                  {picked.length < 5 && "Thin coverage — few scenarios. "}
                  {goldenCount === 0 && "No golden benchmark scenario. "}
                  You can still create the pack.
                </div>
              )}
            </div>
          )}

          <div className="flex items-center gap-2">
            <input
              className={input}
              placeholder="Search committed scenarios…"
              value={scenarioQ}
              onChange={(e) => setScenarioQ(e.target.value)}
            />
            <label className="flex shrink-0 items-center gap-1 text-xs text-ink-400">
              <input
                type="checkbox"
                checked={includeOtherVentures}
                onChange={(e) => setIncludeOtherVentures(e.target.checked)}
              />
              include other ventures
            </label>
          </div>
          <div className="max-h-64 overflow-auto rounded-lg border border-ink-500">
            {available.length === 0 ? (
              <div className="p-3 text-xs text-ink-500">
                {includeOtherVentures
                  ? "No more committed scenarios to add."
                  : "No committed scenarios for this venture — tick “include other ventures”, or commit scenarios in the Scenario Bank first."}
              </div>
            ) : (
              available.map((c) => (
                <button
                  key={c.scenarioId}
                  onClick={() => addScenario(c)}
                  className="flex w-full items-center justify-between border-b border-ink-600 px-3 py-2 text-left text-xs last:border-0 hover:bg-ink-700"
                >
                  <span>
                    <span className="text-ink-100">{c.title}</span>{" "}
                    <span className="font-mono text-[10px] text-ink-500">{c.scenarioId}</span>
                  </span>
                  <span className="rounded bg-ink-600 px-1.5 py-0.5">
                    {TIER_LABEL[c.tier] ?? c.tier}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm">
            <div className="text-lg text-gold-500">{title}</div>
            <div className="font-mono text-xs text-ink-400">{targetPackId}</div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <Meta k="Venture" v={slug(venture)} />
              <Meta k="PHI" v={phi ? "yes" : "no"} />
              <Meta k="Mode" v={mode} />
              <Meta k="Rubric" v={rubric} />
              <Meta k="Flags" v={flags.join(", ") || "none"} />
              <Meta k="Scenarios" v={String(picked.length)} />
            </dl>
            <div className="mt-3">
              <div className="mb-1 text-xs font-semibold text-ink-300">Scenarios</div>
              <ul className="text-xs text-ink-200">
                {picked.map((p) => (
                  <li key={p.s.scenarioId}>
                    · {p.s.title} — {TIER_LABEL[p.s.tier] ?? p.s.tier}, {p.agent}, {p.slo}s
                    {p.golden ? ", golden" : ""}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <p className="text-xs text-ink-500">
            Creating this pack defines the library. It does <strong>not</strong> certify anyone or run
            anything, and it is logged.
          </p>
          {error && (
            <div className="rounded border border-danger/40 bg-danger/10 p-2 text-xs text-danger">
              {error}
            </div>
          )}
          {result && !result.ok && (
            <div className="rounded border border-danger/40 bg-danger/10 p-3 text-xs text-danger">
              <strong>Validation failed — pack not created.</strong>
              <ul className="mt-1 list-disc pl-4">
                {result.issues
                  .filter((i) => i.severity === "error")
                  .map((i, n) => (
                    <li key={n}>
                      {i.code}: {i.message}
                    </li>
                  ))}
              </ul>
            </div>
          )}
          <button
            onClick={() => setConfirm(true)}
            disabled={busy}
            className="self-start rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
          >
            {editing ? "Create new version" : "Create Pack"}
          </button>
        </div>
      )}

      <div className="mt-6 flex items-center justify-between">
        <button
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          className="rounded border border-ink-500 px-3 py-1.5 text-sm text-ink-200 hover:bg-ink-700 disabled:opacity-30"
        >
          ← Back
        </button>
        {step < STEPS.length - 1 && (
          <button
            onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
            disabled={!stepValid[step]}
            className="rounded bg-gold-500 px-4 py-1.5 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
          >
            Next →
          </button>
        )}
      </div>

      <ConfirmModal
        open={confirm}
        title={editing ? "Create a new pack version" : "Create this Pack"}
        requireWord="CREATE"
        confirmLabel="Create"
        busy={busy}
        onConfirm={submit}
        onCancel={() => setConfirm(false)}
      >
        This defines a certification library from {picked.length} committed scenario
        {picked.length === 1 ? "" : "s"}. It does not certify anyone or run anything. Continue?
      </ConfirmModal>
    </div>
  );
}

function Meta({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-ink-400">{k}</dt>
      <dd className="text-ink-100">{v}</dd>
    </div>
  );
}
