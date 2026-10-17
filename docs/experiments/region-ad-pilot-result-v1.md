# A/D development pilot: results and evidence limits

The frozen 36-assignment pilot completed on 2026-10-17, from 14:07 to 17:25 UTC. All assigned trials were consumed once: 30 complete protocol successes, six evaluated model failures, zero unscored incidents and zero pending assignments. No failure was replaced.

A is guided construction. D adds the entire fixed region-ownership procedure to the initial prompt. Luna retains medium reasoning and Sol low reasoning; A/D share the same tools, settings and budgets within each model configuration. This is a comparison of the complete D intervention, not a ranking of the models.

## Primary outcome

Complete success requires a coherent independently reconstructed final assessment with strict_correct true. A high partial score, successful execution, skill mention or numerical agreement alone is insufficient.

| Configuration | A successes | D successes | Descriptive D minus A |
|---|---:|---:|---:|
| gpt-5.6-luna | 6/9 | 7/9 | +11.1 percentage points |
| gpt-5.6-sol | 8/9 | 9/9 | +11.1 percentage points |

| Model | Task | Arm | Successes / 3 | Evaluated failures | Incidents |
|---|---|---|---:|---:|---:|
| gpt-5.6-luna | two_composition_5x5 | A | 1/3 | 2 | 0 |
| gpt-5.6-luna | two_composition_5x5 | D | 2/3 | 1 | 0 |
| gpt-5.6-luna | axially_zoned_5x5 | A | 2/3 | 1 | 0 |
| gpt-5.6-luna | axially_zoned_5x5 | D | 3/3 | 0 | 0 |
| gpt-5.6-luna | reflective_pin_cell | A | 3/3 | 0 | 0 |
| gpt-5.6-luna | reflective_pin_cell | D | 2/3 | 1 | 0 |
| gpt-5.6-sol | two_composition_5x5 | A | 3/3 | 0 | 0 |
| gpt-5.6-sol | two_composition_5x5 | D | 3/3 | 0 | 0 |
| gpt-5.6-sol | axially_zoned_5x5 | A | 2/3 | 1 | 0 |
| gpt-5.6-sol | axially_zoned_5x5 | D | 3/3 | 0 | 0 |
| gpt-5.6-sol | reflective_pin_cell | A | 3/3 | 0 | 0 |
| gpt-5.6-sol | reflective_pin_cell | D | 3/3 | 0 | 0 |

The task pattern is mixed: Luna improves on the two assembly tasks but declines from 3/3 to 2/3 on the reflective cell. The equal-task-weight gain is descriptive and small; it does not demonstrate general efficacy.

## Failure mechanisms and the secondary review

Five submissions failed the finite geometry checks before native transport: 005, 006, 010, 016 and 027. Submission 025 completed transport and passed the declared k-effective comparison, but retained the default 10 K temperature tolerance instead of the requested 1 K. Its score is 96.4286 and its complete-success outcome is false. This discrepancy does not itself demonstrate a difference in realized neutron physics.

Codex's source-review draft flags the targeted alias / in-place mutation / late-complement sequence in 005, 010 and 027, all in A. It instead attributes 006 and 016 to complementing cladding annuli rather than full pin envelopes. These are explanatory proposals: all 36 canonical secondary labels remain pending human review. Do not treat the proposals as a confirmed reduction of the targeted defect.

The evaluator detects geometric consequences; source review supplies the proposed Python root cause. The local anonymous review packet contains unchanged final sources, public task specifications and the frozen measurement definition. It omits model/arm labels, scores, Codex proposals, provider traces and private reference answers. The operator mapping remains outside the packet. Source style can still suggest condition, so metadata masking does not guarantee blinding.

See the [mechanism notes](region-ad-mechanism-notes-v1.md) for safe in-place examples and isolated OpenMC semantic controls.

## Delivery, dependencies and resources

All 36 assessments reconstructed as coherent. All 36 actual-exposure audits passed, including exact initial A/D context, matched request setups, complete upstream responses and final-source binding. All trials matched the originally qualified reference/data/image identities; the 31 that reached native transport matched the qualified native runtime.

The pilot used 147 received requests, with 147 provider HTTP responses and 147 complete responses, against a 576-request ceiling. The four separate real-provider qualification requests are excluded. Reported pilot token usage totals 1,662,299, complete for all 36 records; no monetary cost is inferred.

| Model | Arm | Requests | Reported total tokens | Median authoring seconds | Total assessment minutes |
|---|---|---:|---:|---:|---:|
| gpt-5.6-luna | A | 41 | 432086 | 44.3 | 32.8 |
| gpt-5.6-luna | D | 45 | 513115 | 45.5 | 42.8 |
| gpt-5.6-sol | A | 31 | 357060 | 52.9 | 41.9 |
| gpt-5.6-sol | D | 30 | 360038 | 49.8 | 50.8 |

Assessment totals combine early rejections and full native calculations. They account for workload; they are not a speed benchmark. The implementation passed 435 portable tests, four scripted real-CLI controls and four real-provider transmission controls. Neither scripted controls nor transmission receipts count as scientific task successes.

## What this pilot supports

The A/D execution and evidence chain is technically feasible in the qualified environment. The observed primary rates favor D in both configurations, while a task-level regression and failures outside the targeted mechanism remain. A defensible current claim is an exploratory development result for provided procedural guidance.

Human mechanism adjudication and scientific reference/threshold review remain pending. The experiment reused three development tasks with three repetitions per cell; it does not establish equivalence, broad generalization or nuclear-safety qualification. D supplies extra instructions/context as well as domain content; there is no length-matched placebo. Spontaneous catalog discovery and agent-selected loading in E remain untested.

Before confirmation, use the [separate confirmation proposal](region-ad-confirmation-plan-v1.md) to decide the target claim, new independently reviewed task families, sample size, blinding and budget, then freeze a new manifest before calls. No held-out tasks or confirmation campaign were created or run here.

## Artifacts

- [Public aggregate JSON](region-ad-pilot-results-v1.json): counts, configurations, resources and evidence hashes.
- [Frozen protocol and commands](region-ad-pilot-v1.md).
- Local evidence: scratch/region-ad-pilot-36-v2, including analysis-terminal.json, resource-ledger.json, exposure-audit.json and frozen-dependency-binding.json.
- Local human-review packet: anonymous-source-review/README.md; its operator key is outside that directory.

Raw requests, private references and transcripts remain local. Protocol SHA-256: 9973ba09cc920007d8287fda8a3442c5a1b76b7bbd5d5115c26b0bb22d1b7ab9.
