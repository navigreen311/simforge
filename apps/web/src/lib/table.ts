// Pure, framework-free table helpers (search / sort / paginate) for DataTable.
// Kept separate from the React component so they're unit-testable without a DOM (UI P0 audit).

export type SortDir = "asc" | "desc";

/** Rows whose searchable text contains every whitespace-separated token of `term` (case-insensitive). */
export function applySearch<T>(rows: T[], term: string, searchText: (row: T) => string): T[] {
  const q = term.trim().toLowerCase();
  if (!q) return rows;
  const tokens = q.split(/\s+/);
  return rows.filter((row) => {
    const hay = searchText(row).toLowerCase();
    return tokens.every((t) => hay.includes(t));
  });
}

/** Stable sort by a comparable value; null/undefined always sort last regardless of direction. */
export function applySort<T>(
  rows: T[],
  sortValue: ((row: T) => string | number | null | undefined) | null,
  dir: SortDir,
): T[] {
  if (!sortValue) return rows;
  const indexed = rows.map((row, i) => ({ row, i }));
  indexed.sort((a, b) => {
    const va = sortValue(a.row);
    const vb = sortValue(b.row);
    const an = va === null || va === undefined;
    const bn = vb === null || vb === undefined;
    if (an && bn) return a.i - b.i;
    if (an) return 1; // nulls last
    if (bn) return -1;
    let cmp: number;
    if (typeof va === "number" && typeof vb === "number") cmp = va - vb;
    else cmp = String(va).localeCompare(String(vb));
    if (cmp === 0) return a.i - b.i; // stable
    return dir === "asc" ? cmp : -cmp;
  });
  return indexed.map((x) => x.row);
}

export function pageCount(total: number, pageSize: number): number {
  if (pageSize <= 0) return 1;
  return Math.max(1, Math.ceil(total / pageSize));
}

/** 1-indexed page slice. `pageSize <= 0` means "all rows on one page". */
export function paginate<T>(rows: T[], page: number, pageSize: number): T[] {
  if (pageSize <= 0) return rows;
  const start = (page - 1) * pageSize;
  return rows.slice(start, start + pageSize);
}
