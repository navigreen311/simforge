"use client";

import { useEffect, useState } from "react";

import { scenarioBank, type BankVocabulary, type ExtractResponse } from "@/lib/api/client";

import { ScenarioForm, type ScenarioFormValues } from "./ScenarioForm";

// The "New scenario" front door. Each method produces a human-reviewed DRAFT — never a commit.
//  - Manual   : author a scenario by hand (no LLM).
//  - Paste    : paste text → LLM extracts a candidate → you review it in the form.
//  - Document : upload PDF/DOCX/TXT/MD → text extracted → same LLM candidate → review.
//  - Web/Video: honest "pending dependency" stubs — no fake pipeline.

type Method = "manual" | "paste" | "document" | "web" | "video";

const METHODS: { id: Method; label: string; enabled: boolean; note?: string }[] = [
  { id: "manual", label: "Manual author", enabled: true },
  { id: "paste", label: "Paste text", enabled: true },
  { id: "document", label: "Document upload", enabled: true },
  { id: "web", label: "Web search", enabled: false, note: "web search API" },
  { id: "video", label: "Video / YouTube", enabled: false, note: "transcription" },
];

function candidateToValues(r: ExtractResponse): Partial<ScenarioFormValues> | undefined {
  if (!r.scenario) return undefined;
  return {
    title: r.scenario.title,
    pack: r.scenario.pack,
    family: r.scenario.family,
    tier: r.scenario.tier,
    situation: r.scenario.situation,
    expectedBehaviors: r.scenario.expected_behaviors,
    adversarialTactics: r.scenario.adversarial_tactics,
    jurisdictionFlags: r.scenario.jurisdiction_flags,
  };
}

export function IngestionPanel() {
  const [vocab, setVocab] = useState<BankVocabulary | null>(null);
  const [method, setMethod] = useState<Method>("manual");

  useEffect(() => {
    scenarioBank.vocabulary().then(setVocab).catch(() => setVocab(null));
  }, []);

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {METHODS.map((m) => (
          <button
            key={m.id}
            onClick={() => setMethod(m.id)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              method === m.id
                ? "bg-gold-500 text-ink-900"
                : "border border-ink-500 text-ink-200 hover:bg-ink-700"
            }`}
          >
            {m.label}
            {!m.enabled && <span className="ml-1 opacity-60">·pending</span>}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {!vocab && (method === "manual" || method === "paste" || method === "document") && (
          <p className="text-sm text-ink-400">Loading vocabulary…</p>
        )}
        {vocab && method === "manual" && (
          <ManualTab vocab={vocab} />
        )}
        {vocab && method === "paste" && <PasteTab vocab={vocab} />}
        {vocab && method === "document" && <DocumentTab vocab={vocab} />}
        {method === "web" && <PendingStub dependency="a web search API" />}
        {method === "video" && <PendingStub dependency="audio transcription / a YouTube fetcher" />}
      </div>
    </div>
  );
}

function ManualTab({ vocab }: { vocab: BankVocabulary }) {
  return (
    <div>
      <p className="mb-4 text-sm text-ink-300">
        Write a scenario by hand. It saves as a draft you can commit later.
      </p>
      <ScenarioForm
        vocab={vocab}
        aiDrafted={false}
        sourceType="manual"
        submitLabel="Save draft"
        onSaved={async (body) => (await scenarioBank.createDraft(body)).publicId}
      />
    </div>
  );
}

function PasteTab({ vocab }: { vocab: BankVocabulary }) {
  const [text, setText] = useState("");
  const [ref, setRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ExtractResponse | null>(null);

  async function run() {
    if (!text.trim() || busy) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await scenarioBank.extract({
        source_text: text,
        source_type: "paste",
        source_ref: ref.trim() || null,
      });
      setResult(r);
    } catch (e) {
      setResult({
        ok: false,
        error: e instanceof Error ? e.message : "Extraction failed",
        confidence: null,
        scenario: null,
        source_excerpt: null,
        source_ref: null,
      });
    } finally {
      setBusy(false);
    }
  }

  const values = result?.ok ? candidateToValues(result) : undefined;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ink-300">
        Paste an incident write-up, transcript, or article. The LLM proposes a scenario candidate;
        you review and correct it before saving. Nothing is saved until you do.
      </p>
      <textarea
        className="min-h-[160px] w-full rounded border border-ink-500 bg-ink-900 px-3 py-2 text-sm text-ink-50 focus:border-gold-500 focus:outline-none"
        placeholder="Paste source text here…"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <input
        className="w-full rounded border border-ink-500 bg-ink-900 px-3 py-2 text-sm text-ink-50 focus:border-gold-500 focus:outline-none"
        placeholder="Source reference (optional URL/citation)"
        value={ref}
        onChange={(e) => setRef(e.target.value)}
      />
      <div>
        <button
          onClick={run}
          disabled={!text.trim() || busy}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
        >
          {busy ? "Extracting…" : "Extract scenario"}
        </button>
      </div>

      {result && !result.ok && <ExtractError error={result.error} />}
      {result?.ok && values && (
        <ReviewBlock
          confidence={result.confidence}
          form={
            <ScenarioForm
              vocab={vocab}
              initial={values}
              aiDrafted
              sourceType="paste"
              sourceRef={result.source_ref}
              sourceExcerpt={result.source_excerpt}
              submitLabel="Approve & save draft"
              onSaved={async (body) => (await scenarioBank.createDraft(body)).publicId}
            />
          }
        />
      )}
    </div>
  );
}

function DocumentTab({ vocab }: { vocab: BankVocabulary }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ExtractResponse | null>(null);

  async function run() {
    if (!file || busy) return;
    setBusy(true);
    setResult(null);
    try {
      setResult(await scenarioBank.extractDocument(file));
    } catch (e) {
      setResult({
        ok: false,
        error: e instanceof Error ? e.message : "Extraction failed",
        confidence: null,
        scenario: null,
        source_excerpt: null,
        source_ref: null,
      });
    } finally {
      setBusy(false);
    }
  }

  const values = result?.ok ? candidateToValues(result) : undefined;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ink-300">
        Upload a PDF, DOCX, TXT, or MD file. Text is extracted server-side, then the same LLM
        proposes a candidate for your review. No OCR — a scanned/image-only PDF is reported as such,
        not invented.
      </p>
      <input
        type="file"
        accept=".pdf,.docx,.txt,.md,.markdown,.rst"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="text-sm text-ink-200 file:mr-3 file:rounded file:border-0 file:bg-ink-600 file:px-3 file:py-1.5 file:text-ink-100"
      />
      <div>
        <button
          onClick={run}
          disabled={!file || busy}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
        >
          {busy ? "Reading…" : "Extract from document"}
        </button>
      </div>

      {result && !result.ok && <ExtractError error={result.error} />}
      {result?.ok && values && (
        <ReviewBlock
          confidence={result.confidence}
          form={
            <ScenarioForm
              vocab={vocab}
              initial={values}
              aiDrafted
              sourceType="document"
              sourceRef={result.source_ref}
              sourceExcerpt={result.source_excerpt}
              submitLabel="Approve & save draft"
              onSaved={async (body) => (await scenarioBank.createDraft(body)).publicId}
            />
          }
        />
      )}
    </div>
  );
}

function ExtractError({ error }: { error: string | null }) {
  return (
    <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
      <strong>No scenario was created.</strong>
      <p className="mt-1 text-xs">{error}</p>
      <p className="mt-2 text-xs text-ink-400">
        The system does not invent content to fill a gap. If the source has no usable scenario — or
        the dev environment is using the offline stub LLM — nothing is saved.
      </p>
    </div>
  );
}

function ReviewBlock({ confidence, form }: { confidence: number | null; form: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-ink-500 bg-ink-800 p-4">
      <div className="mb-3 flex items-center gap-2 text-xs">
        <span className="font-semibold text-info">Candidate ready for review</span>
        {confidence != null && (
          <span
            className={`rounded px-2 py-0.5 ${
              confidence < 0.5 ? "bg-warning/20 text-warning" : "bg-ink-600 text-ink-200"
            }`}
          >
            model confidence {(confidence * 100).toFixed(0)}%
            {confidence < 0.5 && " · low"}
          </span>
        )}
      </div>
      {form}
    </div>
  );
}

function PendingStub({ dependency }: { dependency: string }) {
  return (
    <div className="rounded-lg border border-ink-500 bg-ink-800 p-6">
      <div className="inline-block rounded bg-ink-700 px-2 py-0.5 text-[10px] uppercase tracking-wide text-ink-400">
        Pending dependency
      </div>
      <h3 className="mt-3 text-lg text-ink-100">Not yet available</h3>
      <p className="mt-2 max-w-prose text-sm text-ink-300">
        This ingestion method needs {dependency}, which is not configured in this deployment. It is
        intentionally shipped as a stub — there is no hidden or fake pipeline behind it. Once the
        dependency is verified, this method will use the exact same review-then-commit flow: every
        result lands as a draft for a human to approve.
      </p>
    </div>
  );
}
