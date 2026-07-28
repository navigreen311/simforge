"use client";

import { useMemo, useState } from "react";

import { api, type BulkImportResponse, type DepartmentSummary } from "@/lib/api/client";

const input =
  "w-full rounded border border-ink-500 bg-ink-900 px-3 py-2 text-sm text-ink-50 focus:border-gold-500 focus:outline-none";
const label = "mb-1 block text-xs font-semibold text-ink-300";

function slugify(v: string): string {
  return v.trim().toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "");
}

const FLOOR_NOTE =
  "New agents start at minimum autonomy (L1) with zero certs, and earn higher levels through certification. Adding an agent never grants autonomy or certs.";

export function AddAgentsPanel({ departments }: { departments: DepartmentSummary[] }) {
  const [tab, setTab] = useState<"single" | "bulk">("single");
  return (
    <div>
      <div className="mb-6 flex gap-2">
        {(["single", "bulk"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium ${
              tab === t
                ? "bg-gold-500 text-ink-900"
                : "border border-ink-500 text-ink-200 hover:bg-ink-700"
            }`}
          >
            {t === "single" ? "Single agent" : "Bulk import"}
          </button>
        ))}
      </div>
      <div className="mb-4 rounded border border-info/30 bg-info/5 p-3 text-xs text-info">
        {FLOOR_NOTE}
      </div>
      {tab === "single" ? (
        <SingleForm departments={departments} />
      ) : (
        <BulkImport departments={departments} />
      )}
    </div>
  );
}

function SingleForm({ departments }: { departments: DepartmentSummary[] }) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [touched, setTouched] = useState(false);
  const [role, setRole] = useState("");
  const [dept, setDept] = useState(departments[0]?.id ?? "");
  const [gardner, setGardner] = useState(false);
  const [l10, setL10] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const effSlug = touched ? slug : slugify(name);
  const valid = name.trim() !== "" && dept !== "";

  async function submit() {
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.createAgent({
        name: name.trim(),
        villageAgentId: slugify(effSlug) || null,
        role: role.trim(),
        departmentId: dept,
        gardnerFlag: gardner,
        level10Enabled: l10,
      });
      window.location.href = "/dashboard/agents";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
      setBusy(false);
    }
  }

  return (
    <div className="flex max-w-lg flex-col gap-4">
      <div>
        <label className={label}>Display name</label>
        <input className={input} value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div>
        <label className={label}>Id / slug</label>
        <input
          className={input}
          value={effSlug}
          onChange={(e) => {
            setTouched(true);
            setSlug(e.target.value);
          }}
        />
      </div>
      <div>
        <label className={label}>Role</label>
        <input className={input} value={role} onChange={(e) => setRole(e.target.value)} />
      </div>
      <div>
        <label className={label}>Department</label>
        <select className={input} value={dept} onChange={(e) => setDept(e.target.value)}>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </div>
      <div className="flex gap-4 text-sm text-ink-200">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={gardner} onChange={(e) => setGardner(e.target.checked)} />
          Gardner flag
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={l10} onChange={(e) => setL10(e.target.checked)} />
          L10 flag
        </label>
      </div>
      <div className="text-xs text-ink-500">
        Autonomy is not selectable — set to the floor automatically.
      </div>
      {error && <div className="text-xs text-danger">{error}</div>}
      <button
        onClick={submit}
        disabled={!valid || busy}
        className="self-start rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
      >
        {busy ? "Adding…" : "Add agent"}
      </button>
    </div>
  );
}

interface ParsedRow {
  name: string;
  id: string;
  role: string;
  department: string;
  flags: string;
}

const HEADERS = ["name", "id", "role", "department", "flags"];

function parseTable(text: string): ParsedRow[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (lines.length === 0) return [];
  const delim = lines[0].includes("\t") ? "\t" : ",";
  const cells = (l: string) => l.split(delim).map((c) => c.trim());
  let start = 0;
  const first = cells(lines[0]).map((c) => c.toLowerCase());
  const hasHeader = first.includes("name");
  const cols = hasHeader ? first : HEADERS;
  if (hasHeader) start = 1;
  return lines.slice(start).map((l) => {
    const c = cells(l);
    const get = (k: string) => {
      const i = cols.indexOf(k);
      return i >= 0 && i < c.length ? c[i] : "";
    };
    return {
      name: get("name"),
      id: get("id"),
      role: get("role"),
      department: get("department"),
      flags: get("flags"),
    };
  });
}

function BulkImport({ departments }: { departments: DepartmentSummary[] }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<BulkImportResponse | null>(null);

  const deptTokens = useMemo(
    () =>
      new Set(
        departments.flatMap((d) => [d.name.toLowerCase(), d.villageKey.toLowerCase(), d.id]),
      ),
    [departments],
  );

  const rows = useMemo(() => parseTable(text), [text]);
  // Client-side preview validation (server is authoritative on commit).
  const seen = new Set<string>();
  const preview = rows.map((r) => {
    const id = (r.id || slugify(r.name)).trim();
    let problem: string | null = null;
    if (!r.name.trim()) problem = "missing name";
    else if (!r.department.trim() || !deptTokens.has(r.department.trim().toLowerCase()))
      problem = `unknown department "${r.department}"`;
    else if (seen.has(id)) problem = "duplicate id in this list";
    if (id) seen.add(id);
    return { ...r, id, problem };
  });
  const validCount = preview.filter((p) => !p.problem).length;

  function template() {
    const csv = "name,id,role,department,flags\nAda Byron,,Analyst,Engineering,\n";
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "agents-template.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function onFile(f: File | null) {
    if (f) setText(await f.text());
  }

  async function importValid() {
    if (busy || rows.length === 0) return;
    setBusy(true);
    setResult(null);
    try {
      setResult(await api.bulkImportAgents(rows));
    } catch (e) {
      setResult({
        imported: 0,
        skipped: 0,
        errored: 0,
        results: [
          { index: 0, name: "", villageAgentId: null, status: "error", reason: String(e) },
        ],
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ink-300">
        Paste a table (CSV or copied spreadsheet) or upload a CSV. Columns:{" "}
        <span className="font-mono text-xs">name, id, role, department, flags</span> (id auto-derived
        if blank). Rows are validated below; only valid rows import, invalid rows are reported and
        skipped — nothing is invented.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={template} className="rounded border border-ink-500 px-3 py-1.5 text-xs text-ink-100 hover:bg-ink-700">
          ↓ Download CSV template
        </button>
        <input
          type="file"
          accept=".csv,.tsv,.txt"
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          className="text-xs text-ink-300 file:mr-2 file:rounded file:border-0 file:bg-ink-600 file:px-2 file:py-1 file:text-ink-100"
        />
      </div>
      <textarea
        className={`${input} min-h-[120px] font-mono text-xs`}
        placeholder="name,id,role,department,flags"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      {preview.length > 0 && !result && (
        <div className="rounded-lg border border-ink-500">
          <div className="border-b border-ink-600 px-3 py-2 text-xs text-ink-300">
            {validCount} of {preview.length} rows valid
          </div>
          <div className="max-h-64 overflow-auto">
            {preview.map((p, i) => (
              <div
                key={i}
                className={`flex items-center justify-between gap-2 border-b border-ink-600 px-3 py-1.5 text-xs last:border-0 ${
                  p.problem ? "bg-danger/5" : "bg-success/5"
                }`}
              >
                <span className="text-ink-100">
                  {p.name || <em className="text-ink-500">(no name)</em>}{" "}
                  <span className="font-mono text-[10px] text-ink-500">{p.id}</span>{" "}
                  <span className="text-ink-400">· {p.department}</span>
                </span>
                <span className={p.problem ? "text-danger" : "text-success"}>
                  {p.problem ? `✗ ${p.problem}` : "✓ valid"}
                </span>
              </div>
            ))}
          </div>
          <div className="px-3 py-2">
            <button
              onClick={importValid}
              disabled={busy || validCount === 0}
              className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
            >
              {busy ? "Importing…" : `Import ${validCount} valid row${validCount === 1 ? "" : "s"}`}
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-3 text-xs">
          <div className="mb-2 font-semibold text-ink-100">
            {result.imported} imported · {result.skipped} skipped · {result.errored} errored
          </div>
          <div className="max-h-64 overflow-auto">
            {result.results.map((r) => (
              <div key={r.index} className="flex justify-between gap-2 border-b border-ink-600 py-1 last:border-0">
                <span className="text-ink-200">
                  {r.name} <span className="font-mono text-[10px] text-ink-500">{r.villageAgentId}</span>
                </span>
                <span
                  className={
                    r.status === "imported"
                      ? "text-success"
                      : r.status === "skipped"
                        ? "text-warning"
                        : "text-danger"
                  }
                >
                  {r.status}
                  {r.reason ? ` — ${r.reason}` : ""}
                </span>
              </div>
            ))}
          </div>
          <a href="/dashboard/agents" className="mt-2 inline-block text-gold-400 hover:underline">
            ← Back to Agents
          </a>
        </div>
      )}
    </div>
  );
}
