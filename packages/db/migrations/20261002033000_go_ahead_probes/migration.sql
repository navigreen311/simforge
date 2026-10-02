-- ADR-0139: go-ahead probes in every partition, and "any act-rule REFUSE counts".
--
-- A partition scenario may be a `permitted_request`; an outcome's citation may be
-- `other_act_rule` (a refusal under another act-rule of the module, reported, not gating).
-- No new columns, nothing backfilled. Idempotent.
ALTER TABLE "HeldOutPartitionScenario"
    DROP CONSTRAINT IF EXISTS "held_out_partition_scenario_class";
ALTER TABLE "HeldOutPartitionScenario"
    ADD CONSTRAINT "held_out_partition_scenario_class"
    CHECK ("scenarioClass" IN ('never_do_violation', 'silent_failure', 'permitted_request'));

ALTER TABLE "HeldOutPartitionOutcome"
    DROP CONSTRAINT IF EXISTS "held_out_partition_outcome_citation";
ALTER TABLE "HeldOutPartitionOutcome"
    ADD CONSTRAINT "held_out_partition_outcome_citation"
    CHECK ("citation" IS NULL OR "citation" IN ('probed', 'same_group', 'other_act_rule', 'other', 'none', 'out_of_range'));
