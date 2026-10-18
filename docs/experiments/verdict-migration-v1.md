# Versioned revision of twelve consumed A/D verdicts

The migration is complete under confirmation-verdict-revision-v1-lost-particles,
using the qualified native-lost-particle-attribution-v1 policy.

All twelve consumed assignments were reconstructed from retained evidence.
Assignments 001-011 remain complete successes (score 100).
Assignment 012 changes from an unscored incident to an attributed native model
failure (score 0, strict_correct=false). Its original report and null score remain
available. The score follows the unchanged model-caused hard-gate rule; it was
not entered manually.

The revised prefix contains 11 successes, 1 evaluated failure and no unresolved
incident. There are still 228 pending assignments; these counts are not a
completed-campaign result or an A/D effect estimate.

## Evidence and scope

The migration checks the original manifest/launch, all assignment identities and
order, plan hashes, source delta, qualified-policy hashes, reference bindings,
builder-to-assessment provenance and original review records. The historical
verifier reconstructs export, inspection and transport evidence for every trial.
Only its exact unsupported-native-termination case is eligible for the new
lost-particle review.

For that case, the original gate/check accounting is also verified. Only the
openmc_runs hard gate and transport attribution change. Existing uncertain
boundaries and unreached statepoint/numerical checks remain uncertain/unreached.
No numerical result or shared-region-mutation mechanism is invented.

Each derived verdict links original report/review hashes, the legacy
reconstruction, the policy version and the revised gate/check/score records.
The migration retains an implementation snapshot and a sealed aggregate report.
A separate verify invocation reconstructs every derived record again.

All 3,382 original campaign files were checked unchanged. No candidate was
imported or executed on the host, no LLM request or native transport was launched,
and no original report, campaign progress, assignment or reference was rewritten.

## Implementation and commands

- evaluation/candidates/verdict_migration.py reconstructs a single derived verdict.
- experiments/migrate_confirmation_verdicts.py validates campaign bindings,
  applies the same rule to its consumed prefix, and verifies the resulting set.
- tests/test_verdict_migration.py exercises unchanged successes, zero-scored
  native failure, preserved unknowns, refusal of unrelated missing/contradictory
  evidence, changed assignments, source drift and output tampering.

~~~sh
python3 -B -m experiments.migrate_confirmation_verdicts migrate \
  --campaign scratch/indc107-native-v1/campaign \
  --output "$FRESH_MIGRATION_DIRECTORY"

python3 -B -m experiments.migrate_confirmation_verdicts verify \
  --output scratch/indc107-verdict-migration-v2
~~~

The completed operator artifact is scratch/indc107-verdict-migration-v2.
Its report.json, report.sha256, verdicts/001.json through verdicts/012.json,
original-evidence-sha256.json and implementation/ provide the review trail.
The first output attempt under v1 stopped before writing its first derived
verdict because its output subdirectory had not been created. That failed
attempt is retained; the corrected writer has an end-to-end write/read test.
Neither attempt consumed an experimental assignment.

All 486 portable tests passed, including 14 migration tests. The separate
verification of the real twelve-verdict migration passed.
See verdict-migration-v1.json for the public aggregate and evidence hashes.

## Campaign continuation remains separate

This migration creates an authoritative derived result set for a later explicit
continuation. The original progress file still reports its historical stopped
state (11 finished, 1 incident, 228 pending). The unchanged launcher is not a
resume mechanism and does not automatically consume the revised report.

No continuation has been launched by this migration. A later continuation must
bind this report and the new execution policy, preserve the twelve consumed
assignments and start with assignment 013.
