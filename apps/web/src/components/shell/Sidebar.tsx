import Link from "next/link";

// Nav mirrors the dashboard route tree (blueprint §A.5), grouped by concern.
type NavItem = { href: string; label: string };
type NavSection = { title: string; items: NavItem[] };

const SECTIONS: NavSection[] = [
  {
    title: "Certification",
    items: [
      { href: "/dashboard", label: "Overview" },
      { href: "/dashboard/brief", label: "Stakeholder Brief" },
      { href: "/dashboard/readiness", label: "Readiness Matrix" },
      { href: "/dashboard/runs", label: "Runs" },
      { href: "/dashboard/ventures", label: "Ventures" },
      { href: "/dashboard/cold-start", label: "Cold-Start" },
      { href: "/dashboard/packs", label: "Packs" },
      { href: "/dashboard/scenario-bank", label: "Scenario Bank" },
      { href: "/dashboard/truth-review", label: "Truth Review" },
      { href: "/dashboard/certs", label: "Certifications" },
    ],
  },
  {
    title: "Roster",
    items: [
      { href: "/dashboard/agents", label: "Agents" },
      { href: "/dashboard/departments", label: "Departments" },
      { href: "/dashboard/cohort", label: "Cohort Analytics" },
      { href: "/dashboard/coverage", label: "Coverage & Lifecycle" },
    ],
  },
  {
    title: "Enforcement",
    items: [
      { href: "/dashboard/incident", label: "Incident Command" },
      { href: "/dashboard/policy", label: "Policy (PDP)" },
      { href: "/dashboard/execution", label: "Integrated Execution" },
      { href: "/dashboard/drift", label: "Drift Canary" },
      { href: "/dashboard/parity", label: "Forge Parity" },
      { href: "/dashboard/jurisdictions", label: "Jurisdictions" },
    ],
  },
  {
    title: "Quality",
    items: [
      { href: "/dashboard/meta-eval", label: "Meta-Eval" },
      { href: "/dashboard/correlation", label: "Prod Correlation" },
      { href: "/dashboard/golden", label: "Golden Benchmark" },
      { href: "/dashboard/adversarial", label: "Adversarial" },
      { href: "/dashboard/temporal", label: "Temporal Realism" },
      { href: "/dashboard/training", label: "Agent Training" },
      { href: "/dashboard/gaps/software", label: "Gaps" },
    ],
  },
  {
    title: "Governance",
    items: [
      { href: "/dashboard/constitution", label: "Constitution" },
      { href: "/dashboard/lineage", label: "Lineage" },
      { href: "/dashboard/supply-chain", label: "Supply Chain" },
      { href: "/dashboard/narrative", label: "Narrative" },
    ],
  },
];

export function Sidebar() {
  return (
    <aside className="flex w-60 flex-col border-r border-ink-500 bg-ink-800 p-4">
      <div className="mb-8 px-2">
        <span className="font-display text-2xl text-gold-500">SimForge</span>
        <p className="mt-1 text-xs text-ink-200">Agent certification</p>
      </div>
      <nav className="flex flex-col gap-6">
        {SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-ink-400">
              {section.title}
            </div>
            <div className="flex flex-col gap-0.5">
              {section.items.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-3 py-2 text-sm text-ink-50 transition-colors hover:bg-ink-600"
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
