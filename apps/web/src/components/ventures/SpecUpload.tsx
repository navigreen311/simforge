"use client";

import { useState } from "react";

import {
  ventures as venturesApi,
  type EnrichmentProposal,
  type SpecUploadResponse,
  type VentureDetail,
} from "@/lib/api/client";

// Spec upload (Part B). Uploads a PDF/DOCX/TXT/MD, then shows a human-reviewed enrichment DIFF
// (Pass 1) + the AI-draft scenarios it routed to the Scenario Bank (Pass 2). Nothing is applied to
// the venture until the operator accepts fields here; scenarios stay unreviewed drafts in the bank.

const box = "w-full rounded border border-ink-500 bg-ink-900 px-3 py-2 text-sm text-ink-50";

function lines(v: string): string[] {
  return v.split("\n").map((s) => s.trim()).filter(Boolean);
}

export function SpecUpload({ venture }: { venture: VentureDetail }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SpecUploadResponse | null>(null);

  async function upload() {
    if (!file || busy) return;
    setBusy(true);
    setResult(null);
    try {
      setResult(await venturesApi.uploadSpec(venture.slug, file));
    } catch (e) {
      setResult({
        ok: false,
        error: e instanceof Error ? e.message : "Upload failed",
        specDocumentId: null,
        filename: file.name,
        enrichment: null,
        produced_scenarios: [],
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-ink-500 bg-ink-800 p-4">
      <h3 className="mb-1 text-sm font-semibold text-ink-200">Upload spec</h3>
      <p className="mb-3 text-xs text-ink-400">
        PDF, DOCX, TXT, or MD. Proposes venture metadata (you review a diff below) and routes draft
        scenarios into the Scenario Bank for review. Nothing is applied or committed automatically.
      </p>
      <div className="flex items-center gap-2">
        <input
          type="file"
          accept=".pdf,.docx,.txt,.md,.markdown,.rst"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm text-ink-200 file:mr-3 file:rounded file:border-0 file:bg-ink-600 file:px-3 file:py-1.5 file:text-ink-100"
        />
        <button
          onClick={upload}
          disabled={!file || busy}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
        >
          {busy ? "Reading…" : "Upload & extract"}
        </button>
      </div>

      {result && !result.ok && (
        <div className="mt-3 rounded border border-warning/40 bg-warning/10 p-3 text-xs text-warning">
          <strong>Nothing was produced.</strong>
          <p className="mt-1">{result.error}</p>
          <p className="mt-1 text-ink-400">
            No content is fabricated. An unreadable spec (scanned PDF, no text) or the offline dev LLM
            yields nothing.
          </p>
        </div>
      )}

      {result?.ok && (
        <div className="mt-4 flex flex-col gap-4">
          {result.enrichment ? (
            <EnrichmentDiff venture={venture} proposal={result.enrichment} />
          ) : (
            <p className="text-xs text-ink-500">
              No metadata enrichment was proposed from this spec (the dev stub LLM cannot enrich —
              configure a real provider).
            </p>
          )}

          <div>
            <h4 className="mb-1 text-xs font-semibold text-ink-300">
              Draft scenarios produced ({result.produced_scenarios.length})
            </h4>
            {result.produced_scenarios.length ? (
              <ul className="text-xs text-ink-200">
                {result.produced_scenarios.map((s) => (
                  <li key={s.publicId}>
                    ·{" "}
                    <a
                      href={`/dashboard/scenario-bank/${s.publicId}`}
                      className="text-gold-400 hover:underline"
                    >
                      {s.title}
                    </a>{" "}
                    <span className="text-ink-500">
                      — {s.tier} · unreviewed AI draft, awaiting review in the Scenario Bank
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-ink-500">
                No scenario draft was extracted from this spec.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function EnrichmentDiff({
  venture,
  proposal,
}: {
  venture: VentureDetail;
  proposal: EnrichmentProposal;
}) {
  const [applyDesc, setApplyDesc] = useState(proposal.description !== "");
  const [desc, setDesc] = useState(proposal.description);
  const [applyFlags, setApplyFlags] = useState(proposal.complianceFlags.length > 0);
  const [flags, setFlags] = useState(proposal.complianceFlags.join("\n"));
  const [applyForges, setApplyForges] = useState(proposal.internalForges.length > 0);
  const [forges, setForges] = useState(proposal.internalForges.join("\n"));
  const [applyCaps, setApplyCaps] = useState(proposal.capabilities.length > 0);
  const [caps, setCaps] = useState(proposal.capabilities.join("\n"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);

  async function apply() {
    setBusy(true);
    setError(null);
    const body: Record<string, unknown> = {};
    if (applyDesc) body.description = desc.trim();
    if (applyFlags) body.defaultComplianceFlags = lines(flags);
    if (applyForges) body.internalForges = lines(forges);
    if (applyCaps) body.capabilities = lines(caps);
    if (Object.keys(body).length === 0) {
      setError("Nothing selected to apply.");
      setBusy(false);
      return;
    }
    try {
      await venturesApi.update(venture.slug, body);
      setApplied(true);
      window.location.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Apply failed");
      setBusy(false);
    }
  }

  const conf = proposal.confidence;
  return (
    <div className="rounded border border-info/30 bg-info/5 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs">
        <span className="font-semibold text-info">Proposed metadata — review before applying</span>
        {conf != null && (
          <span
            className={`rounded px-2 py-0.5 ${conf < 0.5 ? "bg-warning/20 text-warning" : "bg-ink-600 text-ink-200"}`}
          >
            confidence {(conf * 100).toFixed(0)}%
          </span>
        )}
      </div>

      <Field
        label="Description"
        checked={applyDesc}
        onCheck={setApplyDesc}
        current={venture.description || "(empty)"}
      >
        <textarea className={`${box} min-h-[70px]`} value={desc} onChange={(e) => setDesc(e.target.value)} />
      </Field>
      <Field
        label="Compliance flags (one per line)"
        checked={applyFlags}
        onCheck={setApplyFlags}
        current={venture.defaultComplianceFlags.join(", ") || "(none)"}
      >
        <textarea className={`${box} min-h-[60px]`} value={flags} onChange={(e) => setFlags(e.target.value)} />
      </Field>
      <Field
        label="Internal Forges (one per line)"
        checked={applyForges}
        onCheck={setApplyForges}
        current={venture.internalForges.join(", ") || "(none)"}
      >
        <textarea className={`${box} min-h-[60px]`} value={forges} onChange={(e) => setForges(e.target.value)} />
      </Field>
      <Field
        label="Capabilities (one per line)"
        checked={applyCaps}
        onCheck={setApplyCaps}
        current={venture.capabilities.join(", ") || "(none)"}
      >
        <textarea className={`${box} min-h-[60px]`} value={caps} onChange={(e) => setCaps(e.target.value)} />
      </Field>

      {error && <div className="mt-2 text-xs text-danger">{error}</div>}
      <button
        onClick={apply}
        disabled={busy || applied}
        className="mt-3 rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
      >
        {busy ? "Applying…" : "Apply accepted fields to venture"}
      </button>
    </div>
  );
}

function Field({
  label,
  checked,
  onCheck,
  current,
  children,
}: {
  label: string;
  checked: boolean;
  onCheck: (v: boolean) => void;
  current: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-3 border-t border-ink-600 pt-2">
      <label className="flex items-center gap-2 text-xs font-semibold text-ink-200">
        <input type="checkbox" checked={checked} onChange={(e) => onCheck(e.target.checked)} />
        {label}
      </label>
      <div className="mt-1 text-[11px] text-ink-500">Current: {current}</div>
      <div className={`mt-1 ${checked ? "" : "pointer-events-none opacity-40"}`}>{children}</div>
    </div>
  );
}
