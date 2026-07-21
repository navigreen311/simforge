import Link from "next/link";
import { notFound } from "next/navigation";

import { TierPill } from "@/components/common/TierPill";
import { api, type PackDetail } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function PackDetailPage({ params }: { params: { packId: string } }) {
  let pack: PackDetail;
  try {
    pack = await api.pack(params.packId);
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto max-w-5xl">
      <Link href="/dashboard/packs" className="text-sm text-ink-300 hover:text-ink-100">
        ← Packs
      </Link>
      <div className="mt-2 flex items-center justify-between">
        <h1 className="text-3xl">{pack.name}</h1>
        <span className="font-mono text-sm text-ink-300">
          {pack.packId} · v{pack.version}
        </span>
      </div>

      <div className="mt-6 flex flex-wrap gap-2 text-xs">
        <span className="rounded bg-ink-600 px-2 py-1 text-ink-100">venture: {pack.ownerVenture}</span>
        <span className="rounded bg-ink-600 px-2 py-1 text-ink-100">rubric: {pack.rubricProfile}</span>
        {pack.phiRequired && <span className="rounded bg-danger/15 px-2 py-1 text-danger">PHI required</span>}
        {pack.complianceFlags.map((f) => (
          <span key={f} className="rounded bg-gold-600/15 px-2 py-1 text-gold-300">
            {f}
          </span>
        ))}
        {pack.signedBy && (
          <span className="rounded bg-success/15 px-2 py-1 text-success">signed by {pack.signedBy}</span>
        )}
      </div>

      <section className="mt-10">
        <h2 className="mb-4 text-xl">Scenarios ({pack.scenarios.length})</h2>
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-3 font-medium">Scenario</th>
                <th className="px-4 py-3 font-medium">Tier</th>
                <th className="px-4 py-3 font-medium">Tested agent</th>
                <th className="px-4 py-3 font-medium">SLO</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {pack.scenarios.map((s) => (
                <tr key={s.id} className="hover:bg-ink-800/60">
                  <td className="px-4 py-3">
                    <div className="text-ink-50">
                      {s.title}
                      {s.isGolden && <span className="ml-2 text-xs text-gold-400">★ golden</span>}
                    </div>
                    <div className="font-mono text-xs text-ink-300">{s.scenarioId}</div>
                  </td>
                  <td className="px-4 py-3">
                    <TierPill tier={s.tier} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-100">
                    {s.testedAgentVillageId}
                  </td>
                  <td className="px-4 py-3 text-ink-100">{s.sloSeconds}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
