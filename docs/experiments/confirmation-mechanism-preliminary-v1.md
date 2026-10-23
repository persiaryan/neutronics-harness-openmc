# Source-mechanism pre-review of the frozen 240-assignment campaign

Status: **unblinded Codex proposals; human adjudication pending**.
The [primary closeout](confirmation-240-closeout-v1.md) remains unchanged.
This phase made no model calls, candidate executions, observer runs or transports.

## Corpus and method

All 238 available final submitted sources were parsed as data, not imported.
Assignments 030 and 236 have no final source. Their mechanism outcome is
unassessable, regardless of the provider incident's original attribution.

The review combines:
- An AST-assisted screen of every source for bitwise augmented assignments,
  explicit mutator references, region/node writes, deletions and dynamic features.
- A lexical receiver audit of 662 append/extend calls. All receivers resolve to
  Python lists; two calls use the outer-scope cells list in assignment 022.
  Modifying a list of regions is distinct from changing a region's own nodes.
- Explicit source-flow inspection of all 36 bitwise-augmentation cases, including
  aliases, prior cell assignments, already derived expressions, nested children,
  later consumers and the required damaging consequence.

No dynamic exec/eval/getattr/setattr construction, direct in-place operator
reference, region/node attribute write, region transformation, from_expression
or region clone was found in this corpus. The retained sources have no custom
classes. These are bounded source observations, not a general static analyzer
soundness proof.

The OpenMC 0.15.3 operator behavior was checked against the
[versioned upstream implementation](https://github.com/openmc-dev/openmc/blob/v0.15.3/openmc/region.py)
and the project's retained native mechanism controls. Matching in-place operators
mutate their container. Ordinary matching operators create a new container while
potentially sharing children; a different operator can rebind an accumulator.
Operation order and object type therefore matter.

## Syntax and primary outcomes

| Setup | Arm | Sources available | Sources with &= or |= | Primary successes within that syntax subset |
|---|---|---:|---:|---:|
| Luna | A | 59 | 16 | 14 |
| Luna | D | 60 | 0 | 0 |
| Sol | A | 60 | 20 | 17 |
| Sol | D | 59 | 0 | 0 |

The 36 sources with this syntax comprise **31 complete successes, one evaluated
failure and four unscored outcomes**. Zero syntax occurrences in D does not
establish correct geometry or a reduction in damaging mutations. These syntax
counts are explanatory observations, not a new scientific endpoint.

## Proposed mechanism judgments

Codex's draft finds no demonstrated four-link damaging shared-region mutation
within the reviewed scope in the 238 sources. It proposes
not_observed_within_reviewed_scope for those sources and unassessable for the two
missing submissions. These are **assistant proposals**, not canonical or
human-confirmed negatives.

| Setup | Arm | AI-proposed not observed | Missing source / unassessable | Human adjudication |
|---|---|---:|---:|---|
| Luna | A | 59 | 1 | Pending |
| Luna | D | 60 | 0 | Pending |
| Sol | A | 60 | 0 | Pending |
| Sol | D | 59 | 1 | Pending |

The review was not blinded: the assistant already had campaign context and had
seen outcomes and selected source identities. The prepared human packet omits
assignment/model/arm labels, scores, provider traces and assistant proposals.
Source style can suggest condition, and source hashes can be joined to the
published aggregate. Reviewers should record their initial judgments before
consulting those artifacts. Masking is not a guarantee of blinding.

The [public pre-review aggregate](confirmation-mechanism-preliminary-v1.json)
binds the local draft and packet by hashes without publishing candidate code.

## Cases that prevent simplistic interpretation

- **085:** the accumulator initially refers to a fuel-cell Intersection. The first
  union assignment creates a new Union; later union accumulation changes that
  object, preserving the original cell region. Shared reference plus an augmented
  token is insufficient to demonstrate harm.
- **059:** the flat outer intersection is narrowed through an alias during pin
  construction. Earlier cell expressions have separate flat node sequences;
  the subsequent pin is disjoint from the pin already excluded. No harmful
  consequence is established by the source review.
- **034:** the background accumulation uses exterior radial regions where solid
  pin envelopes were needed. The proposed defect concerns sign/complement choice,
  rather than an unintended consumer observing a mutated shared region.
- **202:** the lower end-water expression has an upper axial bound but no lower
  one. At x=y=0 and z=-26 cm it admits water outside the public -25 cm exterior.
  This static witness explains a distinct domain defect; it does not change the
  original unscored verdict. The wrapper complement was constructed before the
  inner-square accumulator was narrowed.
- **195:** retained boundary evidence reports coincident surfaces with different
  behaviors. No source-level shared-region-mutation chain is established by that
  observation; effective boundary behavior still needs separate qualification.

The positive-chain definition remains unchanged. No endpoint is replaced with
counts of operators, skill mentions, source style or complete-success outcomes.

## Verification

The complete documented portable suite passed **687 tests**, including eleven
mechanism-review controls. These exercise safe-versus-unsafe syntax ambiguity,
method and closure receivers, non-execution of top-level candidate code, declared
AI/human separation, source/task/criteria tampering, forbidden writes into frozen
evidence, public-draft labeling and the unexecuted status of future qualification.
The real 238-source packet imported successfully as AI proposals under the
hardened bindings. All 55,781 original sealed files verified unchanged afterward.

## What this adds and what remains open

The available evidence shows a clear difference in explicit construction style:
36 augmented region-construction sources in A versus none in D. The draft does
not demonstrate the harmful baseline defect that would be needed to support a
claim that D prevented it in this twelve-task corpus. Human adjudication can
confirm or revise these proposals.

The absence of a demonstrated targeted defect does not make all source models
correct. Known geometry/settings failures and all eighteen primary unknowns
remain. Working revisions are outside this final-source endpoint: the draft
does not establish whether an agent introduced and repaired this defect earlier.

This supports treating the completed campaign as a bounded null/mixed outcome
with a style shift and measurement limits, rather than presenting reduced
operator use as reduced scientific error. The next-study question should be
chosen after human adjudication and evaluator qualification.

## Reproduce and complete the review

```sh
python3 -B confirmation_mechanism_review.py prepare \
  --frozen scratch/indc107-closeout-v1 \
  --output scratch/indc107-mechanism-review-v2
python3 -B confirmation_mechanism_review.py import \
  --frozen scratch/indc107-closeout-v1 \
  --prepared scratch/indc107-mechanism-review-v2 \
  --review scratch/indc107-mechanism-review-v2/assistant-review-draft.json \
  --reviewer-type ai \
  --output scratch/indc107-mechanism-review-v2/assistant-analysis.json
```

For independent human review, use only anonymous-source-review/README.md,
measurement-definition.json, unchanged sources/tasks and review-template.json.
Supply a named reviewer, reviewer_type=human, four explanatory fields, source
hashes, line references and limitations. Preserve uncertain/unreviewed cases.
Import a new review file with --reviewer-type human and a fresh output path.
The validator checks declared type and traceability; it does not authenticate a
human identity or certify a judgment's scientific truth.

Canonical campaign annotation templates and all original verdicts stay intact.
Future evaluator work and study decisions are specified separately in the
[next-phase plan](confirmation-next-phase-plan-v1.md).
