// Tier pill — Foundational / Intermediate / Advanced-Crisis (blueprint §D.3).

const STYLES: Record<string, string> = {
  foundational: "bg-info/15 text-info",
  intermediate: "bg-gold-600/20 text-gold-300",
  advanced_crisis: "bg-danger/15 text-danger",
};

const LABELS: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};

export function TierPill({ tier }: { tier: string }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STYLES[tier] ?? "bg-ink-500"}`}>
      {LABELS[tier] ?? tier}
    </span>
  );
}
