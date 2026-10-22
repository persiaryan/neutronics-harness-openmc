# Explicit final continuation at 237

The owner authorized resumption after the blocking builder incident at 236.
Preserve all **236 consumed assignments: 199 protocol successes, 19 evaluated
failures and 18 unscored outcomes**. Assignment 236 remains a historical blocking
incident, with its original `stop_required=true` and no score. It is never
repaired, replayed or assessed.

The four remaining original assignments are:

| ID | Model | Arm | Task |
|---|---|---|---|
| 237 | Luna | A | cross_shaped_mixture |
| 238 | Sol | A | three_annular_fuel_channels |
| 239 | Luna | A | dual_temperature_pin_pair |
| 240 | Sol | D | dual_temperature_pin_pair |

This segment has a ceiling of **64 new model requests**, 16 requests and
600 authoring seconds per assignment, zero retries, and unchanged final
assessment limits. The original 3,840-request ceiling remains fixed; unused
consumed allowances are not redistributed.

## Retained incident 236

Sol D, cylindrical_void_sleeve, repetition 5: five completed response streams,
then request 6 with HTTP 200, absent content type, 34,210 bytes read, an event of
type `error`, failed stream validation and no observed completion. The rejected
response was not forwarded or saved as response-06.sse. The builder failed after
44.806 seconds, cleanup was confirmed and the retained container lifecycle is
removed. There is no final submission or assessment directory.

The read-only diagnosis binds all six original request setups/inventories, the
preloaded D prompt/procedure, retained implementation snapshots, image/container
configuration, five completed streams, sixth upstream metadata and cleanup.
No provider call, candidate import, observer, model repair or transport is made.
Exact provider-versus-relay root cause remains unresolved because the rejected
raw stream was not retained. Missing content type alone does not explain the
failure: the preceding completed streams also accepted its absence.

## Preserved policy and provenance

The [deferred anomaly policy v1](confirmation-deferred-anomalies-v1.md) is unchanged,
including its original document hash and applicability from 133 through 240.
The new controller directly reuses prior.assess, prior.classify_outcome and
prior.persist. It does not modify the builder, evaluator, rubric, migration,
references, data, A/D setup, tools or procedure. Coherent unscored completed
assessments can be deferred; new blocking incidents still stop without retry.

Preparation seals the previous complete file inventory, manifest, progress,
launch, reconstructed 236-assignment prefix and incident diagnosis. It copies
only original prepared inputs and reference-review receipts into a fresh
directory. The new manifest adds resumption_237, leaving previous identities
intact. Earlier retained historical blocking flags do not stop dispatch of this
separately authorized suffix.

```sh
python3 -B confirmation_resume_237.py prepare \
  --previous scratch/indc107-resume-133-v1 \
  --output scratch/indc107-resume-237-v1
python3 -B confirmation_resume_237.py check \
  --output scratch/indc107-resume-237-v1
python3 -B confirmation_resume_237.py run \
  --output scratch/indc107-resume-237-v1 --maximum-model-requests 64
```

The exclusive claim is
scratch/indc107-resume-133-v1-resume-237-claim.json. Do not delete process,
launch or claim receipts or run a second executor. Monitor the new segment's
process.json, progress.json, execution.log, readiness.json,
resumption-237-launch.json, deferred-anomalies.json and sibling claim, plus
actual liveness and phase. Leave live preflight alone before launch receipts.

When all 240 assignments are consumed, verify the final outcome counts from
retained verdicts and the prefix chain, group available anomaly causes without
reevaluation, preserve unknowns in denominators, report limitations and pause
the existing monitor. Completion does not mean every anomaly has been resolved.
Portable tests cover no replay, prefix/score/null preservation, exact budget,
exclusive claims, unchanged policy behavior and rejected/tampered incident
evidence using synthetic process/request records.
