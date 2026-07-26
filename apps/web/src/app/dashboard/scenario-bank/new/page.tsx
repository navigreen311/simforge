import Link from "next/link";

import { IngestionPanel } from "@/components/scenario-bank/IngestionPanel";

export const dynamic = "force-dynamic";

// Every method here produces a human-reviewed DRAFT. Nothing enters certification automatically —
// committing a scenario is a separate, explicit action on its detail page.
export default function NewScenarioPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <Link href="/dashboard/scenario-bank" className="text-sm text-ink-300 hover:text-ink-100">
        ← Scenario Bank
      </Link>
      <h1 className="mt-2 text-3xl">New scenario</h1>
      <p className="mt-3 max-w-prose text-ink-200">
        Create a scenario by hand, or from a pasted passage or an uploaded document. Every method
        produces a <strong>draft</strong> for your review — nothing enters certification
        automatically, and the system never invents content to fill a gap.
      </p>
      <div className="mt-6">
        <IngestionPanel />
      </div>
    </div>
  );
}
