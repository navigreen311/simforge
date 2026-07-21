// L1–L5 autonomy ladder indicator (blueprint §D.3, §F.3).

const LEVELS = ["L1", "L2", "L3", "L4", "L5"];
const LABELS: Record<string, string> = {
  L1: "Observe only",
  L2: "Draft only",
  L3: "Exec + approval",
  L4: "Spot-check",
  L5: "Full autonomy",
};

export function AutonomyLadderIndicator({ level }: { level: string }) {
  const activeIdx = LEVELS.indexOf(level);
  return (
    <span className="inline-flex items-center gap-1" title={LABELS[level] ?? level}>
      {LEVELS.map((lvl, i) => (
        <span
          key={lvl}
          className={`h-1.5 w-4 rounded-sm ${i <= activeIdx ? "bg-gold-500" : "bg-ink-500"}`}
          aria-hidden
        />
      ))}
      <span className="ml-1 font-mono text-xs text-ink-100">{level}</span>
    </span>
  );
}
