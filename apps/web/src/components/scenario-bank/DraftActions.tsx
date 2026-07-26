"use client";

import { useEffect, useState } from "react";

import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { scenarioBank, type BankScenarioDetail, type BankVocabulary } from "@/lib/api/client";

import { ScenarioForm } from "./ScenarioForm";

// Draft lifecycle actions on the detail page. Commit is the ONLY path into the active bank and is
// gated behind a typed confirmation — it is an explicit, logged human action. Nothing auto-commits.
export function DraftActions({ scenario }: { scenario: BankScenarioDetail }) {
  const [vocab, setVocab] = useState<BankVocabulary | null>(null);
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState<null | "commit" | "reject">(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    scenarioBank.vocabulary().then(setVocab).catch(() => setVocab(null));
  }, []);

  async function act(kind: "commit" | "reject") {
    setBusy(true);
    setError(null);
    try {
      if (kind === "commit") await scenarioBank.commit(scenario.publicId);
      else await scenarioBank.reject(scenario.publicId);
      window.location.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
      setBusy(false);
      setConfirm(null);
    }
  }

  if (editing && vocab) {
    return (
      <section className="mt-6 rounded-lg border border-ink-500 bg-ink-800 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-200">Edit draft</h2>
          <button
            onClick={() => setEditing(false)}
            className="text-xs text-ink-400 hover:text-ink-200"
          >
            Cancel
          </button>
        </div>
        <ScenarioForm
          vocab={vocab}
          aiDrafted={scenario.aiDrafted}
          sourceType={scenario.sourceType}
          sourceRef={scenario.sourceRef}
          sourceExcerpt={scenario.sourceExcerpt}
          initial={{
            title: scenario.title,
            pack: scenario.pack,
            family: scenario.family,
            tier: scenario.tier,
            situation: scenario.situation,
            expectedBehaviors: scenario.expectedBehaviors,
            adversarialTactics: scenario.adversarialTactics,
            jurisdictionFlags: scenario.jurisdictionFlags,
          }}
          submitLabel="Save changes"
          onSaved={async (body) => (await scenarioBank.editDraft(scenario.publicId, body)).publicId}
        />
      </section>
    );
  }

  return (
    <section className="mt-6 rounded-lg border border-ink-600 bg-ink-800 p-4">
      <h2 className="text-sm font-semibold text-ink-200">Draft review</h2>
      <p className="mt-1 text-xs text-ink-400">
        This draft is not in certification. Committing assigns a real{" "}
        <span className="font-mono">scn.*</span> id and adds it to the active bank — an explicit,
        logged action. Nothing here auto-commits.
      </p>
      {error && (
        <div className="mt-3 rounded border border-danger/40 bg-danger/10 p-2 text-xs text-danger">
          {error}
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={() => setEditing(true)}
          disabled={!vocab}
          className="rounded border border-ink-500 px-3 py-1.5 text-sm text-ink-100 hover:bg-ink-700 disabled:opacity-40"
        >
          Edit
        </button>
        <button
          onClick={() => setConfirm("commit")}
          className="rounded bg-gold-500 px-3 py-1.5 text-sm font-semibold text-ink-900 hover:bg-gold-400"
        >
          Commit to bank
        </button>
        <button
          onClick={() => setConfirm("reject")}
          className="rounded border border-danger/40 px-3 py-1.5 text-sm text-danger hover:bg-danger/10"
        >
          Reject
        </button>
      </div>

      <ConfirmModal
        open={confirm === "commit"}
        title="Commit scenario to the bank"
        requireWord="COMMIT"
        confirmLabel="Commit"
        busy={busy}
        onConfirm={() => act("commit")}
        onCancel={() => setConfirm(null)}
      >
        This assigns a permanent <span className="font-mono">scn.*</span> id and makes the scenario
        part of the active bank. This is the human commit step — it will be logged with your identity
        and recorded in Lineage. Continue?
      </ConfirmModal>

      <ConfirmModal
        open={confirm === "reject"}
        title="Reject this draft"
        confirmLabel="Reject"
        busy={busy}
        onConfirm={() => act("reject")}
        onCancel={() => setConfirm(null)}
      >
        The draft will be marked <strong>rejected</strong> and kept for the record. You can revisit
        it later. It will not enter certification.
      </ConfirmModal>
    </section>
  );
}
