# Experimental results

## Campaign 2 — October Request-16 campaign

**Complete on 2026-10-03: 150 terminal assignments, zero retries.**
The primary campaign is `campaign-150-rerun-01`. It contains two agent setups ×
three conditions × five reused tasks × five repeats, with 16 requests and 600
seconds per authoring session. These are development tasks, not an untouched
holdout. Luna uses medium reasoning and Sol low reasoning; their generic tools
and agent instructions differ, so this is not a comparison of model weights alone.

- **A — guided construction:** coding tools, required export and bounded repair.
- **B — A plus guided boundary observations.**
- **C — B plus bounded native smoke assistance.**

## Observed outcomes

| Setup | Condition | Diagnostic success | Evaluated failure | Unscored incident | Planned |
|---|---|---:|---:|---:|---:|
| Luna | A | 14 | 7 | 4 | 25 |
| Luna | B | 15 | 9 | 1 | 25 |
| Luna | C | 14 | 10 | 1 | 25 |
| Sol | A | 21 | 1 | 3 | 25 |
| Sol | B | 22 | 1 | 2 | 25 |
| Sol | C | 22 | 2 | 1 | 25 |

![Campaign 2 terminal outcomes per setup and condition](docs/assets/campaign-150-rerun-01-outcomes.svg)

Across all assignments, 108/150 (72%) produced diagnostic success. Among the 138
scored assignments, 108/138 (78.3%) succeeded. The second denominator excludes
incidents and has uneven task coverage; it cannot replace end-to-end reliability.
An incident has no scientific score and is not an evaluated model failure.

Sol has more observed successes in each condition. The counts do not establish
a benefit or harm caused by boundary or smoke tools. Access and guidance change
together, missing outcomes are uneven, and no significance analysis was performed.
The dashboard withholds comparison rates when observed identities are missing;
this static figure shows counts with all planned assignments retained.

| Task | Diagnostic success | Evaluated failure | Unscored incident | Planned |
|---|---:|---:|---:|---:|
| `reflective_pin_cell` | 24 | 4 | 2 | 30 |
| `reflected_7x7` | 24 | 4 | 2 | 30 |
| `two_composition_5x5` | 18 | 10 | 2 | 30 |
| `axially_zoned_5x5` | 22 | 5 | 3 | 30 |
| `asymmetric_5x5` | 20 | 7 | 3 | 30 |

## What assessment and traces explain

Final assessment used `factory-assessment-boundaries-v4-temperature-source-v1`:
frozen Python submission, independent factory export, final XML inspections,
separate native transport and retained-evidence review. No LLM judge assigns the
score. Scientific review is `pending_owner_review` and `grading_enabled=false`.
Passing this diagnostic protocol does not establish scientific qualification.

The 30 evaluated failures are partitioned once per assignment by precedence:

| Primary failure category | Assignments |
|---|---:|
| Invalid geometry at inspection | 11 |
| Factory export failure | 1 |
| Remaining geometry nonconformity | 7 |
| Remaining settings nonconformity | 11 |

Secondary defects may coexist. Eight assignments exhibit the shared mutable
OpenMC region alias pattern across both setups, all three conditions and two
tasks. Other defects include wrong fuel placement, water in required void gaps,
temperature lookup settings and generations per batch. One final submission
contains a construction error after a successful working export.

Smoke was used in 45 sessions. Of 43 sessions with at least one completed smoke,
33 ultimately succeeded and ten failed assessment. Completed smoke checks bounded
runtime behavior and does not certify specification conformity. These observations
do not establish causality, agent understanding or a full property-by-property
pre/post analysis of every trajectory.

The 12 incidents include nine initialization/runtime-preflight failures, one
unsupported source-point representation, one unattributed native exit and one
authoring-budget exhaustion. Budget exhaustion is an agent workflow failure;
these incidents must not all be attributed to infrastructure. Seven assignments
ended before any model request. The continuation consumed these attempts without
replacement and lacked a repeated-initialization-incident stop policy. The
underlying host slowdown was not established.

See the [closeout](docs/experiments/campaign-150-rerun-01.md) for assignment IDs,
continuation limits and evidence checks. Its [JSON](docs/experiments/campaign-150-rerun-01.json)
contains the full task/setup/condition counts and provenance digests. The public
summary excludes raw candidate code, conversations and private reference answers.

## Next experiments and limits

Targeted questions remain prospective:

- Does guidance or observation around mutable region aliases reduce overlaps?
- Does final-source consistency with the last successful export prevent regressions?
- Does checking public settings after smoke reduce persistent mismatches?
- Does a repeated-incident stop policy preserve campaign coverage without silently
  replacing consumed attempts?

Reference review, numerical calibration and untouched tasks remain necessary.
Finite geometry probes do not prove global overlap freedom; the fixed native seed
and uncalibrated ±150 pcm criterion limit interpretation. No new repair experiment
or native calculation was performed for this documentation update.

## Historical campaign 1

Campaign 2 replaces campaign 1 as the primary presentation in this file and the
README. The original [Request-16 development report](docs/experiments/request16-development-study-v1.md),
[mechanistic follow-up](docs/experiments/request16-mechanistic-analysis-v1.md),
data and figure remain archived for traceability. Their original v7 protocol and
results have not been rewritten or pooled with campaign 2. The older mechanistic
follow-up has a different review scope; additional workflow evidence in campaign 2
does not make it a controlled replication or stronger causal study.
