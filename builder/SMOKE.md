# Bounded candidate smoke diagnostics

P4 ports the bounded smoke implementation from experimental continuation
`1c2e805edf1303c0ebf0cfb84b2e226bf1917976`. It adds the explicit
`guided_boundaries_smoke` condition (C), identified as
`generic_coding_guided_boundaries_smoke_v1`. A and B keep their existing prompts,
tools and limits. All three conditions use the same final evaluator.

## Operator preparation and execution

Preparation needs an explicit, locally supplied nuclear-data index. It validates
the index and binds its hash, the adapter identity and the authoring prompt; it
does not dispatch a model or start native transport.

```sh
python3 -B -m experiments.run prepare \
  --assistance guided_boundaries_smoke \
  --smoke-data-index "$DATA_INDEX" \
  --output scratch/condition-C
```

Use a new output directory. The existing separate command
`python3 -B -m experiments.run execute --output scratch/condition-C`
starts live authoring and may run native smoke. It requires reviewed pinned
images, data, authentication and explicit execution authorization. Those
dependencies are not included in this public repository. A changed prepared
data-index hash, adapter identity or prompt blocks dispatch. A/B reject a smoke
data index; C requires one. The lower-level builder also accepts
`--smoke-data-index` only with the declared C condition.

The default remains **8 requests and 600 authoring seconds per task**.
P5 adds the explicit [Request-16 authoring profile](AUTHORING_PROFILES.md);
it changes only the request cap and corresponding guidance, keeping the same
600 seconds and smoke allowances. Smoke consumes this authoring time and its
separate call allowance. Mock inference replaces only the provider;
it does not disable native smoke. Portable tests explicitly substitute local
process doubles as well.

## Candidate command and diagnostic copy

C adds `python3 /work/smoke_openmc.py model.xml` to the guided construction
and boundary workflow. The candidate-local reader accepts a regular, single-link
XML file inside the workspace, up to 500,000 bytes. Only XML bytes cross the
existing socket/stdio bridge. The builder has no native solver, nuclear data,
private reference mount or host Docker socket.

`evaluator.smoke.prepare_xml()` creates a separate diagnostic XML copy:

| Field | Diagnostic value |
|---|---|
| Particles | 1,000 |
| Batches / inactive | 8 / 2 |
| Generations per batch | 1 |
| Seed / native threads | 1 / 1 |
| Statepoint | Final batch 8 |
| Separate source output | Disabled |
| Cross-section index | Explicit operator-selected index inside the isolated data mount |

Original bytes, original/diagnostic hashes and all eight overrides are retained.
Geometry, material definitions, boundary properties, source distributions and
temperature settings are preserved. Unsupported physical inputs are rejected,
not repaired. Do not copy reduced sampling into the final submission.

At most **two attempts** are available. A third request receives a recorded
budget refusal and a fourth is rejected. Refused attempts still count as calls;
`native_attempts` separately counts recorded native-process attempts.
Admission requires at least **180 seconds** remaining. Each native solver
process has **60 seconds**; setup, data hashing, staging, extraction and cleanup
have additional costs. The reserve is not a guaranteed end-to-end deadline.
There are no automatic repairs or retries.

## Receipts and feedback

`evaluator.transport.smoke_xml()` reuses the existing isolated transport
controller and worker. Its input kind is `candidate-session-smoke-v1` and
its transport receipt is `candidate-smoke-transport-v1`, distinct from
final `isolated-xml-transport-v1`. It has no candidate-source hash or
independent-final-export claim. Normal final transport still requires an accepted
factory export; smoke receipts cannot substitute for that export.

The controller retains process exits, interruptions, runtime/data identities,
bounded logs, artifact bindings and cleanup. Uncertain smoke cleanup stops the
builder and prevents the experiment launcher from starting another task.
Native exit zero alone is insufficient for completed smoke: statepoint
validation, data checks and cleanup must also succeed.

The tool uses `candidate-smoke-tool-v1`, result
`candidate-smoke-result-v1` and compact feedback
`candidate-smoke-feedback-v1`. Feedback reports runtime diagnostics, not
task conformity or a score. A successful short run may miss defects; a failed
run alone does not establish model-versus-infrastructure attribution.

Each public full-report log excerpt keeps at most 80,000 bytes of head/tail
content plus an omission marker. Original byte lengths, hashes and completeness
flags remain visible. The default compact JSON is bounded to 16,000 bytes;
oversized metadata produces explicit incomplete feedback. A content-addressed
workspace report supports detail reads without another smoke call. Full host
logs and raw receipts remain operator evidence, not public-repository artifacts.

Call completion and feedback availability do not prove that a later model
request received or interpreted the feedback. The separate
[P6 trajectory projection](TRAJECTORY.md) now reconstructs exact compact-feedback
delivery from retained calls and subsequent request inputs, including delayed
output. It reports missing or ambiguous delivery explicitly and never infers
interpretation. Final assessment independently rebuilds the frozen submission under the unchanged
`factory-assessment-boundaries-v4-temperature-source-v1` route. Historical
results and grading are unchanged; full experimental v7 parity is not claimed.

## Portable verification

```sh
python3 -B -m unittest discover -s tests -p 'test_smoke*.py' -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

[Contract controls](../tests/test_smoke.py) and
[lifecycle/routing controls](../tests/test_smoke_lifecycle.py) use synthetic public
XML, local process doubles and fake statepoint bytes. They exercise override
preservation, receipt separation, resource limits, containment, cleanup, data
changes, log bounds and explicit routing. They run no LLM, factory or native
OpenMC process and do not establish native runtime qualification or efficacy.
