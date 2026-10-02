# Evolving the operator dashboard

The dashboard is an evidence reader. The evaluator still owns scientific checks,
scores and independent review. These contracts concern operator metadata and
presentation; they do not grant tools to an agent or implement a new evaluator.

## Execution path

1. `experiments.run.prepare()` obtains the current description from
   `observation_catalog.json` through `observation_contracts.describe_configuration()`.
   It saves `observation_configuration` inside `plan.json`. Execution rejects a
   mismatch with the plan's assistance/condition. Existing runtime policies still
   decide which tools execute.
2. Boundary and smoke sessions call `observability.tool_observation()` after
   retaining their original results. The additional `observation.json` contains
   tool/version/call identities, host timestamps, duration and SHA-256 hashes of
   available request/response/feedback files. Writing this receipt is best effort.
   It is not delivered to the builder and does not alter its feedback.
3. `evaluation.candidates.run.evaluate()` embeds an `observation_definition`
   in the v5 report: required gates/checks, domain descriptions, weights, score
   scale, global numerical rules and rubric/protocol identities.
4. `evaluation.candidates.verify.assessment_report()` checks this definition
   against the evaluator's rules. `review_assessment()` records `report_sha256`.
   This is the digest of canonical JSON, not the digest of the file's whitespace.
5. `dashboard.contracts.normalize_evaluation()` reads a supported report into a
   display view. `projection.snapshot()` retains both the original report and
   this view. `campaign.read_records()` uses the same reader; the browser does
   not maintain a second scoring/schema implementation.

## Configuration and tool descriptions

The single current catalogue is `observation_catalog.json`. A configuration has
an ID, version, localized label/description, exact assistance/condition and an
ordered tool inventory. Each tool has an ID, version, localized label, optional
evidence directory and budget key. Descriptions are copied into new plans and
canonically hashed. Changing a current description does not rewrite past plans.

For a new tool, implement its runtime policy separately, add its description,
and write request/response/feedback plus a `tool-observation-v1` receipt using
the host helper. The dashboard discovers the declared directory and displays
the generic feedback and receipt. It validates identities and referenced hashes.
Paths are confined to the selected run; arbitrary absolute paths are not allowed.

The receipt's completion timestamp does **not** establish feedback delivery.
Existing boundary/smoke delivery is still established by the trajectory reader.
A new tool needs its own explicit delivery integration before that claim can be
shown. Later edits are temporal observations, not evidence of causal learning.

Configuration labels are not globally unique identities. If two recorded
descriptions use the same ID with different versions or tool definitions, the
campaign gives them separate columns. Any non-shared budget change within a
configuration suppresses comparison, including newly added tool budget keys.

## Reports and reader states

Supported inputs:

- `private-candidate-diagnostic-v5`: current reports with an embedded definition,
  or historical reports matching the frozen legacy rubric identity.
- `evaluation-report-v1`: a future presentation contract exercised by synthetic
  tests. It requires an embedded `evaluation-definition-v1`, a `score` object
  (`value`, `strict_correct`, `status`) and a `criteria` list. Each criterion has
  `domain`, `id`, `verdict` (`pass`, `fail`, `unknown`) and optional `expected`,
  `observed`, `unit`, `rule`, `reason`, `cause`, `evidence`. Its independently
  produced review must bind to the report digest. No production evaluator was
  switched to this format in this consolidation.

Definitions declare all required criteria, a positive score maximum/applicable
points, numerical rules, labels, rubric identity and protocol. The supported
domain aggregation is `all-required-checks-v1`: every required check must pass;
an observed failure fails the domain; otherwise the domain is unknown. A missing
criterion is never inferred to pass. An infrastructure-caused failed gate remains
unknown for scientific success. Scores are displayed, never recalculated.

Reader status is distinct from a scientific verdict:

The separate `operational` view preserves execution status for known report
formats even when the rubric is unavailable. An interrupted historical evaluation
displays its recorded stage/error and original report, rather than a pending-score
message. This does not make its scientific results supported or trusted. Unknown
report formats keep an unavailable operational state; their semantics are not guessed.

| Reader status | Meaning |
| --- | --- |
| `missing` | No readable report is available yet; read warnings remain separate. |
| `supported` | The report matches a known presentation contract. |
| `unsupported` | Its format or historical rubric has no registered reader/definition. |
| `invalid` | A recognized contract is malformed or internally inconsistent. |

`trusted` additionally requires a coherent retained review, matching score and
strict flag, and a report digest for new reports. Unsupported/invalid/unbound
results cannot supply scientific passes in aggregates. Original artifacts remain
accessible, with a visible reader diagnostic. Hashes bind content; they do not
authenticate an operator who can rewrite all evidence or prove physics correct.

## History and comparisons

`dashboard/legacy/evaluation-v5.json` and `configurations-v1.json` are frozen
migration definitions. Do not update them when changing the current rubric or
catalogue. Add a deliberate reader/migration for another historical format.
Legacy reviews lack the new report digest; their weaker binding remains a
documented compatibility limit. A historical admission failure without a rubric
identity cannot acquire one by inference from the current code.

Unassigned legacy observations are grouped by recorded compatibility identities,
including the complete evaluation-definition digest, model, protocol, runtime,
budgets and reference scope. Explicit campaigns instead keep one stable group per
model and validate those identities within that group. Conflicting scales,
criteria, weights or thresholds suppress its rates instead of splitting its
planned denominator into apparently comparable subsets. Pending runs retain their
declared scope separately from the observed scope; missing observed identities
also suppress comparison. Conflicting imported study identities suppress rates
across the unassigned selection. The matrix and pairwise comparisons derive columns and domains from the
retained descriptions. Task weighting, missing-outcome bounds and coverage rules
remain unchanged. These descriptive comparisons do not establish causality.

Adding a criterion within these contracts needs metadata and a verifier result,
not a browser column change. New verdict semantics, aggregation rules, report
formats or specialized interactive visualizations still require explicit code
and tests. This is an intentional validation boundary.

## Portable evolution checks

```sh
python3 -B -m unittest tests.test_dashboard_contracts -v
python3 -B -m tests.test_dashboard_contracts --fixtures scratch/dashboard-contract-fixtures
node tests/test_dashboard_evolution_templates.cjs scratch/dashboard-contract-fixtures/future-state.json scratch/dashboard-contract-fixtures/future-campaign.json
node tests/test_dashboard_interrupted_templates.cjs scratch/dashboard-contract-fixtures/interrupted-state.json
```

Fixtures include D, a thermal probe, a new domain/criterion, a score on 10 and a
75 pcm margin. These commands never dispatch a model or native solver. Template
checks do not replace visual review in a rendered browser.
