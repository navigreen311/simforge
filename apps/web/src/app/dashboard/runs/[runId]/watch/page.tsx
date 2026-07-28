import Link from "next/link";

import { LiveRunMonitor } from "@/components/runs/LiveRunMonitor";

export const dynamic = "force-dynamic";

export default function WatchRunPage({
  params,
  searchParams,
}: {
  params: { runId: string };
  searchParams: { agent?: string };
}) {
  const backHref = searchParams.agent
    ? `/dashboard/runs?agent=${searchParams.agent}`
    : "/dashboard/agents";
  return (
    <div className="mx-auto max-w-4xl">
      <Link href="/dashboard/agents" className="text-sm text-ink-300 hover:text-ink-100">
        ← Agents
      </Link>
      <h1 className="mt-2 mb-4 text-3xl">Live run monitor</h1>
      <LiveRunMonitor runId={params.runId} backHref={backHref} />
    </div>
  );
}
