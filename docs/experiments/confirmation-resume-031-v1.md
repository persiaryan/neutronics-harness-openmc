# Restart at assignment 031 after the stream incident at 030

The stopped segment consumed assignments 001–030: **27 complete protocol
successes, two evaluated model failures and one unscored incident**. The
incident is Luna A on cross_shaped_mixture. Its only request matched the frozen
model/setup and task prompt. The builder failed after 47.621 seconds; cleanup
was confirmed and no final assessment ran.

## Diagnostic and its limit

The retained upstream receipt records HTTP 200, a missing Content-Type,
92,954 response bytes read, last_event_type=response.completed,
stream_validation=failed and completion_observed=false. The error was:
"Unexpected event in upstream Responses stream".

The frozen relay explicitly accepts a missing Content-Type and then validates
the buffered SSE prefix before forwarding it. Therefore the missing header does
not explain this rejection. Seeing a response.completed event does not establish
a validated completed response or delivery to the builder. The frozen validator
rejects unexpected event kinds/order. The rejected raw buffer was not persisted:
the exact offending event and provider-malformation-versus-adapter-strictness
question cannot be reconstructed from these receipts.

This is a provider/adapter stream protocol incident, without a demonstrated
physical-model failure. It remains consumed and unscored. No response is
invented, no candidate is assessed retrospectively and no automatic retry of
030 is performed. The relay remains byte-identical during this comparison.

## Bounded continuation

The explicitly authorized operator entry point is confirmation_resume_031.py.
It imports the frozen confirmation_continuation.py execution path, preserving
the evaluator, builder, procedure, request configurations, references, grading
criteria, task order, plan bytes and per-assignment budgets.

Preparation reconstructs the first twelve migrated verdicts, then all seventeen
results from 013 through 029. It verifies builder-to-candidate provenance,
retained baseline review, derived verdict and progress outcome. It reconstructs
the 030 diagnostic separately and checks its cleanup and lack of a response file
or final assessment. Only a contiguous stopped prefix through 030 is accepted.

The new manifest binds the previous manifest/progress/launch, a full inventory
of the previous directory, the incident diagnosis and the new operator source.
Public preparation inputs are copied to a fresh directory. Existing verdict
paths continue to reference their original locations. The previous evidence
directory is not rewritten. A sibling exclusive claim prevents another
directory from dispatching the same 031–240 suffix.

The remaining budget is **210 × 16 = 3,360 model requests**, with 600 authoring
seconds per slot, zero automatic retries and unchanged separate final-evaluation
phase limits. Unused allowances from consumed slots are not redistributed.
The original 240-slot ceiling remains 3,840 requests.

Every new result follows the same qualified verdict revision as 013–029:
a coherent model failure is recorded and execution continues; an unscored
incident stops execution. Interruptions never authorize replay of a consumed
slot. If another incident occurs, a later explicit continuation requires review.

## Commands and local evidence

```sh
python3 -B confirmation_resume_031.py prepare \
  --previous scratch/indc107-continuation-v2 \
  --output scratch/indc107-resume-031-v1

python3 -B confirmation_resume_031.py check \
  --output scratch/indc107-resume-031-v1

python3 -B confirmation_resume_031.py run \
  --output scratch/indc107-resume-031-v1 \
  --maximum-model-requests 3360
```

Preparation/check send no LLM requests and perform no new neutron transport.
They reuse the runtime/data/reference qualification, 40 native controls, 12
end-to-end reference assessments and four original provider-delivery controls.

The local incident record is
scratch/indc107-resume-031-v1/incident-030.json.
The operational progress is
scratch/indc107-resume-031-v1/progress.json.
The previous segment remains scratch/indc107-continuation-v2.

Fourteen additional portable tests cover incident attribution limits, forged
completion/forwarding metadata, cleanup, response/assessment absence, exact
consumed-prefix preservation, changed verdict rejection, no replay, exclusive
dispatch, budgets and stop behavior. Providers in those tests are doubles;
the real prefix is separately reconstructed before live dispatch.

A final combined analysis remains separate. Operational continuation does not
establish A/D efficacy, mechanism attribution or held-out generalization.
