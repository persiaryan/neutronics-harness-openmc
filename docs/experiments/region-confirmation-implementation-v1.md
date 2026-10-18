# Confirmation evaluation and reference workflow, version 1

Implementation started on 2026-10-18. This is a separately versioned diagnostic
evaluation route: `factory-assessment-confirmation-v1`. Scientific review remains
`pending_owner_review`; the numerical screens are inherited research criteria,
not calibrated physical acceptance or safety limits.

## Scope and task revision

The historical six-task catalog and earlier A/D pilot remain historical records.
The new route admits the twelve confirmation candidate IDs explicitly.
The cylindrical-void-sleeve task is version 2: a rectangular water exterior
surrounds the cylindrical mixture and void sleeve. The original cylindrical
exterior statement is retained under `prompts/confirmation_v1/archive/`.
No curved-boundary observer extension is claimed.

The initial task-release manifest records release-time unqualified states.
Actual technical readiness is determined from the selected operator reference
packages, native control evidence and end-to-end assessments, not from that
public metadata alone.

## Execution path

1. `evaluation.confirmation.cases` transcribes material recipes, location-dependent
   temperatures, geometry expectations, finite probes and per-face requirements.
   It never imports a reference implementation.
2. The existing XML-only workers observe the final factory export. Existing
   comparators support separate source/entropy boxes; temperature expectations
   depend on the material location; leakage consistency depends on boundary
   requirements rather than one historical case name.
3. The existing independent factory, native transport, scoring and retained-evidence
   verifier execute under the new protocol. A and D retain matched tools/budgets.
4. `evaluation.confirmation.references.target` requires an explicit sealed private
   package bound to the task version, suite, evaluator, criteria and nuclear data.
   It never falls back to historical or public-demo answers.
5. `experiments.region_confirmation` prepares/checks the 240-slot manifest,
   independently assesses operator references end to end, records source-review
   annotation templates and summarizes outcomes with pending/incident distinctions.
   Live dispatch is an explicit separate action requiring a declared budget.

Candidate Python is never imported on the host. Private reference constructors,
native inputs, reference answers, raw traces and package paths stay in operator
evidence. Builder messages contain one public specification plus the selected
construction guidance. Neither reference packages nor grader expectations enter
the construction container.

## Qualification protocol

`evaluation/confirmation/protocol.json` fixes three primary seeds (11, 23, 37),
one longer-inactive control (seed 53, 600 batches, 300 inactive), and one point-source
control (seed 71). Primary sampling is 10,000 particles, 400 batches, 100 inactive,
two generations per batch. Native limits are 1800 seconds, one thread, zero retries.

The baseline reference plan comprises 60 native calls for twelve tasks, followed
by twelve end-to-end reference-as-candidate calls (candidate seed 1).
XML-only controls are additional and use no neutron transport or provider calls.
Finite probe coverage is bounded and never proves arbitrary global CSG correctness.

Qualification checks mean precision, primary pair consistency, all-run precision,
entropy drift and practical equivalence of both sensitivity controls.
The inherited 150 pcm margin, 0.02-bit entropy screen and 30 pcm reference-mean
precision remain explicit diagnostic choices. Failed/inconclusive controls are
retained; they do not trigger seed replacement, tolerance relaxation or automatic
retry. A failed reference cannot silently enter the campaign.

## Commands

Supply independently authored self-contained reference modules as
`$PRIVATE_SOURCES/<case>.py`. The operator fixtures created in this session are
under the ignored `scratch/confirmation-reference-sources-v1/`, outside public
prompt inputs. They are not candidate-generated models.

~~~sh
python3 -B -m evaluation.confirmation.controls \
  --sources "$PRIVATE_SOURCES" --output scratch/confirmation-controls \
  --data-index "$DATA_INDEX"

python3 -B -m evaluation.confirmation.qualify \
  --sources "$PRIVATE_SOURCES" --output scratch/confirmation-references \
  --data-index "$DATA_INDEX" \
  --cases cross_shaped_mixture dual_temperature_pin_pair restricted_source_nine_pin
~~~

The first three tasks exercise geometry unions, heterogeneous effective
temperatures and restricted source support. Extend to the remaining nine only
after reviewing this milestone. All output directories must be fresh.
Each reference qualification retains its own code, export, observations, transport,
process receipts, data identities, histories, failures and numerical summary.

`experiments.confirmation_reference_review` independently reconstructs all five
runs before a package enters an operational manifest. It binds the summary to
actual variant source bytes, export receipts, XML observations, sampling, statepoints,
histories, data and native identity. The original qualification files stay intact.

`experiments.confirmation_volume_review` compares independent analytic material
volumes against uniform native point observations. Its estimates and sampling
uncertainties are diagnostic; they do not add a post-hoc score or prove exhaustive
volume correctness. Staged native-control reports can be reconstructed with
`region_confirmation review-controls` without rerunning consumed calculations.

Create an operator JSON mapping task IDs to selected reference-package directories.
No links or implicit reference discovery are used.

~~~sh
python3 -B -m experiments.region_confirmation end-to-end \
  --references "$REFERENCE_INDEX" --data-index "$DATA_INDEX" \
  --output scratch/confirmation-end-to-end

python3 -B -m experiments.region_confirmation prepare \
  --references "$REFERENCE_INDEX" --data-index "$DATA_INDEX" \
  --setups "$REVIEWED_SETUPS" --controls "$NATIVE_CONTROL_REPORT" \
  --end-to-end "$END_TO_END_REPORT" --output scratch/confirmation-ad-240

python3 -B -m experiments.region_confirmation check --output scratch/confirmation-ad-240
python3 -B -m experiments.region_confirmation analyze --output scratch/confirmation-ad-240
~~~

Preparation retains all twelve assignments even when a reference is blocked,
records the cause and dispatches nothing. Readiness checks actual nuclear-data files and pinned images, and requires all twelve references,
the complete 40-control matrix and twelve passing end-to-end assessments.
A report containing only a subset of positive fixtures is insufficient.

## Separate live qualification and launch

These commands are implemented but are not run by the implementation or native
qualification workflow. They consume actual provider calls and require explicit
request ceilings:

~~~sh
python3 -B -m experiments.region_confirmation qualify-provider \
  --setups "$REVIEWED_SETUPS" --output scratch/confirmation-provider-controls \
  --maximum-model-requests 4

python3 -B -m experiments.region_confirmation run \
  --output scratch/confirmation-ad-240 \
  --controls scratch/confirmation-provider-controls \
  --maximum-model-requests 3840
~~~

The four provider checks prove exact initial A/D context and complete provider
responses, not modeling performance. They are excluded from the campaign.
The live comparison has twelve tasks, two setups, A/D and five repeats:
240 assignments, 16 requests and 600 authoring seconds per assignment,
zero retries. It pauses on infrastructure/provider/evaluator incidents and never
replaces consumed failures. Frozen source/task/plan identities are checked again.

The inventory remains a proposed estimation design, not a power guarantee.
Smallest relevant benefit, precision/power justification and scientific threshold
review are decisions to settle before describing a run as confirmatory.
The runner exposes a budgeted diagnostic execution path; it does not supply
scientific approval on the owner's behalf.

## Analysis and annotations

All-assigned success and task/model breakdowns remain primary; partial scores,
targeted mechanisms, other failures and resource use are explanatory.
Unstarted trials stay pending; infrastructure/evaluator incidents are distinct
from evaluated failures. No completed-campaign percentage is emitted while
assignments remain pending. Equal-task-weight D-minus-A rates are reported within
each model setup; repetitions are nested within task.

The template freezes the existing four-part mechanism definition. Nonpending
annotations must cite source hashes, reviewer, causal chain, coverage limitations
and campaign-relative evidence intervals. A pending label is not a negative.
`--annotations` optionally accepts the completed hash-bound template.
Reviewer identity/type is retained as declared; the analyzer does not certify human review.
Available token usage is reconstructed from retained completed responses;
missing usage remains unknown.

Qualification does not establish experimental physical validity, universal
geometry coverage, efficacy of D, or spontaneous loading in E.

## Prelaunch task-version provenance correction

After qualifying the first three version-1 tasks, a metadata defect was found:
the assessment assignment still hardcoded `case_version=1`. Assignments now use
the selected task version, and the independent verifier rejects a wrong version.
The revised cylindrical task therefore records version 2.

The first three sealed packages and their raw assessments remain unchanged.
A narrowly enumerated compatibility rule admits their exact generation hashes
for the three metadata-related source files only. All other evaluator, task,
protocol, numerical and physical identities must still match exactly; the new
runner/verifier hashes are pinned. The rule does not admit these old packages
for the version-2 cylindrical task or any different physical/criteria change.
Independent review retains both the generation and current verifier identities.
No transport was rerun or relabelled for this metadata correction.

## Native capability limit retained during implementation

The initial compact water complement for `wrapped_eight_pin_channel` and its
cell-order variant passed all 3,314 material-map/interface/domain probes,
materials and settings, but left external-boundary domain proof indeterminate:
`root_domain_not_resolved_by_supported_abstraction`. This is an observer
capability limit, not an established model defect. The original sources,
exports, observations and failed qualification matrix remain retained.

The operator reference was revised before any transport for that task. Its
water is partitioned explicitly into the inner square outside pins and the
outer domain outside the wrapper envelope. If pins P are inside inner box I,
and I is inside wrapper envelope E inside domain D, the water sets satisfy
`D minus (P union (E minus I)) = (I minus P) union (D minus E)`.
The pin and wrapper material regions are unchanged. Both exports yield exactly
the same 3,314 native point observations; the new representation also resolves
the external domain. Its correct, reordered and injected-defect controls pass.

The selected forty-control qualification matrix therefore passes, while the
two original indeterminate correct representations remain explicit capability
counterexamples. The observer and score rules were not changed. An unsupported
candidate representation remains an unscored incident and pauses live dispatch;
it cannot become a model failure or a positive result by reusing reference checks.
This representation dependence remains a limitation to review before launching
or interpreting the twelve-task comparison.
