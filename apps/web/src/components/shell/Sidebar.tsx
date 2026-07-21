import Link from "next/link";

// Nav mirrors the dashboard route tree (blueprint §A.5). Routes not yet built are marked.
const NAV: Array<{ href: string; label: string; ready: boolean }> = [
  { href: "/dashboard", label: "Overview", ready: true },
  { href: "/dashboard/readiness", label: "Readiness Matrix", ready: false },
  { href: "/dashboard/runs", label: "Runs", ready: false },
  { href: "/dashboard/packs", label: "Packs", ready: false },
  { href: "/dashboard/agents", label: "Agents", ready: false },
  { href: "/dashboard/departments", label: "Departments", ready: false },
  { href: "/dashboard/certs", label: "Certifications", ready: false },
  { href: "/dashboard/gaps/software", label: "Gaps", ready: false },
  { href: "/dashboard/constitution", label: "Constitution", ready: false },
];

export function Sidebar() {
  return (
    <aside className="flex w-60 flex-col border-r border-ink-500 bg-ink-800 p-4">
      <div className="mb-8 px-2">
        <span className="font-display text-2xl text-gold-500">SimForge</span>
        <p className="mt-1 text-xs text-ink-200">Agent certification</p>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.ready ? item.href : "/dashboard"}
            className={`rounded-md px-3 py-2 text-sm transition-colors hover:bg-ink-600 ${
              item.ready ? "text-ink-50" : "cursor-not-allowed text-ink-300"
            }`}
          >
            {item.label}
            {!item.ready && <span className="ml-2 text-[10px] text-ink-400">soon</span>}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
