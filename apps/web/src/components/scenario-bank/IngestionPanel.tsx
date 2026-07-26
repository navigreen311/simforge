"use client";

import { useEffect, useState } from "react";

import {
  scenarioBank,
  type BankVocabulary,
  type ExtractResponse,
  type WebSearchResponse,
  type WebSearchResult,
} from "@/lib/api/client";

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
  { id: "web", label: "Web search", enabled: true },
  { id: "video", label: "Video / YouTube", enabled: false, note: "transcription" },
];

function candidateToValues(r: ExtractResponse): Partial<ScenarioFormValues> | undefined {
  if (!r.scenario) return undefined;
  return {
    title: r.scenario.title,
    // null (unmapped) → undefined so the form falls back to its default; the human then confirms.
    pack: r.scenario.pack ?? undefined,
    family: r.scenario.family ?? undefined,
    tier: r.scenario.tier ?? undefined,
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
        {vocab && method === "web" && <WebSearchTab vocab={vocab} />}
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
          unmapped={result.scenario?.unmapped_fields}
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
          unmapped={result.scenario?.unmapped_fields}
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

function WebSearchTab({ vocab }: { vocab: BankVocabulary }) {
  const [status, setStatus] = useState<"checking" | "available" | "unavailable">("checking");
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [response, setResponse] = useState<WebSearchResponse | null>(null);
  const [chosen, setChosen] = useState<WebSearchResult | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extract, setExtract] = useState<ExtractResponse | null>(null);

  useEffect(() => {
    scenarioBank
      .webSearchStatus()
      .then((s) => setStatus(s.available ? "available" : "unavailable"))
      .catch(() => setStatus("unavailable"));
  }, []);

  async function runSearch() {
    if (!query.trim() || searching) return;
    setSearching(true);
    setResponse(null);
    setChosen(null);
    setExtract(null);
    try {
      const r = await scenarioBank.webSearch(query);
      setResponse(r);
      if (!r.available) setStatus("unavailable");
    } catch (e) {
      setResponse({
        available: true,
        provider: "",
        query,
        results: [],
        error: e instanceof Error ? e.message : "Search failed",
      });
    } finally {
      setSearching(false);
    }
  }

  async function chooseSource(r: WebSearchResult) {
    setChosen(r);
    setExtracting(true);
    setExtract(null);
    try {
      const res = await scenarioBank.extract({
        source_text: r.content,
        source_type: "web",
        source_ref: r.url,
      });
      setExtract(res);
    } catch (e) {
      setExtract({
        ok: false,
        error: e instanceof Error ? e.message : "Extraction failed",
        confidence: null,
        scenario: null,
        source_excerpt: null,
        source_ref: null,
      });
    } finally {
      setExtracting(false);
    }
  }

  if (status === "checking") return <p className="text-sm text-ink-400">Checking availability…</p>;
  if (status === "unavailable")
    return (
      <PendingStub
        dependency="a web-search provider key"
        detail="Set WEB_SEARCH_PROVIDER=tavily and TAVILY_API_KEY to enable live web ingestion. Until then this is not configured — no results are fabricated."
      />
    );

  const values = extract?.ok ? candidateToValues(extract) : undefined;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ink-300">
        Search the web for real-world sources (enforcement actions, incident reports, articles). Pick
        a result to extract a scenario candidate; you review and correct it before saving. Nothing is
        saved until you do.
      </p>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-ink-500 bg-ink-900 px-3 py-2 text-sm text-ink-50 focus:border-gold-500 focus:outline-none"
          placeholder="e.g. HIPAA breach home-health agency enforcement 2024"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runSearch()}
        />
        <button
          onClick={runSearch}
          disabled={!query.trim() || searching}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
        >
          {searching ? "Searching…" : "Search"}
        </button>
      </div>

      {response?.error && <ExtractError error={response.error} />}

      {response && response.results.length > 0 && !chosen && (
        <ul className="flex flex-col gap-2">
          {response.results.map((r) => (
            <li
              key={r.url}
              className="rounded-lg border border-ink-500 bg-ink-800 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-gold-400 hover:underline"
                  >
                    {r.title}
                  </a>
                  <div className="truncate font-mono text-[11px] text-ink-500">{r.url}</div>
                  <p className="mt-1 line-clamp-2 text-xs text-ink-300">{r.snippet}</p>
                  <div className="mt-1 text-[10px] text-ink-500">
                    {r.content_chars.toLocaleString()} chars of source text
                    {r.published_date ? ` · ${r.published_date}` : ""}
                  </div>
                </div>
                <button
                  onClick={() => chooseSource(r)}
                  disabled={r.content_chars === 0}
                  className="shrink-0 rounded border border-ink-500 px-3 py-1.5 text-xs text-ink-100 hover:bg-ink-700 disabled:opacity-40"
                >
                  Use this source
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {chosen && (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="min-w-0 text-xs">
              <span className="text-ink-400">Extracting from:</span>{" "}
              <span className="font-mono text-ink-200">{chosen.url}</span>
            </div>
            <button
              onClick={() => {
                setChosen(null);
                setExtract(null);
              }}
              className="shrink-0 text-xs text-ink-400 hover:text-ink-200"
            >
              ← back to results
            </button>
          </div>
          {extracting && <p className="text-sm text-ink-400">Extracting…</p>}
          {extract && !extract.ok && <ExtractError error={extract.error} />}
          {extract?.ok && values && (
            <ReviewBlock
              confidence={extract.confidence}
              unmapped={extract.scenario?.unmapped_fields}
              form={
                <ScenarioForm
                  vocab={vocab}
                  initial={values}
                  aiDrafted
                  sourceType="web"
                  sourceRef={extract.source_ref ?? chosen.url}
                  sourceExcerpt={extract.source_excerpt}
                  submitLabel="Approve & save draft"
                  onSaved={async (body) => (await scenarioBank.createDraft(body)).publicId}
                />
              }
            />
          )}
        </div>
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

function ReviewBlock({
  confidence,
  unmapped,
  form,
}: {
  confidence: number | null;
  unmapped?: string[];
  form: React.ReactNode;
}) {
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
      {unmapped && unmapped.length > 0 && (
        <div className="mb-3 rounded border border-warning/40 bg-warning/10 p-2 text-xs text-warning">
          The model couldn&apos;t confidently map: <strong>{unmapped.join(", ")}</strong>. Please
          pick {unmapped.length > 1 ? "these" : "this"} below before saving.
        </div>
      )}
      {form}
    </div>
  );
}

function PendingStub({ dependency, detail }: { dependency: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-ink-500 bg-ink-800 p-6">
      <div className="inline-block rounded bg-ink-700 px-2 py-0.5 text-[10px] uppercase tracking-wide text-ink-400">
        Pending dependency
      </div>
      <h3 className="mt-3 text-lg text-ink-100">Not yet available</h3>
      <p className="mt-2 max-w-prose text-sm text-ink-300">
        {detail ??
          `This ingestion method needs ${dependency}, which is not configured in this deployment. It is intentionally shipped as a stub — there is no hidden or fake pipeline behind it. Once the dependency is verified, this method will use the exact same review-then-commit flow: every result lands as a draft for a human to approve.`}
      </p>
    </div>
  );
}
