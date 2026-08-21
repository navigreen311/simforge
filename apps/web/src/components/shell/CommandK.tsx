"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api/client";

type Item = { id: string; label: string; sublabel?: string; group: string; href: string };

const PAGES: Item[] = [
  ["Overview", "/dashboard"],
  ["Readiness Matrix", "/dashboard/readiness"],
  ["Runs", "/dashboard/runs"],
  ["Packs", "/dashboard/packs"],
  ["Certifications", "/dashboard/certs"],
  ["Operation Certs", "/dashboard/operation-certs"],
  ["Agents", "/dashboard/agents"],
  ["Departments", "/dashboard/departments"],
  ["Cohort Analytics", "/dashboard/cohort"],
  ["Incident Command", "/dashboard/incident"],
  ["Policy (PDP)", "/dashboard/policy"],
  ["Integrated Execution", "/dashboard/execution"],
  ["Drift Canary", "/dashboard/drift"],
  ["Jurisdictions", "/dashboard/jurisdictions"],
  ["Meta-Eval", "/dashboard/meta-eval"],
  ["Golden Benchmark", "/dashboard/golden"],
  ["Adversarial", "/dashboard/adversarial"],
  ["Agent Training", "/dashboard/training"],
  ["Gaps", "/dashboard/gaps/software"],
  ["Constitution", "/dashboard/constitution"],
  ["Lineage", "/dashboard/lineage"],
  ["Narrative", "/dashboard/narrative"],
].map(([label, href]) => ({ id: href, label, group: "Pages", href }));

const RECENT_KEY = "simforge.cmdk_recent_v1";

export function CommandK() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [dynamic, setDynamic] = useState<Item[]>([]);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Global ⌘K / Ctrl+K listener.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Lazy-load agents + packs the first time the palette opens.
  useEffect(() => {
    if (!open || dynamic.length > 0) return;
    (async () => {
      const items: Item[] = [];
      try {
        const agents = await api.agents({ page_size: 500 });
        for (const a of agents.items) {
          items.push({
            id: `agent:${a.villageAgentId}`,
            label: a.villageAgentId,
            sublabel: `${a.name} · ${a.role}`,
            group: "Agents",
            href: `/dashboard/runs?agent=${a.villageAgentId}`,
          });
        }
      } catch {
        /* ignore */
      }
      try {
        const packs = await api.packs();
        for (const p of packs.items) {
          items.push({
            id: `pack:${p.packId}`,
            label: p.packId,
            sublabel: p.name,
            group: "Packs",
            href: `/dashboard/packs/${p.packId}`,
          });
        }
      } catch {
        /* ignore */
      }
      setDynamic(items);
    })();
  }, [open, dynamic.length]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0);
    else {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  const all = useMemo(() => [...PAGES, ...dynamic], [dynamic]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      // Recently visited first, then pages.
      let recent: string[] = [];
      try {
        recent = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
      } catch {
        recent = [];
      }
      const recents = recent.map((id) => all.find((i) => i.id === id)).filter(Boolean) as Item[];
      const rest = PAGES.filter((p) => !recent.includes(p.id));
      return [...recents, ...rest].slice(0, 12);
    }
    const tokens = q.split(/\s+/);
    return all
      .filter((i) => {
        const hay = `${i.label} ${i.sublabel ?? ""}`.toLowerCase();
        return tokens.every((t) => hay.includes(t));
      })
      .slice(0, 30);
  }, [query, all]);

  const go = useCallback(
    (item: Item) => {
      try {
        const recent: string[] = JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
        localStorage.setItem(
          RECENT_KEY,
          JSON.stringify([item.id, ...recent.filter((r) => r !== item.id)].slice(0, 6)),
        );
      } catch {
        /* ignore */
      }
      setOpen(false);
      router.push(item.href);
    },
    [router],
  );

  if (!open) return null;

  const grouped = results.reduce<Record<string, Item[]>>((acc, item) => {
    (acc[item.group] ??= []).push(item);
    return acc;
  }, {});

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[12vh]"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-xl border border-ink-500 bg-ink-800 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(results.length - 1, a + 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(0, a - 1));
            } else if (e.key === "Enter" && results[active]) {
              go(results[active]);
            }
          }}
          placeholder="Search pages, agents, packs…"
          className="w-full border-b border-ink-600 bg-transparent px-4 py-3 text-sm text-ink-50 outline-none placeholder:text-ink-400"
        />
        <div className="max-h-[50vh] overflow-y-auto p-2">
          {results.length === 0 ? (
            <div className="px-3 py-6 text-center text-sm text-ink-400">No results</div>
          ) : (
            Object.entries(grouped).map(([group, items]) => (
              <div key={group} className="mb-1">
                <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-ink-400">
                  {group}
                </div>
                {items.map((item) => {
                  const idx = results.indexOf(item);
                  return (
                    <button
                      key={item.id}
                      onMouseEnter={() => setActive(idx)}
                      onClick={() => go(item)}
                      className={`flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm ${
                        idx === active ? "bg-ink-600 text-ink-50" : "text-ink-100 hover:bg-ink-700"
                      }`}
                    >
                      <span className="font-mono">{item.label}</span>
                      {item.sublabel && (
                        <span className="truncate text-xs text-ink-400">{item.sublabel}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
        <div className="border-t border-ink-600 px-3 py-1.5 text-[10px] text-ink-400">
          ↑↓ navigate · ↵ open · esc close
        </div>
      </div>
    </div>
  );
}
