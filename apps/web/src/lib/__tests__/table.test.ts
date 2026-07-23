import { describe, expect, it } from "vitest";

import { applySearch, applySort, pageCount, paginate } from "@/lib/table";

type Row = { id: number; name: string; score: number | null };

const rows: Row[] = [
  { id: 1, name: "David Kim", score: 0.9 },
  { id: 2, name: "Jennifer Adams", score: 0.5 },
  { id: 3, name: "Taylor Zhang", score: null },
  { id: 4, name: "david clone", score: 0.7 },
];

describe("applySearch", () => {
  it("matches case-insensitively across tokens", () => {
    const out = applySearch(rows, "david", (r) => r.name);
    expect(out.map((r) => r.id)).toEqual([1, 4]);
  });
  it("requires every token to match", () => {
    const out = applySearch(rows, "david kim", (r) => r.name);
    expect(out.map((r) => r.id)).toEqual([1]);
  });
  it("empty term returns all rows", () => {
    expect(applySearch(rows, "  ", (r) => r.name)).toHaveLength(4);
  });
});

describe("applySort", () => {
  it("sorts numbers ascending with nulls last", () => {
    const out = applySort(rows, (r) => r.score, "asc");
    expect(out.map((r) => r.id)).toEqual([2, 4, 1, 3]);
  });
  it("sorts numbers descending with nulls still last", () => {
    const out = applySort(rows, (r) => r.score, "desc");
    expect(out.map((r) => r.id)).toEqual([1, 4, 2, 3]);
  });
  it("sorts strings", () => {
    const out = applySort(rows, (r) => r.name, "asc");
    expect(out.map((r) => r.name)[0]).toBe("david clone");
  });
  it("null sortValue is a no-op", () => {
    expect(applySort(rows, null, "asc")).toEqual(rows);
  });
});

describe("paginate + pageCount", () => {
  it("slices a 1-indexed page", () => {
    expect(paginate(rows, 1, 2).map((r) => r.id)).toEqual([1, 2]);
    expect(paginate(rows, 2, 2).map((r) => r.id)).toEqual([3, 4]);
  });
  it("pageSize <= 0 means all on one page", () => {
    expect(paginate(rows, 1, 0)).toHaveLength(4);
    expect(pageCount(4, 0)).toBe(1);
  });
  it("computes page count", () => {
    expect(pageCount(4, 2)).toBe(2);
    expect(pageCount(5, 2)).toBe(3);
    expect(pageCount(0, 25)).toBe(1);
  });
});

describe("empty data", () => {
  it("search/sort/paginate on empty stay empty", () => {
    expect(applySearch([], "x", () => "")).toEqual([]);
    expect(applySort([], (r) => r, "asc")).toEqual([]);
    expect(paginate([], 1, 25)).toEqual([]);
  });
});
