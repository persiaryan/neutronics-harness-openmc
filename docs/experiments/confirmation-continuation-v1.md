# Continuation after the twelve-verdict migration

The dedicated operator entry point is `confirmation_continuation.py`.
It continues assignments 013–240 from the original randomized order. The first
twelve assignments remain consumed: eleven protocol successes and one evaluated
model failure under the qualified lost-particle policy.

## Preserved experiment

The original campaign directory and its 3,382 files remain untouched. Preparation
copies only public input bundles and plans into a separate continuation directory.
Their bytes, execution identifiers, task order, model configurations, A/D procedure,
references and budgets are preserved. The aggregate progress includes the twelve
migrated verdicts, with links to their separate evidence directory.

The remaining ceiling is 228 × 16 = **3,648 new model requests**, with 600 authoring
seconds per assignment and no automatic retries. The original full ceiling remains
3,840 requests. Final evaluations use their original separate phase limits.

## Execution and evidence

For each remaining assignment:

1. Check frozen implementation, controller identity, data index, prepared inputs
   and a 10 GiB disk reserve.
2. Run the original builder with its original matched request setup.
3. Freeze and verify the delivered source, then run the unchanged independent
   final evaluation.
4. Retain its baseline report and reconstructed `review.json`.
5. Apply `verdict_migration.revise()` uniformly and save
   `assessment/revised-verdict.json`.
6. Continue after a coherent scored result, including a qualified model failure.
   Stop on missing/contradictory evidence, an unqualified native diagnostic,
   incomplete builder execution or uncertain cleanup.

No candidate is repaired and no failed assignment is replaced. A pre-dispatch
guard failure leaves the unstarted assignment pending. An interrupted or failed
started assignment remains consumed and requires explicit review before any
further continuation.

The controller is a separate, explicitly hash-bound operator file at repository
root. This preserves the exact evaluator/builder/migration inventories needed to
reconstruct sealed references and the twelve migrated verdicts. The continuation
manifest records both the original manifest hash and the migration report hash;
it permits only the source revision already verified by that migration.
The original qualification checker is reused for runtime/data/reference checks,
40 native controls and 12 end-to-end reference assessments. The four retained
provider delivery controls are reconstructed against the unchanged setups.

A reservation `launch.json` prevents use of the historical launcher on the new
directory. Actual dispatch uses `continuation-launch.json` and atomically creates
`continuation-claim.json` beside the sealed migration files. This exclusive claim
also prevents a second directory from replaying the same suffix. It is additional
operator metadata; none of the sealed migration files are rewritten.

## Commands

From the repository root, after the explicit authorization to resume:

```sh
python3 -B confirmation_continuation.py prepare \
  --output scratch/indc107-continuation-v2 \
  --migration scratch/indc107-verdict-migration-v2 \
  --provider-controls scratch/indc107-provider-controls-v1

python3 -B confirmation_continuation.py check \
  --output scratch/indc107-continuation-v2

python3 -B confirmation_continuation.py run \
  --output scratch/indc107-continuation-v2 \
  --maximum-model-requests 3648
```

`check` reconstructs evidence and checks local dependencies; it sends no LLM
request and performs no new neutron transport. `run` repeats this preflight,
then performs the authorized live work. Never delete launch/claim receipts to
restart a stopped process.

The live aggregate is `scratch/indc107-continuation-v2/progress.json`.
Its first twelve rows point to migrated verdicts; subsequent rows point to new
revised verdicts. The historical analysis command still reconstructs the baseline
policy, so it is not an analysis of this derived continuation policy. A final
combined scientific analysis remains a separate step.

## Verification and limitations

Portable tests cover preservation of the consumed prefix and randomized suffix,
budget enforcement, duplicate dispatch and restart refusal, cross-directory
exclusivity, preservation of baseline reviews, cleanup failures, model-failure
continuation and incident stopping. Execution/physics providers in these tests
are doubles; native validity comes from the retained qualification evidence and
the independent per-assignment evaluation.

This remains the exploratory A/D comparison. D supplies the complete procedure
in the initial prompt; spontaneous skill selection is not tested. Neither the
continuation mechanism nor the verdict migration establishes skill efficacy,
generalization or scientific/safety qualification.

The first offline preparation directory (v1) is retained as superseded. A status
reporting correction separates the historical launcher reservation marker from
an actual continuation launch. No assignment was consumed by that preparation.
