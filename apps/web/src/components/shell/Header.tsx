import { StatusDot } from "@/components/common/StatusDot";
import { api } from "@/lib/api/client";

// Server component: shows live API readiness in the header.
export async function Header() {
  let status = "error";
  try {
    const ready = await api.ready();
    status = ready.status;
  } catch {
    status = "error";
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-ink-500 bg-ink-800 px-6">
      <div className="text-sm text-ink-200">Governance &amp; certification console</div>
      <div className="flex items-center gap-4">
        <StatusDot status={status} label={`API ${status}`} />
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gold-600 text-sm font-semibold text-ink-900">
          IV
        </div>
      </div>
    </header>
  );
}
