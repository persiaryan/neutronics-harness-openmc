# Neutronics Harness

A research prototype for evaluating LLM-assisted OpenMC model construction.
An agent turns a public physical specification into Python, can inspect its working
model, and submits `build_model() -> openmc.Model` for independent assessment.

The research question is whether scientific inspection helps an LLM produce more
faithful neutronics models, and eventually whether it narrows differences between
models. **The current project does not establish either effect.**

## What is implemented

```text
public task -> isolated builder -> working export / optional scientific feedback
            -> frozen Python submission
            -> one independent factory export -> admitted model.xml
            -> fresh XML-only inspection -> separate native OpenMC transport
            -> code-based assessment and evidence verification
```

- A provider-neutral scientific core with a working Codex subscription adapter.
- Matched conditions: guided construction with generic coding tools, or the same
  setup plus guided boundary inspection. Neither is tool-free.
- Effective boundary observations, including albedo and domain participation,
  with explicit support limits and indeterminate results.
- Contained candidate execution, bounded artifact retrieval and evidence verification.
- Independent physical and numerical checks. Tool invocation earns no points;
  builder-reported observations never determine the final score.

See [the architecture walkthrough](DESIGN.md), [boundary support](evaluation/scientific/BOUNDARIES.md),
[the builder tool](builder/INSPECT_BOUNDARIES.md), and [scoring](evaluation/benchmark_suite/SCORING.md).

## Try the public source without model calls

Run from the extracted repository with Python 3.12 or newer. Host code uses the
standard library; these commands need no OpenMC installation, Docker, nuclear
data, credentials or model calls.

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B -m prompts.prepare --case reflective_pin_cell --output scratch/public-prompt
python3 -B -m experiments.run prepare --assistance guided_construction --output scratch/condition-A
python3 -B -m experiments.run prepare --assistance guided_boundaries --output scratch/condition-B
```

Use a new output directory on each preparation. The last two commands only write
task/prompt bundles and budgeted plans. They do not execute an agent or transport.
The public tests are a portable subset using synthetic inputs and local doubles;
they do not replace native integration or scientific qualification.

## Native execution prerequisites

The operational environment is pinned to OpenMC 0.15.3 and Linux ARM64 containers.
Live authoring also needs the pinned Codex image and subscription authentication.
Credentials stay in the host relay. The adapter is version-specific; compatibility
with arbitrary CLI versions or providers has not been established.

**This source release is not a self-contained native benchmark distribution.**
Reviewed dependency images, nuclear data and sealed reference packages are not
distributed here. Existing build commands wrap pinned local source images; they
are not clean-machine dependency acquisition recipes. See [execution profiles](evaluator/profiles.py),
[factory execution](evaluator/MODEL_FACTORY.md) and [transport](evaluator/TRANSPORT.md).

With those dependencies supplied privately, the existing entry points are:

```sh
# Live model calls: explicitly budget and authorize before running.
python3 -B -m experiments.run execute --output scratch/condition-A
# Native assessment: requires the private reference packages and data.
python3 -B -m experiments.run assess --output scratch/condition-A --data-index "$DATA_INDEX"
```

Both conditions use the same evaluator. The default two-task usability plan has
8 requests and 600 authoring seconds per task; B permits at most two 120-second
inspections inside that allowance. It includes a curved-cylinder task to exercise
interpretation of unsupported observations, not to claim boundary conformity.
The plan records phase budgets and the zero-retry policy.

## Scope and research status

The observer supports specified root-box boundary representations; it is not a
general CSG proof system. Finite probes do not establish global overlap freedom.
Unsupported coverage remains unresolved even when numerical agreement is good.
The diagnostic score uses hard gates and 70 applicable points normalized to 100;
execution evidence is mandatory but earns no scientific points.

Reference review, Monte Carlo scoring calibration and untouched repeated multi-model
comparisons remain open work. The current ±150 pcm equivalence margin is a frozen
internal design choice with unresolved calibration. No formal harness-improvement
result is claimed here.

Private benchmark answers, reference implementations, model conversations, study
results and nuclear data are excluded from this public source snapshot. Complete
research records remain in a separate private repository. Publishing the harness
does not give a candidate session access to that repository.

## License

MIT; see [LICENSE](LICENSE). OpenMC, Codex, container dependencies and nuclear data
retain their own licenses and are not included in this source snapshot.
