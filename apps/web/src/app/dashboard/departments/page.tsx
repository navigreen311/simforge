import { api, type DepartmentSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function DepartmentsPage() {
  let departments: DepartmentSummary[] = [];
  let error: string | null = null;

  try {
    departments = (await api.departments()).items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load departments";
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-1 text-3xl">Departments</h1>
      <p className="mb-8 text-ink-200">Village departments and their agent headcount.</p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load departments: <code className="text-danger">{error}</code>
        </div>
      ) : departments.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No departments registered.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {departments.map((d) => (
            <div key={d.id} className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="flex items-baseline justify-between">
                <span className="text-lg text-ink-50">{d.name}</span>
                <span className="font-display text-2xl text-gold-500">{d.totalAgents}</span>
              </div>
              <div className="mt-1 font-mono text-xs text-ink-300">{d.villageKey}</div>
              <div className="mt-1 text-xs text-ink-400">
                {d.totalAgents} agent{d.totalAgents === 1 ? "" : "s"}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
