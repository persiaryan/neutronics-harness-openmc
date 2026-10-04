# Request-16 mechanistic follow-up

> Historical campaign 1 archive. The primary results are now [campaign 2](../../RESULTS.md).
> This report retains its original protocol, findings and evidence scope.

**Exploratory retrospective analysis**

This analysis examines observed failure paths after the development-study outcomes
were known. It is not a preregistered causal explanation of the lower C rate.

## Scope and method

All **50 C assignments** were inspected; final outcomes and effort from all
**150 assignments** supplied A/B/C comparisons. The analysis used retained source
versions, export artifacts, XML sections, execution receipts, request/response
ordering and actual feedback delivery. It made **no LLM calls, candidate
executions, factory exports, transport runs or grader reruns**. Historical files
and scientific outcomes were unchanged.

Evidence strength is property-specific. Direct artifact/receipt linkage can
establish that a particular defect persisted or a particular property changed.
A partial-state or default-value inference is weaker. Model prose and temporal
sequence alone do not establish repair, regression or internal reasoning.

Reconstructed source text comes from retained completed file-change events and
literal patches; it is not an independent filesystem snapshot. Final-answer
source changes are tracked separately from workspace writes. Matching relevant
XML sections supports persistence; unequal hashes alone do not prove different
physics. Unrecognized dynamic writes remain a coverage limitation.

## Main finding

Of the **15 C non-successes**:

| Retained trajectory finding | Assignments | Evidential limit |
|---|---:|---|
| Final demonstrated defect already present before first smoke | 12 | Strong property-specific pre/final artifact linkage |
| Final-submission regression after completed smoke | 1 | Strong construction/API regression evidence; no causal attribution to smoke |
| Never reached smoke | 2 | No pre/post-smoke comparison available |

Thus **13/15** have strong property-specific pre/post evidence; this is not a count
of regressions. The remaining two include a factory failure and the unscored
provider/stream incident.

Retrospective trajectory analysis found that 12 of the 15 C non-successes already
contained their final defect before smoke. Successful smoke execution did not
certify task-level conformity. Runtime-error feedback could still support useful
repairs. The analysis does not establish that smoke caused the aggregate
performance difference.

## What a smoke run can observe

A short native run is primarily an execution/runtime diagnostic. It does not
certify compliance with the whole public specification. The diagnostic copy
replaces sampling and scheduling settings, so its completion does not validate
the original task's sampling settings. Temperature requirements and finite
geometry defects can also remain undetected by a completed smoke.

Across C, **48 sessions used smoke**, and **47 had at least one completed smoke**.
Of those 47, **12 ended as non-successes**: 11 retained defects not discriminated
by clean smoke, and one changed the final submitted source. These are retained
counts, not a new percentage or significance estimate.

The original feedback already disclosed its limits and made no task-conformity
claim. The observed coverage limitation is not a demonstrated relay/tool bug.
It also does not explain why C initially generated more of certain defects than
A/B, or what the same sessions would have produced under another condition.

## Different patterns in Luna and Sol

### Luna: settings-heavy non-successes

Luna/C had eight demonstrated physical-violation outcomes and three hard-gate
failures. All eight settings-failing sessions had identical relevant pre-smoke
and final settings XML: temperature tolerance or method mismatches persisted;
one also had the wrong generations per batch. These are specification mismatches,
not demonstrated numerical disagreement.

Two further sessions retained geometry failures: 029 had overlapping geometry
despite completed smoke; 147 retained an empty/outside root geometry after a failed
smoke and a comment-only edit. Trial 070 failed factory construction before
reaching smoke. There were no C numerical discrepancies.

### Sol: overlaps, a final-submission regression and an incident

Sol/C had two pre-existing geometry-overlap failures, 006 and 057, despite completed
smoke; one final-submission construction regression, 016; and incident 067.
There were no final Sol settings failures. The common cross-setup observation is
limited specification coverage, but the dominant failure families differ.

### Trial 016: working source and final submission diverge

The working source used `Box(..., only_fissionable=True)), exported successfully
and completed smoke. The final submitted source changed that API call to
`Box(..., constraints=...)`. Independent final factory construction then failed
with an unexpected-keyword `TypeError`.

No post-smoke workspace edit or re-export of that final submission was established.
This is a **final-submission regression**, not evidence of general workspace
over-editing. A deprecation warning appeared earlier, but the records do not
establish why the agent changed the API or that smoke caused it.

## Repairs and counterexamples

| Trial | Observable change and subsequent outcome | Limit |
|---|---|---|
| 013, Luna/C | After completed smoke, changed temperature interpolation to nearest; final assessment succeeded | A useful post-smoke correction, not evidence that smoke identified the mismatch |
| 049, Luna/C | After completed smoke, added explicit nearest/tolerance settings; final assessment succeeded | The pre-change default-value inference has moderate strength |
| 101, Luna/C | Lost-particle feedback preceded addition of missing guide-bore water; later smoke completed and final geometry checks passed | Another pre-existing temperature-tolerance mismatch remained, so overall assessment was non-success |

Trial 029 also corrected a temperature option while retaining overlapping geometry.
A repair of one property and overall non-success can coexist. No successful C
session in this dataset followed a failed native smoke; 101 is the strongest
runtime-repair example and retains its final settings failure.

## Effort and the over-editing hypothesis

Reported means include all 25 assignments per setup/condition and the incident's
recorded effort. They are descriptive, without a causal interpretation.

| Setup | Arm | Requests | Authoring seconds | Working-export attempts | Completed candidate workspace writes |
|---|---|---:|---:|---:|---:|
| Luna | A | 6.12 | 120.50 | 1.60 | 1.72 |
| Luna | B | 6.16 | 127.46 | 1.60 | 1.76 |
| Luna | C | 7.56 | 152.58 | 1.52 | 1.68 |
| Sol | A | 4.08 | 89.96 | 1.08 | 1.08 |
| Sol | B | 5.40 | 103.93 | 1.12 | 1.12 |
| Sol | C | 5.88 | 113.98 | 1.04 | 1.04 |

C used more requests and authoring time, but did **not** have more mean working
exports or completed workspace writes. **Broad harmful workspace over-editing
is not supported.** The single final-answer regression and the successful
corrections must both be retained.

Write counts include initial creation and only recognized completed file-change
receipts. Export attempts use a bounded literal-command recognizer. Request count
is not edit count; issuing an edit is not proof it persisted. Extra effort can
follow a defect rather than cause one.

## Task heterogeneity

The [full task table](request16-development-study-v1.md#task-results) remains
essential context. Luna's lower C success concentrates in reflected and
two-composition tasks, while axial C exceeds A and the pin task is unchanged.
Sol's losses relative to B occur in axial/asymmetric tasks and the reflected
incident; its pin and two-composition cells are unchanged. Sol C exceeds A on
two-composition. No single aggregate mechanism describes every task.

## Which hypotheses are supported?

| Hypothesis | Assessment |
|---|---|
| Completed smoke can coexist with task-conformity defects | Supported by retained artifact and final-assessment evidence |
| Runtime feedback has limited specification coverage | Supported within this tool's declared scope |
| Pre-existing final defects often persist | Supported by property-specific pre/final comparisons |
| Broad over-editing explains the lower C rate | Mixed evidence overall; broad harmful workspace over-editing is not supported |
| Added trajectory complexity causes failure | Mixed descriptive evidence; causation is not established |
| Smoke universally harms or improves agents | Not supported |
| Internal confidence, misunderstanding or attention explain the result | Not testable from retained evidence |

These conclusions describe observable trajectories. They neither infer internal
understanding nor establish the causal source of the aggregate C−A difference.

## Three prospective interventions

These are questions for future experiments, **not implemented or validated fixes**.

| Candidate intervention | Evidence motivating it | Prospective comparison and trade-off |
|---|---|---|
| Require final source identity with the last successful working export, or re-export a changed submission | 016's submission-only API regression | Current C versus C with final-source consistency, preserving the authoring allowance and final grader |
| Add an explicit public-settings check after smoke | Persistent settings mismatches and useful corrections | Current C versus C plus a checklist using only public task requirements, with the same budget |
| Use smoke conditionally after an observed export/runtime problem | Extra request/time cost and the bounded repair in 101 | Routinely guided versus conditional smoke; conditional use may miss initially hidden runtime defects |

A blanket freeze after clean smoke would suppress demonstrated corrections.
Repeating the existing execution-only disclaimer would not be a distinct
intervention. Untouched tasks and broader reference qualification are separate
future validation needs.

## Provenance and reproducibility limits

The source is **Request-16 retained-evidence mechanistic analysis**, report/evidence
commit `19aa097455e8270ae1e5cfaa58f1a6f33e4b111e`, with tooling commit
`251b99ce5339fdb6ca4027a226f72b433a066205`. It consumes the completed study at
`59f370f54c5edb3f6499af37259e3ae09d3e9ca7`, protocol
`factory-assessment-boundaries-v7`, authoring `authoring-requests-16-v1`.

The decomposition comes from the report's opening findings and **Every C
non-success**; setup patterns from **Failure-family decomposition**; repairs from
**Highest-value within-trajectory findings**; means from **Effort and revision
distributions**; hypotheses and interventions from the corresponding final tables.
These are transcriptions and bounded summaries, not new scientific calculations.

The original authoring of the inherited assignments and their separate v7
assessments are preserved, as are missing values. Raw trajectories, provider
content and private reference packages remain in the separate research archive.
The public summary does not enable independent reconstruction without that archive.

See [the development-study report](request16-development-study-v1.md) for the
amendment, incident and design limitations, or return to [RESULTS.md](../../RESULTS.md).
