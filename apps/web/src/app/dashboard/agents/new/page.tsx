import Link from "next/link";

import { AddAgentsPanel } from "@/components/agents/AddAgentsPanel";
import { api, type DepartmentSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function AddAgentsPage() {
  let departments: DepartmentSummary[] = [];
  let error: string | null = null;
  try {
    departments = (await api.departments()).items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load departments";
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/dashboard/agents" className="text-sm text-ink-300 hover:text-ink-100">
        ← Agents
      </Link>
      <h1 className="mt-2 text-3xl">Add agents</h1>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        Add agents to the roster one at a time or in bulk. Adding an agent does not run, certify, or
        authorize anything — new agents start at minimum autonomy with zero certs.
      </p>
      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-danger">
          {error}
        </div>
      ) : (
        <AddAgentsPanel departments={departments} />
      )}
    </div>
  );
}
