# Preloaded region-ownership procedure and condition D

## Scope and scientific status

D is A's guided construction plus the complete preloaded
[openmc-region-ownership](../../builder/skills/openmc-region-ownership/SKILL.md)
procedure. It has A's tools and budgets, without boundary inspection, native
smoke, a detector, automatic repair or scientific credit.

This is provided instruction assistance maintained as a skill, not native skill
discovery. In D, the builder rejects a skills catalog and personal memory in its
first request. Only the allowlisted procedure enters its ordinary prompt; the
repository and private evaluation are not exposed.

The eight examples in the [closeout](campaign-150-rerun-01.md#failure-analysis)
motivated the intervention. The evaluator detected geometry defects;
retrospective source analysis identified the shared mutable-region pattern.
This change does not automatically diagnose that cause. D's efficacy is
**not tested**. The independent evaluator, public physics, references, rubric,
thresholds and historical results are unchanged. Scientific review is pending
and grading remains disabled.

## Evidence boundary recorded on 2026-10-17

At implementation commit `32d9ab2`, D supplies the complete procedure in the
initial authoring prompt. The SKILL.md filename and frontmatter do not make this
an agent-selected, progressively loaded skill experiment.

| Capability or result | Status at this checkpoint |
|---|---|
| Read the allowlisted procedure and preload its complete content in D | Implemented; portable plumbing tests passed |
| Expose only skill name/description/path initially | Not implemented |
| Let the builder decide to load the body when relevant | Not implemented or tested |
| Observe an actual builder loading and applying the skill on demand | Not tested |
| Demonstrate improved LLM modeling from the preloaded procedure | Not tested |
| Demonstrate OpenMC region mutation behavior in small controls | Tested separately; no LLM or neutron transport |

No result from this checkpoint may be presented as evidence of automatic skill
selection, on-demand loading, or skill efficacy. Preloading verifies a different
intervention: providing specialized instructions. A later automatic-loading
condition should preserve D as its own preloaded-instruction comparison, carry
a new configuration identity, and distinguish catalog exposure, observed body
loading, and behavioral effects. This dated checkpoint remains historical if
those capabilities are subsequently implemented.

A later implementation on 2026-10-17 adds separate [condition E](region-skill-selective-v1.md)
for native metadata discovery and optional reading. Its offline controls are
scripted; automatic LLM selection and efficacy remain untested. The table above
describes the earlier checkpoint and is intentionally preserved.

## Critical path and evidence

1. builder.region_skill.material reads one bounded, non-linked source file.
   Its identity records ID, version, byte count, SHA-256 and preloaded delivery.
2. builder.route.condition_prompt appends it to A's prompt for D. Fixed hashes
   from ecb7624 check every A/B/C prompt for six public tasks and both profiles.
3. experiments.run.prepare saves the exact procedure snapshot and its identity
   alongside the existing full authoring-prompt hash.
4. execute checks the binding before dispatch. The builder checks the prepared
   identity before authentication or Docker access, then saves its own snapshot.
5. builder.submission.submission checks the identity, snapshot, reconstructed
   prompt and first retained request; provenance carries the procedure identity.
   A/B/C reject undeclared procedure metadata or snapshots.

Changing source after preparation, altering/removing a snapshot or omitting its
identity invalidates D. Historical D evidence requires its original procedure
version. Hashes do not prevent an operator rewriting all records. A retained
request alone does not establish provider receipt, comprehension or application.

## Small controls with real OpenMC

builder/region_ownership_controls.py is explicitly invoked; it is not staged
into the builder or used by the grader. Literal slab/union examples compare
point membership with analytic expectations. They use no candidate, private
reference, nuclear data or neutron transport.

The controls cover shared intersection mutation, an assigned cell observing it,
a changed complement, non-mutating construction, intentional unshared in-place
construction, unions and a nested shared child. A new outer expression is not a
deep copy. Executed on 2026-10-16 with the existing pinned authoring image:

~~~sh
docker run --rm -i --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges=true --user 1000:1000 \
  --memory 1g --cpus 1 --pids-limit 64 \
  --tmpfs /tmp:rw,nosuid,nodev,size=67108864,mode=1777 \
  --env MPLCONFIGDIR=/tmp/matplotlib --entrypoint python3 \
  sha256:8dfbafd6160d9833111ac51d0b066126066f1690d3c315261583baf5f12b81a5 \
  -I -B - < builder/region_ownership_controls.py
~~~

[Allowlisted result](region-ownership-controls-v1.json): OpenMC 0.15.3,
12 assertions passed, exit zero. The script digest binds the tested bytes.
There were no network or host mounts. This establishes the small programming
mechanism, not global geometry validity or skill efficacy. The existing image
is a local dependency, not a new public acquisition recipe.

## Portable preparation

Preparation creates no model calls, Docker processes or transport:

~~~sh
python3 -B -m experiments.run prepare \
  --assistance guided_construction_region_ownership \
  --request-budget authoring-requests-16-v1 \
  --cases two_composition_5x5 axially_zoned_5x5 reflective_pin_cell \
  --output scratch/region-skill-D
~~~

Prepare a contemporaneous A control in another fresh directory with the same
model, cases/profile and assistance guided_construction. Eight requests remain
the default; selecting the 16-request profile is explicit.

## A/D development pilot preparation

The comparison region-ownership-ad-v1 prepares 36 pending assignments:
two retained model setups x A/D x three development tasks x three repeats.
Each has 16 requests / 600 seconds: at most 576 requests. Order uses reproducible
shuffle seed 20261016. Historical A results are not substituted for fresh controls.

This comparison is separate from the public-reference --pilot; combining them
is rejected. Final assessment requires the existing private task references,
not the one public demonstration reference. With a real operator-selected data
index and reviewed request setup file:

~~~sh
python3 -B -m experiments.dashboard_campaign prepare \
  --comparison region-ownership-ad-v1 \
  --data-index "$DATA_INDEX" --setups "$SETUPS" \
  --output scratch/region-skill-ad-36
~~~

Only preparation is authorized by these commands. The separate run action makes
live model calls and native final assessments; it is **not part of offline
validation**. The initial implementation was validated offline; the subsequent
[frozen A/D workflow](region-ad-pilot-v1.md) records real provider qualification
and the separately executed development pilot. See its
[completed results](region-ad-pilot-result-v1.md). Portable tests
prepare a complete synthetic campaign. Their placeholder data and setups are
test doubles, not provider or nuclear-data qualification.

The pilot is exploratory: three repeats and reused tasks are not a power
calculation or held-out generalization test. Report strict protocol success
using all assigned slots, and separate geometry defects, other defects,
incidents, requests, available tokens and time. Mechanism annotation distinguishes
demonstrated alias mutation, no observed defect within coverage and unassessable
source. The retrospective syntax recognizer is not a new scientific gate.

The existing runner pauses on incidents, without automatic retries/replacements.
The previous permissive continuation controller is not extended here.

## Verification and next step

~~~sh
python3 -B -m unittest tests.test_region_skill -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
~~~

Portable checks cover exact A/D differences, unchanged A/B/C prompts/budgets,
absence of extra adapters, preparation/controller/submission binding, altered or
absent source metadata/snapshots, first-request context, undeclared assistance
and balanced 36-slot preparation. They cannot establish live uptake or efficacy.

Before a live pilot: review the frozen skill, qualify effective provider settings,
check private reference/data/runtime readiness and explicitly authorize execution.
Before a confirmatory paper: freeze mechanism annotation, analysis and sample size;
review references/thresholds; use held-out tasks without tuning on their outcomes.

The subsequent [frozen A/D pilot workflow](region-ad-pilot-v1.md) implements the
scientific protocol, dependency checks, separate transmission controls and
annotation/analysis preparation. Its live launch remains a separate operation.
