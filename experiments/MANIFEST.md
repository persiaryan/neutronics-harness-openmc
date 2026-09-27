# Prospective study manifests

P7 extracts preparation invariants from the experimental planner at
`1c2e805edf1303c0ebf0cfb84b2e226bf1917976`, without its fixed models,
150-session schedule, historical amendments or incident exceptions.

`experiments.manifest` prepares and verifies a small frozen package.
It cannot dispatch, assess, resume or reconcile a trial. Successful verification
is neither execution authorization nor runtime/scientific qualification.

## Explicit study specification

A JSON specification declares the study ID, selected public tasks, excluded task
reason IDs, setups, arms, repetitions, resource IDs, analysis choices and every
assignment in the desired order. There is no scheduling seed or implicit shuffle.
The assignment list must contain exactly one entry per task/setup/arm/repetition
combination; duplicate, missing and unknown assignments are rejected.

This two-slot example is a template, not a qualified campaign:

```json
{
  "study_id": "prospective-example",
  "tasks": ["reflective_pin_cell"],
  "excluded_tasks": {
    "reflected_7x7": "outside-selection",
    "moderated_cylinder": "outside-selection",
    "two_composition_5x5": "outside-selection",
    "axially_zoned_5x5": "outside-selection",
    "asymmetric_5x5": "outside-selection"
  },
  "setups": [{
    "id": "setup-one",
    "model": "operator-selected-model",
    "request_setup_id": "client-one",
    "request_budget": null
  }],
  "arms": [
    {"id": "baseline", "assistance": "guided_construction"},
    {"id": "boundary", "assistance": "guided_boundaries"}
  ],
  "repetitions": 1,
  "data_id": "data-one",
  "reference_ids": {"reflective_pin_cell": "reference-pin"},
  "assignments": [
    {"case": "reflective_pin_cell", "setup": "setup-one", "arm": "baseline", "repeat": 1},
    {"case": "reflective_pin_cell", "setup": "setup-one", "arm": "boundary", "repeat": 1}
  ],
  "analysis": {
    "primary_contrast": ["boundary", "baseline"],
    "secondary_contrasts": [],
    "trajectory_examples": "none"
  }
}
```

Set the actual reviewed model identity explicitly. Each setup uses one
request-configuration descriptor and one request budget across all arms:
`null` selects the existing eight-request profile;
`"authoring-requests-16-v1"` explicitly selects sixteen. The 600-second
authoring allowance, tool limits and zero retries are unchanged. Different
setups may declare different profiles; comparisons remain separate by setup.

Arm labels are operator identifiers, mapped to the existing named assistance
conditions. Labels do not create new tools or guidance. C's existing smoke
condition remains `guided_boundaries_smoke`. Metadata limits are 10,000
assignments and 4 MB per JSON file; these are preparation limits, not new
scientific or authoring budgets.

## Private local bindings

A separate, uncommitted JSON file resolves public resource IDs:

```json
{
  "data": {"data-one": "external-data/cross_sections.xml"},
  "references": {"reference-pin": "private-references/pin"},
  "request_setups": {"client-one": "private-setups/client-one.json"}
}
```

Keep this bindings file outside the public checkout. Paths resolve relative to
that file; the data collection must also be outside the checkout under the
existing admission contract. Paths are not copied into the manifest. Copying identical resources to another location preserves their
identity. Missing or extra bindings are rejected.

- Data: use the existing flat external data-directory admission contract.
  Preparation hashes the index and every listed library's complete bytes. This
  can take time for large collections. The manifest retains the index hash,
  aggregate inventory hash, file count and byte count, not library contents.
  Hashing/admission does not qualify HDF5 contents, table compatibility or OpenMC.
- References: use an existing sealed reference package for each declared task.
  The existing `references.verify_package` checks its seal and full inventory;
  the manifest retains the package-manifest hash and file count. No reference
  values or scientific-review text are published. Sealed bytes do not establish
  scientific approval or activate grading.
- Request setups: supply the reviewed descriptor from
  `builder.context.request_setup`, not a raw request or credentials. Only its
  file hash and size enter the manifest. Instruction content stays local.
  This binds a declared setup, not proof that a future live client will match it.

Resources remain evaluator/operator inputs. This preparation does not mount
them into a builder or create an authoring session. Keep bindings and private
resources out of the public repository.

## Prepare and verify

```sh
python3 -B -m experiments.manifest prepare \
  --spec scratch/study-spec.json \
  --bindings "$LOCAL_BINDINGS" \
  --output scratch/prospective-study/manifest

python3 -B -m experiments.manifest verify \
  --bindings "$LOCAL_BINDINGS" \
  --output scratch/prospective-study/manifest \
  --expected-sha256 "<hash-returned-by-prepare>"
```

`LOCAL_BINDINGS` names the private resolver JSON above; it is not an
authentication file. Use a new output directory. Preparation creates only `spec.json`,
`assignments.json`, `analysis.json`, `manifest.json` and `seal.sha256`.
It does not create trial directories or candidates. Keep future execution
artifacts outside this frozen bundle; its exact file inventory is checked.

Verification reconstructs the declarations from the specification and current
local dependencies. It checks assignment order, condition prompt hashes,
per-setup/arm budgets, aggregate ceilings, tool and runtime declarations,
rubric/protocol identity, source inventory, resources and analysis definitions.
The scientific route remains
`factory-assessment-boundaries-v4-temperature-source-v1`.

The source closure covers Python, JSON, Markdown and Dockerfile inputs under
`builder/`, `evaluator/`, `evaluation/`, `experiments/` and
`prompts/`, excluding private frozen packages and bytecode caches. Public
task requirements, sampling and scientific rules remain in those bound sources;
the manifest does not override them. Resource/runtime availability, authentication,
native qualification and execution authorization remain separate future gates.

The returned SHA-256 is a binding to retain independently. A seal stored beside a
manifest detects inconsistent changes, but cannot stop an operator replacing
the whole bundle and its seal. `--expected-sha256` checks an independently
retained binding. Optional `--require-committed` also requires all five
preparation files and every implementation file to match current Git HEAD.
The implementation checkpoint must be an ancestor of HEAD, allowing a later
commit to add the preparation. These checks never commit or push files.
Review public metadata before any publication; IDs and model names are operator
supplied, and hashes are not encryption or an authenticity guarantee.

## Frozen analysis declarations and limits

`descriptive-balanced-policy-v1` freezes equal task weights, separate setup
reporting, all-started success denominators, available-score denominators,
preserved null scores, per-cell descriptive 95% Wilson intervals, unresolved
identification bounds, overlapping family counts and separate numerical,
physical and incident outcomes. Balanced contrasts are withheld for incomplete
inventory. This module declares that policy; it computes no outcomes or statistics.

A contrast `[left, right]` means left minus right. The operator explicitly
chooses the primary and secondary contrasts. Optional trajectory examples use
`first_verified_success_and_non_success_per_setup_arm`; otherwise choose
`none`. No historical pooling or causal interpretation is enabled. New
scientific acceptance criteria or intervention designs require a separate task.

## Portable validation

```sh
python3 -B -m unittest tests.test_study_manifest -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

Controls use literal small schedules, synthetic data bytes and sealed synthetic
references, plus local Git fixtures. They test changed/missing/reordered bindings,
commit checks, links, strict JSON, read-only verification and dispatch tripwires.
Synthetic data and references are deliberately not scientific qualification.
No live model, factory or native transport run is required. P8's serial executor
and P9's analyzer are outside P7; full experimental v7 parity is not established.
