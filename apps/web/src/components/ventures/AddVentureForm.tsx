"use client";

import { useEffect, useState } from "react";

import { api, ventures as venturesApi, type FlagCatalog } from "@/lib/api/client";

const input =
  "w-full rounded border border-ink-500 bg-ink-900 px-3 py-2 text-sm text-ink-50 focus:border-gold-500 focus:outline-none";
const label = "mb-1 block text-xs font-semibold text-ink-300";

function slugify(v: string): string {
  return v.trim().toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
}

export function AddVentureForm() {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("in_development");
  const [flags, setFlags] = useState<string[]>([]);
  const [flagVocab, setFlagVocab] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<FlagCatalog | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.authoringOptions().then((o) => setFlagVocab(o.jurisdiction_flags)).catch(() => {});
    api.flagCatalog().then(setCatalog).catch(() => {});
  }, []);

  const effectiveSlug = slugTouched ? slug : slugify(name);
  const valid = name.trim() !== "" && slugify(effectiveSlug) !== "";

  function toggle(f: string) {
    setFlags((cur) => (cur.includes(f) ? cur.filter((x) => x !== f) : [...cur, f]));
  }

  async function submit() {
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      const v = await venturesApi.create({
        name: name.trim(),
        slug: slugify(effectiveSlug),
        description: description.trim(),
        status,
        defaultComplianceFlags: flags,
      });
      window.location.href = `/dashboard/ventures/${v.slug}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <label className={label}>Name</label>
        <input
          className={input}
          placeholder="e.g. Wexford Labs"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <div>
        <label className={label}>Slug (machine id)</label>
        <input
          className={input}
          value={effectiveSlug}
          onChange={(e) => {
            setSlugTouched(true);
            setSlug(e.target.value);
          }}
        />
        <p className="mt-1 text-xs text-ink-500">
          Lowercase letters, numbers, hyphens. Used everywhere the venture is referenced.
        </p>
      </div>
      <div>
        <label className={label}>Description</label>
        <textarea
          className={`${input} min-h-[80px]`}
          placeholder="What this venture does (plain language)."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <div>
        <label className={label}>Status</label>
        <select className={input} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="in_development">In development</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
      </div>
      <div>
        <label className={label}>Default compliance flags (from the Jurisdiction engine)</label>
        <div className="flex flex-wrap gap-2">
          {flagVocab.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => toggle(f)}
              title={catalog?.flags[f]?.tooltip}
              className={`rounded px-2 py-1 text-xs ${
                flags.includes(f)
                  ? "bg-gold-500 text-ink-900"
                  : "border border-ink-500 text-ink-200 hover:bg-ink-700"
              }`}
            >
              {catalog?.flags[f]?.label ?? f}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-ink-500">
          Capabilities and internal Forges are left empty — populate them by uploading a spec or
          editing later. An empty venture is fine.
        </p>
      </div>

      {error && (
        <div className="rounded border border-danger/40 bg-danger/10 p-2 text-xs text-danger">
          {error}
        </div>
      )}
      <button
        onClick={submit}
        disabled={!valid || busy}
        className="self-start rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
      >
        {busy ? "Creating…" : "Create venture"}
      </button>
    </div>
  );
}
