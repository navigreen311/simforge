"use client";

import { type ReactNode, useMemo, useState } from "react";

import { applySearch, applySort, paginate, pageCount, type SortDir } from "@/lib/table";

export interface Column<T> {
  key: string;
  header: string;
  /** Cell renderer. */
  cell: (row: T) => ReactNode;
  /** Sortable when provided — returns the comparable value. */
  sortValue?: (row: T) => string | number | null | undefined;
  /** Contributes this row's text to the global search box. */
  searchText?: (row: T) => string;
  /** Renders a filter <select> in the toolbar; `match` decides inclusion. */
  filter?: { label: string; options: { label: string; value: string }[]; match: (row: T, value: string) => boolean };
  align?: "left" | "right";
  className?: string;
}

const PAGE_SIZES = [25, 50, 100, 0]; // 0 = All

export function DataTable<T>({
  columns,
  data,
  getRowKey,
  onRowClick,
  emptyState,
  searchPlaceholder = "Search…",
  initialPageSize = 25,
  toolbarExtra,
}: {
  columns: Column<T>[];
  data: T[];
  getRowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyState?: ReactNode;
  searchPlaceholder?: string;
  initialPageSize?: number;
  toolbarExtra?: ReactNode;
}) {
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);

  const searchable = columns.filter((c) => c.searchText);
  const filterable = columns.filter((c) => c.filter);

  const processed = useMemo(() => {
    let rows = data;
    for (const col of filterable) {
      const val = filters[col.key];
      if (val) rows = rows.filter((r) => col.filter!.match(r, val));
    }
    if (search && searchable.length) {
      rows = applySearch(rows, search, (r) => searchable.map((c) => c.searchText!(r)).join(" "));
    }
    const sortCol = columns.find((c) => c.key === sortKey);
    rows = applySort(rows, sortCol?.sortValue ?? null, sortDir);
    return rows;
  }, [data, filters, search, sortKey, sortDir, columns, filterable, searchable]);

  const total = processed.length;
  const pages = pageCount(total, pageSize);
  const current = Math.min(page, pages);
  const rows = paginate(processed, current, pageSize);

  function toggleSort(col: Column<T>) {
    if (!col.sortValue) return;
    if (sortKey === col.key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(col.key);
      setSortDir("asc");
    }
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        {searchable.length > 0 && (
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder={searchPlaceholder}
            className="min-w-[14rem] flex-1 rounded border border-ink-500 bg-ink-800 px-3 py-1.5 text-sm text-ink-50 placeholder:text-ink-400"
          />
        )}
        {filterable.map((col) => (
          <select
            key={col.key}
            value={filters[col.key] ?? ""}
            onChange={(e) => {
              setFilters((f) => ({ ...f, [col.key]: e.target.value }));
              setPage(1);
            }}
            className="rounded border border-ink-500 bg-ink-800 px-2 py-1.5 text-xs text-ink-100"
          >
            <option value="">{col.filter!.label}: all</option>
            {col.filter!.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        ))}
        {toolbarExtra}
        <span className="ml-auto text-xs text-ink-400">{total} rows</span>
      </div>

      {/* Table */}
      {total === 0 ? (
        emptyState ?? (
          <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-center text-ink-300">
            No matching rows.
          </div>
        )
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="sticky top-0 z-10 bg-ink-800 text-ink-200">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => toggleSort(col)}
                    className={`px-4 py-3 font-medium ${col.align === "right" ? "text-right" : ""} ${
                      col.sortValue ? "cursor-pointer select-none hover:text-ink-50" : ""
                    }`}
                  >
                    {col.header}
                    {sortKey === col.key && <span className="ml-1 text-gold-400">{sortDir === "asc" ? "▲" : "▼"}</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {rows.map((row) => (
                <tr
                  key={getRowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={`hover:bg-ink-800/60 ${onRowClick ? "cursor-pointer" : ""}`}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-4 py-3 ${col.align === "right" ? "text-right" : ""} ${col.className ?? ""}`}
                    >
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > 0 && (
        <div className="flex flex-wrap items-center gap-3 text-xs text-ink-300">
          <label className="flex items-center gap-1">
            Rows:
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="rounded border border-ink-500 bg-ink-800 px-2 py-1 text-ink-100"
            >
              {PAGE_SIZES.map((s) => (
                <option key={s} value={s}>
                  {s === 0 ? "All" : s}
                </option>
              ))}
            </select>
          </label>
          {pageSize > 0 && (
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={current <= 1}
                className="rounded border border-ink-500 px-2 py-1 disabled:opacity-40"
              >
                Prev
              </button>
              <span>
                Page {current} of {pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(pages, p + 1))}
                disabled={current >= pages}
                className="rounded border border-ink-500 px-2 py-1 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
