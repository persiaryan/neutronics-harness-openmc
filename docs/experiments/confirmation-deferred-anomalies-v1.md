# Deferred anomaly diagnosis policy v1

Identity: `confirmation-deferred-anomalies-v1`.
Adopted explicitly by the owner after assignment 132. Effective prospectively
for assignments **133–240**, identically for both models and A/D.
This is an operational protocol amendment made during the campaign, not a
preregistered policy or a change to scientific scoring.

## Decision at each assignment

Continue after a scored, coherently verified outcome, including a demonstrated
model failure. A null score is eligible for deferred diagnosis only when:

- the builder submitted successfully with its existing verified cleanup/provenance;
- the independent assessment completed (`assessed`, no stopped phase), and cleanup
  is explicitly confirmed;
- retained-evidence review and the existing verdict reconstruction are coherent;
- all six hard gates are explicitly true: model construction, native completion,
  bounded geometry validity, required data, finite statepoint and observables;
- the original verdict is unscored, strict correctness is false, and at least one
  required scientific check is unresolved.

Eligible nulls remain **unscored**, including new capability limitations. The
operator records them as incident rows with `disposition=deferred_unscored`,
`score=null`, `strict_correct=null`, `stop_required=false`, and a path to the
unaltered original derived verdict. The retained verdict may have
`strict_correct=false`; that does not make the operator outcome a model failure.
No error-message allowlist or geometric witness assigns scientific credit.

Continue to the next original assignment without retry, repair, replacement,
extra model calls, diagnosis transport or new observer execution. The evaluator,
rubric, source checks and verdict migration do not change.

## Blocking conditions

Stop dispatch on an execution exception, incomplete builder, rejected submission,
uncertain cleanup, contradictory/insufficient evidence, unresolved hard gate,
changed code/input/data/policy identity, depleted disk reserve or another failed
execution guard. An unscored result with incomplete native execution is not
eligible for automatic continuation. A demonstrated model failure with coherent
evidence and confirmed cleanup remains scored and does not stop the campaign.

This policy does not implement automatic process restarts after blocking incidents.
Consumed or interrupted assignments are never replayed. Existing exclusive claims
and process/launch receipts are never removed.

## Preservation and later analysis

The nine pre-existing non-scored assignments (030, 039, 050, 066, 117, 118, 119,
120, 132), the 110 protocol successes and 13 evaluated failures remain unchanged.
Their earlier stop policy remains historical. The new policy does not reclassify
old incidents as newly eligible outcomes.

`deferred-anomalies.json` is an operator queue derived from progress, including the
nine historical unknowns and future deferred/blocking incidents. Original
assessment/report/review/verdict files remain the scientific evidence.
Completion means all assignments have been consumed; it does not mean all
anomalies have been resolved.

After collection, group unresolved outcomes by task, model, A/D and mechanism.
Report successes, evaluated failures, unknowns and pending slots separately;
do not silently remove unknowns from denominators or claim A/D efficacy from
the scored subset. Diagnosis does not grant a score. Any future evaluator change
and uniform reassessment require a separate version and authorization, preserving
original outcomes.

## Budget and provenance

The remaining segment contains 108 assignments, at most **1,728 model requests**,
16 requests and 600 authoring seconds each, zero retries. The original total
ceiling stays 3,840; prior unused allowances are not redistributed. Assessment
phase limits remain unchanged.

A new root controller `confirmation_resume_133.py`, its manifest and this document
are bound by hashes. Original controllers and frozen implementation inventories
are unchanged. No private reference or operator diagnosis enters builder context.
