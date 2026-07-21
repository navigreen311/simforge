import { governance, type Amendment, type ConstitutionCurrent } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const STATUS_STYLE: Record<string, string> = {
  in_cooling: "bg-warning/20 text-warning",
  ratified: "bg-success/15 text-success",
  withdrawn: "bg-ink-600 text-ink-300",
  vetoed: "bg-danger/15 text-danger",
};

export default async function ConstitutionPage() {
  let current: ConstitutionCurrent | null = null;
  let amendments: Amendment[] = [];
  let error: string | null = null;
  try {
    current = await governance.current();
  } catch {
    current = null;
  }
  try {
    amendments = (await governance.history()).amendments;
  } catch (e) {
    error = e instanceof Error ? e.message : null;
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-1 text-3xl">Constitution</h1>
      <p className="mb-8 text-ink-200">
        The governing document for agent certification and autonomy. Amendments require a cooling
        period + Ivan ratification.
      </p>

      {current ? (
        <div className="rounded-xl border border-gold-700 bg-gold-900/10 p-5">
          <div className="flex items-center justify-between">
            <span className="font-display text-2xl text-gold-500">{current.version}</span>
            <span className="rounded bg-success/15 px-3 py-1 text-sm text-success">active</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-ink-100">
            <div>Ratified by: {current.ratified_by}</div>
            <div>Ratified: {new Date(current.ratified_at).toLocaleDateString()}</div>
            <div className="col-span-2 font-mono text-xs text-ink-300">
              hash {current.content_hash.slice(0, 24)}…
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No constitution ratified yet. Seed it with{" "}
          <code>python scripts/seed-constitution.py</code>.
        </div>
      )}

      <section className="mt-10">
        <h2 className="mb-4 text-xl">Amendments</h2>
        {error ? (
          <div className="text-sm text-danger">{error}</div>
        ) : amendments.length === 0 ? (
          <p className="text-ink-300">No amendments proposed.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {amendments.map((a) => (
              <div
                key={a.amendment_id}
                className="flex items-center gap-3 rounded-lg border border-ink-500 bg-ink-800 px-4 py-3 text-sm"
              >
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium ${
                    STATUS_STYLE[a.status] ?? "bg-ink-600"
                  }`}
                >
                  {a.status}
                </span>
                <span className="flex-1 font-mono text-xs text-ink-200">{a.amendment_id}</span>
                <span className="text-ink-300">by {a.proposed_by}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
