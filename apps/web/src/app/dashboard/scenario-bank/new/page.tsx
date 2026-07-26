import Link from "next/link";

export const dynamic = "force-dynamic";

// Placeholder — the ingestion flows (manual author, paste/extract, document, web, video) land in
// the next batches. Nothing here creates or commits a scenario yet.
export default function NewScenarioPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/dashboard/scenario-bank" className="text-sm text-ink-300 hover:text-ink-100">
        ← Scenario Bank
      </Link>
      <h1 className="mt-2 text-3xl">New scenario</h1>
      <p className="mt-3 text-ink-200">
        New scenarios are created through the ingestion flows. Each one lands as a{" "}
        <strong>draft</strong> for human review — nothing enters certification automatically.
      </p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {[
          ["Manual author", "Write a scenario by hand", true],
          ["Paste text", "Extract a scenario from pasted text", true],
          ["Document upload", "Extract scenarios from a PDF/docx/txt", true],
          ["Web search", "Find real-world sources to draft from", false],
          ["Video / YouTube", "Transcribe then draft", false],
        ].map(([title, desc, soon]) => (
          <div
            key={title as string}
            className="rounded-xl border border-ink-500 bg-ink-800 p-4"
          >
            <div className="flex items-center gap-2">
              <span className="text-ink-50">{title}</span>
              <span className="ml-auto rounded bg-ink-700 px-2 py-0.5 text-[10px] text-ink-400">
                {soon ? "next batch" : "pending dependency"}
              </span>
            </div>
            <p className="mt-1 text-xs text-ink-400">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
