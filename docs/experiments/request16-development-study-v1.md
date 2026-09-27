# Request-16 A/B/C development study

**Complete development study · 150 terminal assignments · zero retries**

The question is whether domain-specific scientific feedback improves an agent's
ability to turn an engineering specification into a conforming OpenMC model.
The experiment evaluates assistance packages and agent setups, rather than
assuming that more tools imply better modeling.

This is a public summary of the frozen completed-study report identified under
[Provenance](#provenance). It adds no experimental observations or statistical tests.

## Design and conditions

Two frozen model-specific agent setups, GPT-5.6 Luna and GPT-5.6 Sol, each received
three assistance conditions on five reused tasks, with five authoring repeats per
task/condition. Each session had **16 requests and 600 authoring seconds** under
`authoring-requests-16-v1`. Task order and budgets were frozen; consumed assignments
were never retried or replaced.

| Condition | Authoring assistance |
|---|---|
| A: guided construction | Generic coding/OpenMC tools, a required working-export attempt, and bounded construction-error repair |
| B: guided boundaries | A plus boundary observations and guidance on using them |
| C: guided smoke | B plus guided short native OpenMC execution feedback |

A is not tool-free. B−A varies tool access and guidance together. C−B measures
incremental smoke assistance with boundaries already available, not a smoke-only
comparison. The setups are not otherwise identical bare-model interventions.

The tasks are `reflective_pin_cell`, `reflected_7x7`,
`two_composition_5x5`, `axially_zoned_5x5`, and `asymmetric_5x5`.
These development tasks had been used previously; repeated authoring on them is
not holdout generalization.

## Independent final assessment

The builder submits frozen Python with the contract
`build_model() -> openmc.Model`. A separate factory performs one final export.
Fresh inspections and separate native transport consume the admitted final XML;
the builder's working exports, observations and self-reports do not set the grade.
There is no LLM judge.

Under `factory-assessment-boundaries-v7`, verified protocol success requires
coherent evidence, completed assessment and all implemented required checks
passing within declared coverage. Unknown or unreached checks are not passes.
Deterministic comparison rules operate on inspected properties and numerical
evidence; the underlying transport is Monte Carlo. A finite geometry check is
not a proof of global validity.

The secondary rubric is `weighted-keff-score-v2`, with a fixed 70-point denominator
normalized to 100. Tool use earns no scientific points; a high partial score does
not replace strict success.

## Primary and secondary results

Each arm has 25 started assignments and equal task weights.

| Agent setup | A | B | C | Primary C−A | Secondary B−A | Secondary C−B |
|---|---:|---:|---:|---:|---:|---:|
| GPT-5.6 Luna | 72% | 68% | 56% | −16 pp | −4 pp | −12 pp |
| GPT-5.6 Sol | 92% | 100% | 84% | −8 pp | +8 pp | −16 pp |

In this bounded development study, the combined boundary + smoke assistance
package did not improve verified protocol success relative to guided construction.
Observed differences varied by setup and task. These observations do not establish
general causality or an agent's internal understanding.

![Verified protocol success by setup and condition](../assets/request16-success-rates.svg)

### Task results

Each entry is verified successes out of five assignments.

| Setup | Task | A /5 | B /5 | C /5 |
|---|---|---:|---:|---:|
| Luna | axially_zoned_5x5 | 3 | 4 | 4 |
| Luna | reflective_pin_cell | 4 | 4 | 4 |
| Luna | asymmetric_5x5 | 4 | 3 | 4 |
| Luna | reflected_7x7 | 2 | 3 | 1 |
| Luna | two_composition_5x5 | 5 | 3 | 1 |
| Sol | axially_zoned_5x5 | 5 | 5 | 3 |
| Sol | reflective_pin_cell | 5 | 5 | 5 |
| Sol | asymmetric_5x5 | 4 | 5 | 4 |
| Sol | reflected_7x7 | 5 | 5 | 4 |
| Sol | two_composition_5x5 | 4 | 5 | 5 |

Luna's declines concentrate in reflected and two-composition models, whereas its
axial result improves relative to A. Sol's axial/asymmetric results decline; its
reflected C cell contains the unscored incident, and two-composition improves
relative to A. The pattern is not uniform across tasks.

### Uncertainty

The frozen report's **Wilson 95% intervals for five-assignment task cells** are
reproduced below as a compact lookup for the preceding table.

| Successes /5 | Wilson 95% interval |
|---|---|
| 1/5 | 4%–62% |
| 2/5 | 12%–77% |
| 3/5 | 23%–88% |
| 4/5 | 38%–96% |
| 5/5 | 57%–100% |

These are descriptive cell intervals, not a new pooled IID interval or a
significance test of the contrasts. Unresolved identification bounds answer a
different question: how much the unknown incident could change the rate without
imputing an outcome. Sol/C reflected is bounded at 80–100%, and Sol/C overall at
84–88%. Other identification bounds equal their verified rates. Incident 067
stays in the denominator and is not assigned a scientific zero or a success.

## Outcome composition and numerical checks

| Exclusive terminal category | Assignments |
|---|---:|
| Verified protocol success | 118 |
| Demonstrated physical violation | 19 |
| Model hard-gate failure | 12 |
| Provider/stream incident | 1 |

A hard-gate failure can also contain observed physical violations. No separate
numerical-only or coverage-only terminal category occurred; this does not imply
that every requirement in every assessment was resolved.

Numerical comparisons yielded **134 agreements, three resolved discrepancies,
and 13 unreached comparisons** (12 gates and the incident). All three discrepancies
were in Luna A/B; none was in C. Numerical agreement did not compensate for
geometry or settings violations.

Family-level counts below are **check verdicts across 149 verified reports**,
not independent trial counts. Incident 067 supplies no scientific checks.

| Family | Passed | Failed | Unresolved |
|---|---:|---:|---:|
| Engineering consistency | 274 | 0 | 24 |
| Geometry | 548 | 36 | 12 |
| k-effective | 134 | 3 | 12 |
| Materials | 588 | 0 | 8 |
| Physics settings | 569 | 19 | 8 |
| Statistical quality | 274 | 0 | 24 |

Scores are available for 149/150 assignments, including 12 justified gate zeros.

| Setup | Arm | Available scores /25 | Available-score mean | Full-arm mean |
|---|---|---:|---:|---:|
| Luna | A | 25/25 | 85.86 | 85.86 |
| Luna | B | 25/25 | 92.00 | 92.00 |
| Luna | C | 25/25 | 86.71 | 86.71 |
| Sol | A | 25/25 | 92.00 | 92.00 |
| Sol | B | 25/25 | 100.00 | 100.00 |
| Sol | C | 24/25 | 87.50 | null |

## Effort and actual feedback delivery

The following retained totals include incident 067's recorded effort. Final
assessment costs are separate from authoring allowances.

| Setup | Arm | Requests | Authoring seconds | Boundary attempted / completed / delivered | Smoke attempted / native-completed / delivered |
|---|---|---:|---:|---|---|
| Luna | A | 153 | 3012.61 | 0/0/0 | 0/0/0 |
| Luna | B | 154 | 3186.49 | 30/30/30 | 0/0/0 |
| Luna | C | 189 | 3814.51 | 27/27/27 | 30/28/29 |
| Sol | A | 102 | 2249.04 | 0/0/0 | 0/0/0 |
| Sol | B | 135 | 2598.34 | 26/26/26 | 0/0/0 |
| Sol | C | 147 | 2849.53 | 25/25/25 | 24/24/24 |

Delivery means a retained later request contained the feedback. It does not prove
comprehension or repair. A smoke reply can convey a runtime error rather than
native completion. A/B have no smoke capability. Incident 067's boundary feedback
entered its failing request, so no subsequent model decision is established.
Missing token usage for that request remains missing.

## Evaluator amendment and incident handling

A demonstrated temperature-representation evaluator defect prompted a v6-to-v7
amendment: pinned OpenMC could load an explicit single cell temperature as a
finite singleton list, which the old inspection rejected. The correction accepts
qualified scalar-equivalent representations without changing the physical values,
score rubric, task requirements or assistance conditions.

All **38 already-started assignments were uniformly and separately reviewed under
v7**. **37 outcomes were unchanged**; one evaluator-stop candidate, 038, became a
verified success. Original v6 outcomes and authoring remained preserved. The
review reused retained exports and native evidence where available; 038 received
its first missing final native observation, not a new builder attempt. Subsequent
execution used v7. The reported comparison uses the separate v7 assessments for
the inherited assignments, not a mixture of original v6 and v7 scores.

Incident **067** remained `provider_or_stream_incident`, with root cause
`cause_not_established`, no submission, no assessment and `score=null`.
Explicit operational reconciliation permitted continuation only through unstarted
slots. The incident was permanently consumed and never retried; the continuation
introduced no new incident.

## Limits and interpretation

- Five reused development tasks and small task cells do not establish holdout
  performance or universal OpenMC correctness.
- Results compare different frozen model-specific agent setups. Guidance and tool
  availability vary together; model weights and tool effects are not isolated.
- Transport used fixed native seed 1. Repeats vary authoring, not independently
  reseeded transport.
- Boundary and geometry inspection have bounded coverage. Finite probes can miss
  localized overlap; unresolved observations must remain visible.
- The ±150 pcm equivalence margin is an uncalibrated internal design choice.
  Scientific reference review and numerical calibration remain future work.
- The retrospective mechanism analysis addresses observed paths, not the causal
  explanation of the aggregate C−A difference.

## Provenance

These are identities in the separate experimental research archive, **not commit
links in this public repository**. Raw traces, reference answers, native files and
provider content are intentionally not vendored. A hash identifies a source record;
it does not make the underlying private evidence independently available.

| Record | Frozen identity |
|---|---|
| Completed-study closeout | `59f370f54c5edb3f6499af37259e3ae09d3e9ca7` |
| Mechanistic analysis tooling | `251b99ce5339fdb6ca4027a226f72b433a066205` |
| Mechanistic report and evidence | `19aa097455e8270ae1e5cfaa58f1a6f33e4b111e` |
| Original v7 execution | `8dae2e5a9ab835af2746a77adcaa10d4faf267c7` |
| Pending-only continuation | `1c2e805edf1303c0ebf0cfb84b2e226bf1917976` |
| Scientific protocol | `factory-assessment-boundaries-v7` |
| Authoring profile | `authoring-requests-16-v1` |

Rates, task cells and Wilson bounds are transcribed from **Completed request-16
A/B/C development study — Primary and secondary contrasts**. Outcome, check and
score tables come from **Failures, unresolved checks and numerical outcomes**;
effort comes from **Effort and feedback delivery**. Amendment details come from
the closeout-bound **Uniform v7 retained-input review**. No new rates, substituted
outcomes or balanced comparison have been computed for this publication.

The public implementation remains the earlier source release:
`e1b9a59d7b412ffb3d7adeae17fc66d53699da79`, with the A/B workflow and v4
assessment route described in [DESIGN.md](../../DESIGN.md). The later v7/C study
implementation is not included by this documentation update.

The chart uses only the frozen rates in
[request16-success-rates.json](../assets/request16-success-rates.json).
Reproduce it without dependencies from the repository root:

```sh
python3 -B docs/assets/render_request16.py
python3 -B docs/assets/render_request16.py --check
```

See the [results index](../../RESULTS.md) and [public usage](../../README.md).
