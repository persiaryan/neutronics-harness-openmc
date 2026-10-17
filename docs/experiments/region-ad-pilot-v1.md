# Frozen preparation of the A/D region-ownership pilot

This is the original **36-assignment A/D development pilot**, separate from E.
A is guided construction; D adds the entire fixed procedure to the initial
prompt. The same model-specific generic tools, instructions, reasoning, request
profile and time budgets apply within each A/D comparison.

## Recorded operational checkpoint — 2026-10-17

The real preparation is `scratch/region-ad-pilot-36-v2`. Its 435 portable tests,
four native A/D controls and four real provider-transmission controls passed.
See the [historical prelaunch receipt](region-ad-prelaunch-v1.json). The pilot
ran from 2026-10-17 14:07 to 17:25 UTC and completed all 36 assignments.
The [terminal report](region-ad-pilot-result-v1.md) and
[aggregate JSON](region-ad-pilot-results-v1.json) record 30 complete successes,
six evaluated failures and no incidents. Source-review proposals remain separate
from human-confirmed mechanism annotations. The prelaunch receipt describes its
own phase; canonical execution state belongs to the local progress.json.

## Scientific protocol

The executable preparation freezes
[region_ad_protocol.json](../../experiments/region_ad_protocol.json) and the exact
[skill body](../../builder/skills/openmc-region-ownership/SKILL.md). Its SHA-256
is `93a7cb7746b7baaa22bad948473ddd596d6c2807079bd92596fdb1f4e3a9d416`.

The procedure was reread for this preparation. It correctly distinguishes
Python aliasing, shared OpenMC intersections/unions, complements, cell references,
and shared nested children. It explicitly permits intentional unshared in-place
construction and does not claim global geometry validity. No task-specific
answers, repair policy or grader changes were added. Existing small OpenMC
controls demonstrate the programming mechanism; their success does not establish
an effect on an LLM.

The frozen primary measure is **complete independent protocol success**, using
the retained-evidence verifier and an assessed final model. A skill mention,
receipt or corrected operator syntax earns no scientific credit.

There are two model configurations, two arms, three reused tasks and three
repeats: 36 assignments. Each has 16 requests and 600 authoring seconds, for
at most 576 pilot model requests. Independent final assessments retain the
existing export/inspection/transport budgets. All consumed slots, incidents and
unstarted assignments remain explicit. No retries or replacements are automatic.

The analysis reports, by model × task × arm:

- Protocol successes, evaluated model failures, unscored incidents and pending slots.
- All-assigned success fractions after that cell is terminal, plus conditional
  success among scored assignments, with its changed denominator explicit.
- Targeted-defect annotation counts, preserving missing and uncertain cases.
- Independent geometry/settings findings and available authoring/assessment effort.
- Equal-task-weight descriptive D-minus-A comparisons within each model, only
  when all its cells are terminal.

A pending assignment is not a model failure or a measured zero success rate.
This is an exploratory development comparison, without a powered significance
claim or held-out generalization claim.

## Recognizing the secondary defect

A positive `demonstrated` annotation requires evidence for all four links:

1. The same region object is shared before mutation, possibly through an alias,
   an assigned cell or a nested component.
2. An operation changes that same shared mutable Intersection or Union in place.
3. A downstream cell, complement or expression observes the changed object.
4. That change conflicts with the public geometry requirement or the construction
   meaning that needed preservation, supported by independent geometry evidence
   or an explicit semantic derivation.

The presence of `&=` or `|=` alone does not meet these criteria. An operation on
an unshared object can be correct. A new outer expression does not prove that
nested components were copied.

`not_observed_within_reviewed_scope` requires a documented review of the submitted
geometry's aliases, mutations, shared children and downstream uses.
`unassessable` covers missing submissions and unresolved evidence.
`pending` means review has not been completed. No unknown case becomes a negative
annotation.

The initial endpoint concerns the **final submitted source**. Working revisions
are process evidence and must be described separately. Manual annotation is bound
to the final source hash, a named reviewer, four explanatory fields, coverage
limitations, and campaign-relative artifact hashes and line references.
The validator checks traceability, not the scientific truth of the human judgment.
Review blinded to arm where feasible; adjudicate uncertain positives before
reporting them. Never import candidate Python on the host to perform this review.

## Qualification and preparation

`experiments.region_ad.dependencies` performs local technical checks without
model inference or neutron transport:

- Availability of the existing login token, without logging identity or credentials.
- Exact immutable Linux ARM64 image identities for authoring, export and transport.
- OpenMC Python versions and native OpenMC version and binary/library/worker hashes.
- Seals of the private suite and packages, public-task compatibility, and exact
  required nuclear-data content hashes for each of the three tasks.
- Agreement between the frozen reference runtime and active assessment profile.

These checks do not approve the scientific reference: review remains
`pending_owner_review`, with `grading_enabled=false`. The check reads only the
data directory explicitly supplied by the operator and the existing private
reference paths. Nothing private enters the builder.

Preparation uses the existing reviewed per-model setup objects. Luna retains
medium reasoning; Sol retains low reasoning. It does not silently adopt a new
request configuration from a failed probe.

~~~sh
python3 -B -m experiments.region_ad prepare \
  --data-index "$DATA_INDEX" --setups "$REVIEWED_AD_SETUPS" \
  --output scratch/region-ad-pilot-36
~~~

This writes the real 36-slot manifest, a separate manifest seal, frozen protocol
and procedure snapshots, the local qualification receipt and an
`annotations-template.json`. It dispatches no model. The manifest is deliberately
not launchable until the separate controls pass.

## Separate technical controls

First qualify the actual pinned CLI for A and D in each model configuration:

~~~sh
python3 -B -m experiments.region_ad qualify-native \
  --output scratch/region-ad-pilot-36
~~~

These four sessions use scripted responses and no provider. They verify the exact
A/D prompts, D's complete preloaded bytes and matched effective CLI setups.

The following is a **live** operation. Run it only with a separately agreed budget:

~~~sh
python3 -B -m experiments.region_ad probe-provider \
  --output scratch/region-ad-pilot-36
~~~

It allows **four provider requests total**, one for each model × A/D, with
120 seconds per session. The public two-composition task is used for transmission
qualification; these controls are excluded from pilot outcomes and must not be
used to tune the procedure. Each request uses the frozen 16-request guidance,
but the host caps the control at one provider request. A subsequent requested turn
can therefore stop at the cap; this does not invalidate a complete first-response
delivery receipt. No successful model submission or scientific assessment is
claimed by this control.

A qualifying receipt needs the exact initial prompt, expected model and setup,
D's exact snapshot, a complete valid provider response and corresponding successful
upstream diagnostics, the pinned controller/image, and confirmed cleanup.
A mock response, retained request alone or HTTP 200 alone cannot qualify it.
This is bounded evidence of compatibility of the existing subscription relay,
not a provider attestation of comprehension or long-term service reliability.

Each control batch is consumed once. A failure preserves artifacts and stops the
batch. A new attempt requires an explicit decision and fresh preparation; no
retry or evidence replacement occurs automatically.

~~~sh
python3 -B -m experiments.region_ad check \
  --output scratch/region-ad-pilot-36
~~~

Readiness compares reference/data/runtime identities with the frozen local
receipt, so even a newly sealed replacement reference cannot silently enter the
study. It also rechecks current local dependencies and the actual
native/provider control evidence. The serial campaign runner invokes this gate
before writing a launch record or consuming any pilot slot.

## Pilot execution and analysis

The next command launches the separate, budgeted 36-assignment pilot:

~~~sh
python3 -B -m experiments.dashboard_campaign run \
  --output scratch/region-ad-pilot-36
~~~

An incident pauses execution; a consumed campaign cannot silently resume or
replace its failed slots. Reference packages, procedure, protocol, source and
request configurations must retain their frozen identities.

Copy the annotation template to a new file and fill it after reviewing retained
final-source and geometry evidence. Produce analysis in a fresh output:

~~~sh
python3 -B -m experiments.region_ad_analysis \
  --campaign scratch/region-ad-pilot-36 \
  --annotations scratch/region-ad-pilot-36/annotations.json \
  --output scratch/region-ad-pilot-36/analysis.json
~~~

The analysis revalidates final assessment evidence with the existing independent
verifier. Missing assessments stay unscored. Annotation fields do not affect
primary success. Raw requests, references and transcripts remain local.

A reduction of the alias defect without better complete protocol success is a
local mechanism benefit. Better success on these reused tasks is development
evidence. Neither result alone establishes broad skill efficacy.

## Confirmation after the pilot

Use the pilot to assess feasibility and variability. Before confirmation,
justify the sample size, define new task families or geometry variants and
create a separately frozen held-out manifest, annotation procedure and analysis.
Do not generate or tune on confirmation outcomes during this pilot. No held-out
tasks or confirmation results are claimed by this implementation.

## Verification

~~~sh
python3 -B -m unittest tests.test_region_ad -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
~~~

## Interpretation boundaries of A/D

The randomized order and matched within-model setups compare the complete D
intervention with A under this harness. D adds both specific region-ownership
content and additional initial instructions/context. There is no length-matched
or generic-instruction placebo. The pilot therefore cannot separately attribute
an observed difference to technical content rather than the other consequences
of adding that procedure. Any such decomposition needs a separately frozen design.

Three repeats per task/arm yield coarse cell rates and substantial uncertainty.
A positive descriptive difference motivates confirmation; a null or mixed
difference does not establish equivalence or prove that useful effects are absent.
A task at ceiling provides little information about improvement on that task.
Report all twelve cells, including unfavorable outcomes, before interpreting
aggregates. Do not select a model or task subset after seeing its favorable rate.

Confirmed mechanism annotations could support a narrow explanation of specific
failures. They do not prove that a model understood the instructions, and source
style is not a substitute for independent final assessment. The A/D pilot does
not test spontaneous catalog discovery, agent-selected loading, or condition E.
