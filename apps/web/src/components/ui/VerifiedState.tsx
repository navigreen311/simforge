import { type ReactNode } from "react";

// A check result NEVER has two states. A check that ran against an EMPTY set did not pass —
// it is INDETERMINATE. This component makes that impossible to get wrong (P0-B audit, Finding 1/3).
export type Verdict = "pass" | "fail" | "indeterminate";

/** Derive the verdict from a scan: 0 checked is ALWAYS indeterminate, never pass. */
export function verdictFor(checked: number, violations: number): Verdict {
  if (checked <= 0) return "indeterminate";
  return violations > 0 ? "fail" : "pass";
}

const STYLE: Record<Verdict, string> = {
  pass: "border-success/40 bg-success/10 text-success",
  fail: "border-danger/50 bg-danger/15 text-danger",
  indeterminate: "border-warning/50 bg-warning/15 text-warning",
};

const DOT: Record<Verdict, string> = {
  pass: "bg-success",
  fail: "bg-danger",
  indeterminate: "bg-warning",
};

export function VerifiedState({
  verdict,
  checked,
  total,
  passText,
  failText,
  asOf,
  children,
}: {
  verdict: Verdict;
  /** Number of items actually checked (the denominator that proves the check ran). */
  checked?: number;
  total?: number;
  /** Message when the check passed — MUST cite the denominator, e.g. "No drift across 34 certs". */
  passText?: string;
  failText?: string;
  asOf?: string;
  children?: ReactNode;
}) {
  const body =
    verdict === "indeterminate"
      ? `Inconclusive — checked ${checked ?? 0}${total != null ? ` of ${total}` : ""} items. This is not a pass.`
      : verdict === "fail"
        ? (failText ?? `Violations found across ${checked ?? 0} checked.`)
        : (passText ?? `No violations across ${checked ?? 0} checked.`);

  return (
    <div className={`rounded-xl border p-4 ${STYLE[verdict]}`}>
      <div className="flex items-center gap-3">
        <span className={`h-3 w-3 rounded-full ${DOT[verdict]}`} aria-hidden />
        <span className="text-sm font-semibold uppercase">{verdict}</span>
        <span className="text-sm text-ink-50">{body}</span>
        {asOf && <span className="ml-auto text-xs text-ink-400">as of {asOf}</span>}
      </div>
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}
