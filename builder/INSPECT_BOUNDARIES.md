# Candidate-only boundary inspection adapter

Use `--assistance boundaries` for optional inspection, or `--assistance
guided_boundaries` for the [guided authoring policy](guided_authoring.md).
`generic` and `guided_construction` have coding tools without this adapter. Conditions share the
authoring image, factory task, evaluator and wall/request budgets. Guided use
requires export attempts and inspection by instruction, not runtime enforcement;
optional use remains optional. New boundary-enabled prompts are explicitly
versioned for compact feedback; historical prompt bytes are not rewritten.
No tool-use score or reward applies.

## Critical path

1. The launcher verifies the existing pinned authoring container and its OpenMC
   Python environment, then attaches `boundary_tool.AttachedSession` to its exact
   container ID. The existing image, entrypoint and baseline runtime are unchanged.
2. The builder can run `python3 /work/inspect_boundaries.py model.xml` from its
   workspace. `boundary_client.read_candidate` opens a bounded regular file below
   `/work/workspace`, without symlinks, hardlinks, FIFO/device input or `..` traversal.
3. A Unix socket inside that container forwards XML bytes over a separate Docker
   stdio pipe. Neither a host path nor another session's artifact handle is an
   accepted host request. The bridge cannot invoke a host command or choose a URL.
4. The controller snapshots those bytes, applies existing XML admission, invokes
   a **fresh mount-free XML-only inspector**, and verifies its retained receipts.
   Candidate Python, task requirements and references do not enter that inspector.
5. The adapter retains the full reply and its deterministic `feedback.json`
   projection. The client saves the full reply once in the candidate workspace
   and prints the compact projection. Neither contains expected values, scoring,
   repair, host exception text or private execution receipts. Inspection completion
   and subsequent model-request delivery are separate recorded facts.
6. Final private assessment still executes the submitted factory again, retrieves
   its exports and re-runs the protocol's inspections and transport. It does not
   accept builder-tool claims as grading evidence.

The builder and its client code are untrusted. Session ownership means bytes
received over the pipe attached to that verified container; it does not prove
that a claimed Python factory generated them. Candidate-created fake tool text
cannot supply private evaluator evidence. Only the final frozen submission enters
the normal independent assessment path.

## Scope and output semantics

The shared primitive is `effective-boundary-observation-v2`. Its corrected
`uniform-root-box-boundaries-v2` scope accompanies every reply: root union must be
established as one box, and supported effective behavior is uniform across each
face's possible contributors. Those contributors are a conservative superset,
not individually certified contacts. Mixed patches, curved exteriors, periodic
coupling and unresolved face hierarchy remain limited. No global geometry,
overlap, material, convergence or task-compliance verdict is produced.

An unsupported sphere returns `status=observed` with
`observations.domain.status=indeterminate` and its specific cause. Invalid input,
unavailable evidence, timeout/cleanup uncertainty or exhausted allowance instead
produce an indeterminate operation reply. A missing observation never means pass.
All causes and candidate bytes remain in operator-side evidence. Unexpected
exceptions are sanitized in the public reply. The operator verifier qualifies
successful observations, the explicit over-budget refusal, and one narrowly
supported loading failure: a cell references a material ID absent from the
retained XML and the completed worker reports the matching string-key
`KeyError`. Other retained failure causes remain insufficient.

`boundaries.execution_record()` verifies the pinned worker, artifact/input hashes,
containment, normal external completion and confirmed cleanup before interpreting
any output. `record()` still accepts only a valid boundary observation.
`missing_material_failure()` separately reconstructs the missing IDs from the
same XML; an exception alone is not sufficient. Changed IDs/errors, missing or
inconsistent receipts, interruption and uncertain cleanup cannot qualify.

For a qualified failure, the unchanged builder reply remains
`status=indeterminate`, `cause=inspection_evidence_incomplete`, `observations=null`.
No raw error, operator classification, task verdict or score is added to feedback.
The operator verification result records `failed_inspections` with
`observation_status=unavailable` and `scientific_credit=none`; `inspections`
counts usable observations, while `started_inspections` includes qualified failed
calls. Failed attempts still consume the existing allowance and never trigger an
automatic retry. This is additional read-only receipt verification, not a new
observation, grading rule, feedback format or assessment protocol. Original
receipts, replies and historical grades are not rewritten.

Surface and cell IDs are traceability references only. The adapter does not compare
them to a private model. It reports effective loaded values and XML provenance;
it cannot recover Python arguments erased by export normalization.

## Resource policy

The `candidate-boundary-tool-v2` profile preserves the existing budgets: two inspection attempts per
session, XML up to 500,000 bytes, and a 120-second worker deadline per call. The
fresh inspector keeps the existing two-CPU, 1-GiB, 128-PID, read-only-root and
network-none restrictions. Client staging has 30 seconds; bridge readiness has
10 seconds. Existing individual Docker setup/cleanup calls retain their 30-second
limits. Replies are capped at 1,800,000 bytes. A third request gets one recorded
budget refusal; a fourth stops the session, bounding retained request growth.

The existing session deadline continues to govern request admission and model
traffic. No inspection starts with fewer than 180 seconds remaining. This is an
admission reserve, not a guarantee that all setup and cleanup finish within that
reserve: the independent stage deadlines still apply, and cleanup can extend
elapsed time. No budgets are increased for a particular artifact or failed call.
Zero invocations are explicitly recorded, rather than inferred from missing logs.

## Model-facing feedback contract

`candidate-boundary-feedback-v1` is deterministic ASCII JSON, at most 16,000 bytes
including its newline. This leaves headroom under the actual outer `functions.exec`
default of 10,000 approximate tokens (the Axial incident preserved 40,000 characters).
Nested command output budgets do not override that outer budget. No Codex history
setting is changed. Arbitrarily smaller builder-chosen budgets or extra output can
still truncate a result; the instruction is not a runtime delivery guarantee.

The complete projection includes inspection status/cause, artifact hash, observer
and OpenMC versions, the domain record, every available face record with the
effective properties of its referenced surfaces, coverage, all scope/observation/
surface limitations, unresolved observation obligations, counts, and `full_result`.
It does not infer uniformity or task compliance from those properties. Differing
albedos stay visible alongside unresolved hierarchy. Missing faces/properties do
not become passing observations. IDs remain traceability aids.

`full_result` gives a workspace-relative filename, SHA-256, byte length and opaque
evidence reference. The full JSON contains all surface records, names, geometry,
XML provenance and raw public evidence. It is written exclusively, without following
links or overwriting a different existing file. Repeating the same save verifies
the existing bytes. Candidate files remain untrusted; operator receipts retain
the original result and independent final evaluation never consumes these files.

Use ordinary Python in the sandbox to read details without another inspection:

```python
import hashlib, json
from pathlib import Path
# Use the exact full_result.path and sha256 returned in the compact reply.
raw = Path("boundary-report-<sha256>.json").read_bytes()
assert hashlib.sha256(raw).hexdigest() == "<sha256>"
report = json.loads(raw)
print(json.dumps(report["observations"]["surfaces"][0:3]))
```

`feedback_complete=true` means the defined presentation is complete, even when
the scientific observation is unresolved. If that projection exceeds 16,000 bytes,
the response explicitly returns `feedback_complete=false`, `feedback_byte_limit`,
required bytes and omitted sections, keeping identity, domain status/cause and the
full-result reference. Limitations/obligations then require a saved-file read; they
are never silently dropped from a supposedly complete reply. Full reports are
subject to the existing 1,800,000-byte bridge bound.

The trajectory summary compares actual request content with retained expected
feedback, not merely parseability or an artifact ID. It reports compact-feedback
delivery separately from delivery of the full raw reply. Filtering, truncation or
no later request cannot establish complete feedback. Partial detail reads are not
automatically combined into an inferred complete delivery.

## Validation and pilot

Run the portable unit suite documented in the root README. Native qualification
records and their private fixtures are not distributed in the public snapshot.
See the README for preparation commands and runtime prerequisites. The default tasks are
pin and unsupported cylinder: eight requests, 600 authoring seconds, at most
two inspections each, no retries and no transport. Preparation does not dispatch.

The optional-use diagnosis and full model-context delivery controls remain in the
private research records. The separately versioned guided condition is implemented;
its instruction is linked above. It is not silently applied to optional sessions.
The portable suite alone does not certify live delivery.
