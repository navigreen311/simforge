import Link from "next/link";

import { AddVentureForm } from "@/components/ventures/AddVentureForm";

export const dynamic = "force-dynamic";

export default function NewVenturePage() {
  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/dashboard/ventures" className="text-sm text-ink-300 hover:text-ink-100">
        ← Venture Registry
      </Link>
      <h1 className="mt-2 text-3xl">Add venture</h1>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        Register a new Green Companies venture. You can enrich it later by uploading a spec document
        or editing it by hand.
      </p>
      <AddVentureForm />
    </div>
  );
}
