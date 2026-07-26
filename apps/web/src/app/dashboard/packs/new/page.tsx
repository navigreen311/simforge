import Link from "next/link";

import { NewPackWizard } from "@/components/packs/NewPackWizard";

export const dynamic = "force-dynamic";

export default function NewPackPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/dashboard/packs" className="text-sm text-ink-300 hover:text-ink-100">
        ← Packs
      </Link>
      <h1 className="mt-2 text-3xl">New Pack</h1>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        Assemble a certification Pack from committed Scenario-Bank scenarios plus its venture and
        compliance metadata. Creating a Pack defines the library — it does not certify anyone or run
        anything.
      </p>
      <NewPackWizard />
    </div>
  );
}
