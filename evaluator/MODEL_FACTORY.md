# Model-factory contract

Only `openmc-model-factory-v1` is active, with export format
`isolated-export-evaluation-v2`. Historical execution requires the checkpoint.

## Execution path

1. `evaluator.run.evaluate(..., contract=...)` validates bounded source and data,
   creates a fresh contained environment, and stages the unchanged `candidate.py`
   plus the hash-bound `evaluator/factory.py`. Neither is imported on the host.
2. The unchanged, separate `evaluator/process.py` observer launches the driver
   in a child interpreter, capturing signed termination and bounded log bytes.
3. The driver imports the module as `candidate`, resolves callable `build_model`,
   invokes it without arguments, checks compatibility with pinned `openmc.Model`,
   and passes that exact returned object to the captured unbound
   `Model.export_to_model_xml` method at `/work/model.xml`. No global-model search,
   script fallback, XML rescue or physical correction is performed.
4. The controller retains independent process records, freezes all container
   processes, retrieves a bounded flat archive, verifies artifact identities and
   admits the combined XML envelope. The new envelope permits only `model.xml`.
5. The private assessor passes those exact bytes to the existing fresh XML-only
   inspector. Repeat construction uses another fresh export container and another
   fresh inspector. Existing semantic comparisons remain unchanged; byte equality
   or matching OpenMC identifiers is not introduced as a physical requirement.
6. The existing separate transport consumes the admitted XML, never the candidate
   module or a serialized live model. Existing scientific checks and the frozen
   scoring policy then apply.

`evaluation.candidates.run.evaluate` records the selected contract in its assignment
and uses it for both exports. `evaluation.candidates.verify` requires the assignment, public
prompt and export versions to agree before reconstructing outcomes. Factory
staging, launch and source receipts are checked by `phase_evidence.export_outcome`.

## Ordinary execution contract and limits

Import makes the entry point available. Definitions, helpers and in-memory
initialization are allowed; guarded manual-use code is not executed. Construction
returns a model. An annotation is optional; implicit materials discovered through
geometry are allowed, as supported by OpenMC 0.15.3. There are no new requirements
on optional `Model` attributes and no new dependencies or bundled input resources.

The pinned source confirms that `export_to_model_xml` writes consolidated XML;
`export_to_xml` writes separate files. Only the former is used. Its existing default
behavior is preserved, including materials inference. The driver does not adjust
materials, geometry, temperatures, boundaries, histories or sources.

Practical side-effect checks are deliberately bounded:

- Compare metadata snapshots of `/input`, `/tmp` and `/work` after import and
  construction, without following symlinks, with a 256-entry bound. Persistent
  changes or coverage exhaustion fail delivery. Other writable special files,
  transient changes restored between snapshots and native-memory effects are
  not exhaustively observed.
- A CPython audit hook rejects observed XML/HDF5 writes and child-process launch
  events during import/resolution/construction/return checking. Caught attempts
  remain recorded in the driver's violation list. Ordinary in-memory operations
  are unaffected. Direct native syscalls or library activity without these audit
  events are not fully covered. No general purity guarantee is claimed.
- The required fresh output location is checked before loading the candidate.
  The exporter accepts only the new combined envelope. Pre-existing XML cannot
  rescue an invalid return in ordinary driver execution.

**The driver shares the candidate interpreter.** A hostile candidate can affect
Python state, object methods, introspection and diagnostics. Capturing the class
and unbound export method reduces accidental ambiguity; `isinstance`, hooks and
method calls are not independent security or scientific attestations. Containment,
the external process observer and fresh untrusted-XML admission remain necessary.
The inspector observes the exported physical artifact, not the original live
Python object. Host, Docker, kernel and pinned images remain trusted.

## Evidence and attribution

| Phase | Retained evidence | Authority |
|---|---|---|
| Driver/candidate staging and selected launch | `staging.json`, `driver-staging.json`, `execution-launch.json`, source snapshots/hashes | Host controller and staging process |
| Module loading, entrypoint resolution, construction, return check, export | JSON diagnostic lines and tracebacks in `candidate-stderr.txt` | Candidate interpreter; diagnostic only |
| Child completion or budget stop | Protected observer output, child process record, captured log bytes, post-execution Docker state | Separate process observation |
| Artifact retrieval | Frozen-container record, raw bounded archive and retrieval receipt | Controller/Docker |
| XML observations | Separate inspector input, worker, execution and result records | Fresh XML-only process, within existing coverage |

Internal diagnostics identify a reported phase, exception type and bounded text.
They are never promoted to independent receipts. A forged success message cannot
override an observed nonzero exit or missing XML. A zero exit with XML establishes
delivery under the observed process protocol, not proof of adversarial internal
behavior or scientific fidelity. Candidate source is never imported to verify a
historical claim.

Ordinary nonzero child exits (including explicit 255), missing/invalid output and
observed budget excess follow the existing model-delivery-failure policy. None,
wrong type, absent/noncallable/incompatible-argument factories and detected side
effects normally raise inside the child, preserving their traceback and exit.
`SystemExit`, `os._exit`, signals and observer stops are not caught and replaced
by a generic driver exit. A signal/OOM or interrupted observer remains
indeterminate and unscored. Documented controller/setup defects and missing or
contradictory receipts are not converted to candidate scientific failures.
See the evidence semantics and trust limits in the root DESIGN.md.

Coherent evidence, contradictory evidence and insufficient evidence remain
distinct from execution outcome, attribution and score eligibility. No new
scientific points or weights are introduced. Exception text alone does not prove
whether a fault originated in candidate intent, library code or the driver.

## Commands and checks

The current commands and fixed budgets are in the root README and DESIGN.
Run the portable unit suite for synthetic controls. Native characterization
fixtures and historical qualification evidence remain in the private research
repository; those commands are not shipped in the public source snapshot.
Driver phase diagnostics are candidate-interpreter observations, not independent
proof. Process and retrieval receipts remain the authority for completion.
