import Link from "next/link";
import { notFound } from "next/navigation";

import { NewPackWizard } from "@/components/packs/NewPackWizard";
import { api, type PackDetail } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function EditPackPage({ params }: { params: { packId: string } }) {
  let pack: PackDetail;
  try {
    pack = await api.pack(params.packId);
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        href={`/dashboard/packs/${params.packId}`}
        className="text-sm text-ink-300 hover:text-ink-100"
      >
        ← {pack.name}
      </Link>
      <h1 className="mt-2 text-3xl">Edit Pack → new version</h1>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        Editing creates the next version of this Pack and preserves the current one untouched — certs
        already pinned to the current version keep resolving. Pick the scenario set for the new
        version; a committed scenario can belong to one version, so the picker offers scenarios not
        already bound to a pack.
      </p>
      <NewPackWizard base={pack} />
    </div>
  );
}
