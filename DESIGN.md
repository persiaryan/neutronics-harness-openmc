# Architecture and scientific boundaries

The objective is to compare matched authoring conditions while keeping final
assessment independent. The path uses direct functions, ordinary OpenMC models
and code-based graders.

## Follow one request

1. `prompts.prepare.prepare()` reads an allowlisted public specification and factory
   template. Private answers cannot enter preparation. `experiments.run.prepare()`
   records task, model, assistance policy, prompt hashes and budgets.
2. `experiments.run.execute()` calls `builder.run.run()` in a fresh container.
   `builder.route.condition_prompt()` selects the declared policy. The Codex relay
   is an adapter, not a scientific dependency. Both conditions have coding tools.
3. The builder attempts a working export. With assistance enabled,
   `builder.boundary_tool.Session.inspect_boundaries()` accepts authorized workspace
   artifacts and invokes a fresh XML-only observer. `builder.boundary_feedback`
   returns effective observations, coverage and limitations; the full response
   remains available for detail reads. No private expectations or scores enter
   this loop. Instructions do not guarantee tool use.
4. `builder.submission.submission()` verifies delivered source and provenance.
   The source is frozen; the host never imports candidate Python.
5. `evaluation.candidates.run.evaluate()` calls `evaluator.run.evaluate()` once.
   In a separate container, `evaluator.factory` calls `build_model()`, checks its
   `openmc.Model` return and exports that object. There is no script fallback,
   alternative-model search or automatic physical repair.
6. `evaluation.scientific.inspection.inspect_xml()` and `boundaries.observe()` run
   fresh XML-only processes. Observers extract data; task requirements and generic
   comparators determine per-requirement verdicts. Missing observations do not pass;
   an unresolved property does not hide an observed mismatch.
7. `evaluator.transport.transport()` receives the same admitted XML bytes in a
   separate native OpenMC container with read-only data. Candidate Python and
   builder observations never enter it. Physics and settings are not rewritten.
8. `assessment.complete_checks()` compares numerical evidence with a private sealed
   reference; `scoring.score()` applies hard gates and weights. Independently,
   `candidates.verify.review_assessment()` reconstructs coherent, contradictory or
   insufficient evidence. `experiments.run.assessment_summary()` reports outcomes;
   `builder.trajectory.summarize()` reports observable authoring behavior separately.

## Contracts and limits

Current route: `openmc-model-factory-v1`, `factory-serial-v1`,
`factory-assessment-boundaries-v4-temperature-source-v1`, boundary observer v2. There
is one independent final export, not a repeat-build stability grader. Working exports are authoring
activity and never replace final evaluation.

The export child gets 60 seconds including startup/import/construction/export,
plus 10 seconds for external completion reporting. Staging/retrieval calls have
separate 30-second limits. Inspections get 120 seconds; native transport gets
1,800 seconds. Execution is serial with no automatic retries. These are phase
limits; cleanup can extend total elapsed time.

The boundary observer uses loaded OpenMC regions. Conservative bounds establish
spatial absence only, before Boolean simplification and bounded enumeration.
Domain occupancy and face participation remain separate obligations. Neither a
bounding box nor a surface name proves global validity. See [the precise scope](evaluation/scientific/BOUNDARIES.md).

The private material inspector rejects a demonstrated material with neither nuclides
nor macroscopic data as invalid native input; proper void cells remain valid.
Successful export stays recorded when transport eligibility fails. Unknown inspector
errors remain unresolved and unscored; exceptions alone cannot justify candidate-zero.
This check does not expand macroscopic admission support.

Effective temperature keeps cell → material → settings-default precedence,
falling back only when the preceding value is absent (`None`). The worker uses
the qualified experimental v7 rule: a finite real scalar or one-element
list/tuple resolves to one value. A wrong finite temperature fails; empty or
multiple entries (even equal ones), nested/unsupported containers, strings,
booleans and non-finite values remain unresolved. No arbitrary array coercion
or distributed-instance selection is performed. A demonstrated mismatch remains
false alongside unknown observations; an otherwise complete assessment with
unknown-only temperature evidence stays unscored under the unchanged rubric.

The scientific inspection receipt remains `private-scientific-inspection-v3`
(introduced by the temperature port); boundary inspection remains
`private-boundary-inspection-v2`. Source comparisons operate on the already
admitted final XML and do not change either inspector worker or receipt schema.
The prospective route advances from
`factory-assessment-boundaries-v4-temperature-v1` to
`factory-assessment-boundaries-v4-temperature-source-v1`. It identifies these
bounded ports without claiming `factory-assessment-boundaries-v7`. Current
verification rejects previous routes/inspection versions and binds worker bytes.
Review historical evidence with its original verifier; do not relabel or rescore
archived receipts automatically. Required physics, score weights, authoring
budgets and assistance conditions are unchanged.

The temperature delta is ported from experimental continuation
`1c2e805edf1303c0ebf0cfb84b2e226bf1917976`; its worker and receipt changes are
unchanged in the final v7 archive. The portable
[temperature controls](tests/test_effective_temperature.py) exercise the trusted
worker functions with loaded-value doubles and synthetic execution receipts.
They check extraction, precedence, assessment/scoring and historical/tampered
evidence rejection without importing OpenMC or running native transport.

Source comparison preserves the qualified v7 rules through two small admitted-XML
observers/comparators: [source_space.py](evaluation/scientific/source_space.py)
(`uniform-box-source-comparison-v1`) and
[source_angle.py](evaluation/scientific/source_angle.py)
(`isotropic-source-comparison-v1`). They never import candidate Python or load
private reference packages. The settings assessment retains their observations,
limitation reasons and comparison versions in `export-fidelity.json`; retained
evidence review reconstructs these values from the accepted final XML.

- Spatial: a finite ordered box or independent Cartesian Uniform marginals must
  match each required axis interval. Missing/duplicate axes, nonuniform or
  unsupported descriptions remain unresolved. Fissionability and rejection
  strategy remain separate requirements; the existing point-source path is
  unchanged.
- Angular: default/explicit isotropy or qualified independent Uniform mu in
  [-1, 1] and phi over one full 2π interval in a supported orthonormal frame.
  Directional/finite-atomic laws and demonstrated incorrect support fail.
  Unqualified frames, malformed/unsupported descriptions and multiple-turn
  azimuthal support remain unresolved. This is not a general distribution
  equivalence engine.
- A known mismatch remains a false detailed assertion and sets the settings
  status to discrepancy even beside unknown assertions. As in v7, the unchanged
  assessment aggregation leaves the combined source check null if any required
  source property is unresolved, so an otherwise complete assessment remains
  unscored. Energy/Watt, particle, source constraints and other settings checks
  retain their existing rules and numeric tolerance.

The source helpers and settings integration match the same frozen v7 continuation
identified above. Portable [spatial](tests/test_source_space.py),
[angular](tests/test_source_angle.py) and
[evidence](tests/test_source_evidence.py) controls use synthetic public XML;
execution/reference providers in evidence controls are doubles. They cover
supported encodings, wrong/unknown aggregation, unchanged constraints and
rejection of tampered comparison records or historical route identities. They
neither run neutron transport nor establish full experimental v7 parity.

Operator-side [boundary receipt verification](builder/INSPECT_BOUNDARIES.md)
also ports v7's narrow failed-call qualification. A completed, contained and
cleaned-up worker execution is distinct from a usable boundary observation.
A missing cell-material reference must be demonstrated by the retained XML and
a matching worker KeyError. It produces an operator failure record with no
observation or scientific credit; the builder's indeterminate reply and compact
feedback remain unchanged. Other failures stay insufficient. This additive
read-only verification uses the existing v2 receipts and preserves the current
assessment route, worker, comparator, budgets and historical records. The
[portable controls](tests/test_boundary_failure_receipts.py) exercise actual
controllers and verifiers with synthetic process/owner receipts, not live
builders or transport. Full experimental v7 parity is not established.

Evidence binds task/prompt, model/adapter, budgets/protocol, code/environment/data,
artifacts, process outcomes and justifications. Hashes identify bytes; they are
neither scientific proof nor protection against an operator rewriting all records.
Docker, the host controller, OS, images and data provider remain trusted. Candidate
containers receive no reference mount, credentials or host Docker socket.

## Public/private separation

Public: harness source, physical task statements, requirement comparisons, score
policy and portable synthetic regressions. Private: reference implementations and
answers, campaigns, raw model traces, native qualification evidence and external
runtime/data artifacts. Private-data tests and study-specific continuation commands
are excluded from the public snapshot, not deleted from research history.
Reference-based assessment cannot complete without private packages; missing data
must never be replaced with fabricated expectations or bypassed verification.

The private historical test count is not the public test count. Passing local
doubles does not imply native transport, calibrated uncertainty, independent
reference qualification or harness efficacy.
