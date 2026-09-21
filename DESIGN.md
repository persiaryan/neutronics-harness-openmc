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
`factory-assessment-boundaries-v4`, boundary observer v2. There is one independent
final export, not a repeat-build stability grader. Working exports are authoring
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
