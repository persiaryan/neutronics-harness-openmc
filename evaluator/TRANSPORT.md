# Isolated XML loading and transport

Native transport is the internal final phase of `evaluation.candidates.run`. It
consumes an admitted combined XML export, with no candidate Python or builder
feedback. Use the root README workflow and the fixed assessment profile.

## Critical execution path

1. `transport_input.accepted_export()` requires `exported`, passed XML inspection,
   confirmed cleanup, a removed lifecycle and matching XML byte count/SHA-256.
   It reads only four receipt files and `artifacts/model.xml`, not candidate
   source or arbitrary sibling artifacts. The receipts are trusted operator
   records; hashes are not signatures against someone who can rewrite them.
2. `transport_input.transport_profile()` independently checks the XML envelope
   and supported execution features. It records requested sampling and required
   nuclear-data tables. It rejects unsupported inputs instead of repairing them.
3. `run.data_directory()` admits the sole host bind, a flat data-only collection.
   `transport.data_identity()` hashes the index and every file required by the
   explicitly named neutron nuclides and thermal-scattering tables. The host
   reads these as bytes, without importing OpenMC or parsing HDF5.
4. `transport.transport()` creates and verifies a fresh container and bounded
   tmpfs work volume. The image includes only pinned dependencies and v5 trusted
   worker code. Runtime version, native executable/library hashes and worker
   hash are retained; a stale worker image stops before XML staging.
5. Bounded stdin transfers XML to `/input/model.xml` and `/work/model.xml`, with
   a matching hash. `transport_worker.load_xml()` calls
   `openmc.Model.from_model_xml()` and records settings and boundary checks.
   This Python object is never re-exported or used to replace settings.
6. A separate `docker exec` runs `/opt/openmc/bin/openmc -s 1` in `/work`, reading
   the original combined XML. The host bounds its output and wall time. No
   seed, particles, source, temperatures or geometry are overridden.
7. `transport_worker.extract()` reads the native final statepoint using
   `openmc.StatePoint(..., autolink=False)` inside the container. It verifies
   solver version, final batch, seed, particles, generations per batch, inactive
   and active batch counts, finite positive k-effective and uncertainty, and
   complete finite generation histories. Requested entropy must be present.
8. The controller freezes the runtime before bounded artifact retrieval. It
   never extracts tar paths or parses HDF5 on the host. It checks the returned
   JSON receipts, unchanged XML bytes and the retained statepoint hash.
9. The container and volume are removed, then data hashes are checked again.
   Changed data invalidate the result. Before/after checks detect observed
   changes; they are not an atomic snapshot of host data or proof of authenticity.

These APIs were checked against the installed OpenMC 0.15.3 source and real
runtime. General upstream references: [Model XML loading](https://docs.openmc.org/en/stable/pythonapi/generated/openmc.model.Model.html)
and [StatePoint fields](https://docs.openmc.org/en/stable/pythonapi/generated/openmc.StatePoint.html).
The upstream stable documentation may describe a newer version.

## Retained success verification

`evaluation.candidates.receipts.transport_record()` requires successful process
receipts for preflight, solver-version, runtime-identity, staging, XML loading,
OpenMC transport and statepoint extraction. Each receipt must contain exactly an
integer zero exit code and a null stop reason. It also rechecks the frozen
container's isolation and requires it to have been running and paused before
artifact retrieval. The receipt bytes join the existing evidence inventory.

`review_assessment()` leaves a missing required receipt **insufficient** and a
receipt contradicting claimed success **contradictory**, both with `score=null`.
The original reported score remains explicitly separate; neither state assigns
a physical model failure or changes the archived report. Complete evidence still
uses the same scientific checks and scoring. These are checks on trusted operator
records, not signed proof against an operator rewriting the whole dossier.

Portable regression command:

```sh
python3 -B -m unittest tests.test_transport_receipts -v
```

## Supported inputs and resource limits

The first profile supports continuous-energy neutron eigenvalue calculations,
inline CSG cells/surfaces/rectangular or hexagonal lattices, explicit nuclide
materials, thermal-scattering tables, inline independent sources, regular
entropy meshes, temperature settings and ordinary state/source-point options.
Default seed, inactive batches and generations per batch are reported when
omitted; OpenMC's source and physical defaults are not replaced by the evaluator.

File/compiled sources, file paths, DAGMC/unstructured geometry or meshes,
nonempty tallies/plots, multigroup, photon transport, variance-reduction and
other unsupported settings are rejected. An explicit cross-section path must
equal `/data/<admitted-index-name>`; omission uses the provided environment.
Output paths are restricted to the working directory. A final-batch statepoint
must be requested when an explicit statepoint schedule is given.

Admission allows up to 1,000,000 particles, 10,000 batches, 100 generations per
batch and 50,000,000 total histories, with at least two active batches. Regular
meshes are limited to 1,000,000 cells. These are execution limits, not scientific
acceptance criteria. Resource exhaustion or unsupported features are not proof
of a physically incorrect model.

The container has no external network, credentials, host home/repository or
Docker socket. It is nonroot, read-only at the root, with capabilities dropped,
no new privileges, 3 GiB RAM, 2 CPUs and 128 processes. Input tmpfs is 16 MiB,
temporary tmpfs 128 MiB, and work volume 256 MiB. XML is capped at 8 MB, combined
stdout/stderr at 1 MB per phase, each retrieved artifact at 32 MB and the archive
at 128 MB (at most 64 entries). The assessment profile sets the solver wall budget to 1,800 seconds. Loading, extraction, staging and control operations have
separate bounded deadlines. The reported elapsed time includes setup and hashing.

The native solver is the reviewed serial Linux ARM64 OpenMC 0.15.3 build, commit
`27e38e894697bb32a1dac7848d2618818b6b8daf`. Its warning that it ignores `-s 1`
reflects a build without OpenMP; it runs serially. The runtime build copies only
third-party Python packages from the S04 dependency image and native
`/opt/openmc/bin` and `/opt/openmc/lib` from pinned local image
`sha256:973f4f64b0e4df0b32c9e1578bba8de333d3b423e89fae8d29f397bd03a2ce8c`.
No v4 harness, reference, fixture or data files are copied. Reproducing these
dependencies on another machine remains a portability prerequisite.

## Results and limits

- `calculated_unreviewed`: XML loaded, solver completed, extracted results and
  artifact identities passed checks, data were unchanged at the checks, cleanup
  was confirmed. This is **not** a scientific pass.
- `rejected`: input was not admitted, XML loading failed, or the solver returned
  a normal nonzero error. Inspect the phase and logs; do not conflate unsupported
  features or data problems with demonstrated modeling errors.
- `budget_exceeded`: a phase exceeded its time or log budget. The container is
  removed before further data hashing and no live artifacts are retrieved.
- `failed`: infrastructure, abnormal process exit, extraction, artifact
  integrity or data-stability checks failed. No numerical success is reported.
- `cleanup_uncertain`: removal could not be confirmed. Do not replay.

`artifacts/calculation.json` contains k-effective with one-sigma Monte Carlo
uncertainty, actual sampling and native runtime metadata.
`artifacts/convergence.csv` contains generation number, active/inactive flag,
k per generation and entropy (blank if not requested).
The native statepoint, XML, other bounded solver outputs, logs, data identities,
container checks and controller source snapshots are retained.

No convergence threshold, overlap-absence proof, geometry/material fidelity
score or private reference comparison is implemented. Loading and transport can
both succeed for an incorrect physical model. No automatic repair or feedback is performed. Historical qualification
records and their original commands are restored through the checkpoint/archive.
