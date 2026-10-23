# Explicit continuation at 067, preserving 066 unscored

The owner authorized this continuation after diagnosis of assignment 066.
Preserve all **66 consumed assignments: 57 protocol successes, five evaluated
failures and four unscored outcomes (030, 039, 050, 066)**. Assignment 066 is
Luna D, indc107_reflective_pin, repetition 4. It is never replayed, repaired or
rescored by this continuation.

## Diagnosis and decision

066 completed native transport, retained coherent execution evidence and
confirmed cleanup. Geometry, materials, numerical equivalence, statistical and
leakage checks pass. All four physics_settings checks remain null.

The candidate restricts its initial source to fuel_cell using domains. XML
records domain_type=cell and domain_ids=1. The frozen settings comparator only
recognizes the explicit fissionable flag (or legacy fission spatial encoding),
so it records source_fissionable=false and both domain fields as unsupported.
The settings aggregator leaves its entire category unresolved when unsupported
options occur. This produces a null score and the prescribed dispatch stop.

The local XML witness checks the exact two-cell partition: cell 1 is the
uranium cylinder of radius 1.27 cm; cell 2 is the remaining water; both span
the prescribed reflective slice. The source box is correct. Selecting cell 1
therefore selects the expected geometric region in this particular model.
This is not generic qualification of OpenMC domain constraints or their
rejection/distribution semantics. The elementary false flag is not, by itself,
proof that this candidate accepts source points in water.

Decision: retain 066 consumed and unscored and proceed at 067 under the same
evaluation. No new source observer, grading exception, points or automatic
incident continuation is introduced. The incident differs from the boundary
abstraction limits at 039 and 050. Future unscored outcomes still stop dispatch.

## Implementation and verification

confirmation_resume_067.py reuses the frozen 051 controller and its predecessor
chain. terminal_prefix verifies the inherited first 50 assignments and
reconstructs the retained 051–065 outcomes. diagnose reconstructs 066 and
checks its exact unsupported-source signature and local XML witness.

prepare copies only prepared public inputs and reference-review receipts into
a fresh directory. The manifest binds the previous manifest, progress, launch,
complete file inventory, diagnosis and new controller. check verifies these
bindings, original task order, dependencies and frozen settings. Neither
preparation nor checking executes candidate Python, a provider, an XML worker
or neutron transport. Original evidence remains unchanged.

run uses a separate exclusive sibling claim and dispatches only 067–240:
**174 assignments, 2,784 maximum new model requests**, 16 requests and 600
authoring seconds per assignment, zero retries. Original total ceiling is
3,840. Unused allowances from consumed assignments are not redistributed.
A/D configuration, preloaded procedure, tasks, reference data, evaluator,
rubric and final-assessment phase budgets remain unchanged.

Fifteen added portable tests use synthetic public XML and execution doubles.
They cover prefix/score/order preservation, null retention, diagnosis mismatch,
no replay, exclusive launch, exact budget, model-failure continuation and
incident stopping. They do not qualify source-distribution equivalence.

```sh
python3 -B confirmation_resume_067.py prepare \
  --previous scratch/indc107-resume-051-v1 \
  --output scratch/indc107-resume-067-v1
python3 -B confirmation_resume_067.py check \
  --output scratch/indc107-resume-067-v1
python3 -B confirmation_resume_067.py run \
  --output scratch/indc107-resume-067-v1 --maximum-model-requests 2784
```

The live run is separately authorized by the owner. Never delete process,
launch or claim receipts to restart a consumed or interrupted segment.
The monitor must inspect process.json, progress.json, execution.log,
readiness.json, resumption-067-launch.json and the sibling
scratch/indc107-resume-051-v1-resume-067-claim.json, then verify actual liveness.
Silence during transport or preflight is not proof of a stopped executor.

## Separate future improvement

Qualify semantic comparison of source constraints in a new evaluator version.
Positive controls should establish equivalent cell/material restrictions;
negative controls must include selection of water, omitted fuel cells,
additional regions and changed rejection strategy. Duplicates, unresolved
hierarchies and unsupported domain types should remain indeterminate. Determine
which settings unknowns actually affect before aggregating them; preserve
known discrepancies beside unknowns. Validate against the pinned OpenMC
implementation and isolated sampling controls before any new scientific study.
Merely allowlisting domain XML fields would not establish conformity.
Any later reanalysis must be separate and versioned; this campaign's retained
outcomes and original denominators remain visible.
