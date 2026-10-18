# Lost-particle attribution: qualification checkpoint

This is the next bounded step after the twelve-task A/D campaign stopped.
It qualifies a new native diagnostic; it does not migrate historical scores,
resume the campaign or change its scientific criteria.

## Diagnosis of consumed assignment 012

The candidate was exported, loaded and executed by pinned OpenMC 0.15.3.
Ten retained warnings name internal surfaces 7 and 8 (z=-12 and z=12 cm);
the process then reports "Maximum number of lost particles has been reached."
Its exit code is 255 and no controller stop reason is recorded. The calculation
produced no final statepoint. Cleanup was confirmed.

The central water cell is outside the sleeve and between these axial planes,
but is not intersected with the exterior box. It therefore occupies points
beyond the required lateral vacuum faces. Above and below the central slice,
water is clipped to the box. This provides an explicit route to unoccupied
space after crossing an internal axial plane.

XML-only inspection of the retained artifact gives these witnesses:

| Point in cm | Matching cell IDs |
|---|---|
| (11, 0, 0) | 3 (central water outside the requested box) |
| (11, 0, 11.999) | 3 |
| (11, 0, 12.001) | none |
| (9, 0, 12.001) | 5 (upper water inside the box) |

These are semantic witnesses, not reconstructed neutron trajectories. Ten
particle restart files were read without running the candidate; their retained
fields alone do not establish every lost trajectory.

Correction to the preliminary explanation: the original spatial checks DID
detect four outside-face discrepancies (expected outside, observed water).
The original geometry group had domain=false, while invalid_geometry=0.
The effective boundary comparison was indeterminate. The controller's early
geometry gate stops holes/overlaps found by probes; an extent mismatch did not
prevent native transport. Thus the inspection did not wholly miss the defect.
Changing early admission/score aggregation is outside this qualification step.

The independent evidence review was insufficient because the frozen native
classifier did not recognize this 255 diagnostic. The original report,
null score, review, progress and launch records remain unchanged.

## Explicit qualified path

- evaluation/candidates/lost_particles.py::diagnostic recognizes one exact fatal
  error line with the expected failed-phase flags, integer exit 255 and no stop
  reason. Unknown errors, quoted text, multiple error lines and interruptions
  do not inherit attribution.
- lost_particles.review reconstructs independent export, source/XML identity,
  native containment, pinned runtime, data snapshots, prerequisite process
  receipts, frozen retrieval and artifact bytes. It also checks actual staged
  XML, the loaded-XML record, solver/worker identity and absence of a statepoint.
- phase_evidence.transport_failure accepts an explicit allow_lost_particles
  switch, default False, reusing its existing evidence checks. The normal
  run/verify path retains its original classification.
- The output states attribution=model and protocol_success=false. It assigns
  no campaign score and infers no shared-region-mutation mechanism.

The reference/runtime argument is an operator binding obtained from the sealed
reference reader. Hashes bind local evidence; they are not signatures protecting
against an operator rewriting all evidence. The policy is qualified for the
pinned serial runtime, not every OpenMC version or parallel execution mode.

## Native qualification

experiments.qualify_lost_particles runs a fresh, separately budgeted qualification:

1. Verify the retained failed assignment without re-executing its source/transport.
2. Export and run an independently constructed three-slab fixture with its middle
   slab absent. That genuine gap must trigger the qualified lost-particle fatal.
3. Export and run the complete three-slab partition. It must complete transport
   and must not receive lost-particle attribution.
4. Verify that every file in the original assessment is unchanged.

Both fixtures use 1,000 particles, 8 batches, 2 inactive batches, one generation
per batch, seed 1 and a 120-second transport limit. They qualify execution and
classification; they are not benchmark reference calculations or efficacy trials.
Maximum two native transports, zero retries and zero provider requests.
All consumed evidence remains recorded even if a control fails.

~~~sh
python3 -B -m experiments.qualify_lost_particles \
  --assessment "$RETAINED_ASSESSMENT" --reference "$PRIVATE_REFERENCE" \
  --data-index "$DATA_INDEX" --output "$FRESH_QUALIFICATION_DIRECTORY"

python3 -B -m unittest tests.test_lost_particles -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
~~~

The completed local qualification is under scratch/lost-particle-qualification-v1.
Both native controls passed and the retained assignment has coherent native
model-failure attribution under the new explicit policy. Every original
assessment file is unchanged. Public aggregate evidence is in
lost-particle-qualification-v1.json; raw inputs, traces and nuclear-data paths
remain operator-local.

## Required next milestone

A continuation still requires an explicit evaluator-policy version and migration
record, uniform reconstruction of all twelve consumed assessments, compatibility
review of frozen references, and a resume manifest preserving assignments,
consumption and order. The current launch guard intentionally refuses both a
changed source inventory and restarting a consumed campaign. This checkpoint
does not bypass those checks.

The campaign remains stopped with eleven completed successes, one originally
unscored incident and 228 pending assignments. The newly qualified attribution
is retained separately until that migration. No model call, retry, candidate
repair, score replacement, threshold change or automatic continuation occurred.
