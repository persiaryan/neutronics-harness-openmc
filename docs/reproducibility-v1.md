# Reproduce one native OpenMC assessment

This workflow evaluates a **handwritten reflective pin-cell fixture**, not an
LLM-authored historical submission. It uses the existing isolated factory,
admitted XML, scientific inspector, boundary observer, native transport,
numerical comparison, scoring and retained-evidence verifier.

The supported target is a **native Linux ARM64 Docker engine** (including
Docker Desktop on Apple Silicon), OpenMC **0.15.3**, and one native transport
thread. x86_64, emulation and other OpenMC versions are not qualified here.

## Requirements

- Git and host Python **3.12+**. Host commands use the standard library only.
- Docker with BuildKit and a native ARM64 Linux engine. Allow at least 8 GB
  Docker memory and 12 GB free Docker disk space for source builds/cache.
- HTTPS access to Docker Hub, Debian Snapshot, GitHub, PyPI and the official
  OpenMC data host during preparation. Assessment containers have no network.
- Around **9.7 GB download**, **3.0 GB retained data**, and memory for XZ
  decompression. The full archive is streamed, not stored or fully extracted.
- No OpenMC host install, Codex account, API key or private reference directory.

The runtime recipe pins Python 3.12.11's public image digest, Debian's
2025-10-01 snapshot, OpenMC commit
`27e38e894697bb32a1dac7848d2618818b6b8daf` (v0.15.3), its Git submodules, and
[scientific Python dependency versions](../reproducibility/runtime/requirements.txt).
It builds native OpenMC with MPI disabled and OpenMP available; assessment uses
one thread. Compiler/HDF5 packages come from that fixed Debian snapshot: GCC 12.2.0 and
HDF5 1.10.8 in the validated build. Scientific Python dependencies are directly
pinned; auxiliary transitive Python packages are resolved by PyPI. This is not a
hermetic or bit-for-bit container-build guarantee.
The [Dockerfile](../reproducibility/runtime/Dockerfile) starts from public images,
not any historical project image.

## Clean-checkout commands

Before this PR is merged, add `--branch feat/reproducibility-v1` to the clone command.
Run these from a checkout containing this milestone. Use new output directories;
the commands refuse to overwrite evidence.

```sh
git clone https://github.com/persiaryan/neutronics-harness-openmc.git
cd neutronics-harness-openmc

python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B -m prompts.prepare --case reflective_pin_cell --output scratch/public-prompt

python3 -B -m reproducibility.build_runtime \
  --no-cache --output scratch/public-runtime.json

DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/nh-public-data.XXXXXX")/tables"
python3 -B -m reproducibility.data \
  --source download --output "$DATA_DIR" \
  --expected examples/reflective_pin_cell/reference/data-acquisition.json \
  --receipt scratch/public-data-receipt.json
DATA_INDEX="$DATA_DIR/cross_sections.xml"

python3 -B -m examples.reproduce_reflective_pin_cell \
  --runtime scratch/public-runtime.json \
  --data-index "$DATA_INDEX" --output scratch/public-example
```

Inspect `scratch/public-example/report.json` and `report.md`.
A successful example exits zero only after the existing independent verifier
reports coherent retained evidence and all required protocol checks pass.
Do not infer success from native completion alone. Inspect failures and null
results as reported; the runner does not repair or retry a candidate.

For a second same-runtime check, repeat only the last command with
`--output scratch/public-example-repeat`. Compare the final XML SHA, candidate
k-effective and checks. Timestamps, elapsed times, container IDs and raw
statepoint hashes need not match. No cross-machine bitwise reproducibility claim
is made: Monte Carlo sampling, compiler/library differences and platform
differences must be distinguished from deterministic grading of fixed evidence.

## Public nuclear data

The unchanged task specifies **ENDF/B-VIII.1** at 293.6 K, nearest-temperature
lookup with 1 K tolerance. The [official OpenMC data page](https://openmc.org/data/)
offers an HDF5 library processed with **NJOY2016.78**. Acquisition uses its public
Box download endpoint, following the current host redirect:
[official archive](https://anl.app.box.com/public/static/6qr7jezzihkj9p9esl5jn19qgpujyjyz.xz).

This milestone publishes hashes and provenance, **not nuclear data**. Obtain
the data directly from upstream; the repository's MIT license does not license
the dataset. The website's documentation license must not be treated as a
separate grant to redistribute the data.

The acquisition command verifies the complete archive and the selected bytes:

- Archive size: **9,661,406,540 bytes**.
- Archive SHA-256:
  `b7ad59cb4a3d76d8a291326093a98507f8d24b6e6af629116d3f7dc85f83c4cb`.
- Nine neutron tables: H1, O16, U235, U238, Zr90, Zr91, Zr92, Zr94, Zr96.
- Thermal scattering: c_H_in_H2O.
- Required HDF5 subset: **2,974,881,632 bytes**.

An already downloaded official archive can be supplied as
`--source /path/to/library.tar.xz` instead of `download`; all checks still apply.
The reference run emitted a **Zr96 unresolved-resonance probability-table warning
at 294 K**. The pinned OpenMC source detects negative table entries and clips
negative sampled elastic, fission or capture cross sections to zero; see
[the pinned implementation](https://github.com/openmc-dev/openmc/blob/27e38e894697bb32a1dac7848d2618818b6b8daf/src/nuclide.cpp#L898).
The data and this behavior were not changed. Its numerical impact is not
quantified here: shared-data agreement is not validation of the data library.

Long downloads can fail or time out; partial output is retained and there is no
automatic retry. If retrying after checking the connection, use a new data
directory and receipt name. On macOS, an optional `caffeinate -dimsu` prefix
keeps the machine awake during preparation or native execution.

A changed upstream archive fails verification. Never silently substitute another
library or temperature processing.

The result is a flat directory of ten ordinary HDF5 files and a relative
`cross_sections.xml` index, outside the repository. No natural-element
expansion, data rewriting or private path is involved. The evaluator checks the
collection against the public reference and hashes required data before and
after transport. Receipts stay outside the flat data directory.

## Runtime identity and isolation

`scratch/public-runtime.json` binds two local immutable image IDs and native
binary hashes to the pinned semantic recipe. A rebuild may produce different
image IDs; users are not expected to possess the owner's historical image IDs.

The binding is explicit operator-owned configuration, **not signed attestation**.
It does not authenticate an untrusted Docker daemon or maliciously modified
local receipts. The builder command produces it from images it builds. Execution
and verification still bind the selected IDs, workers, source, XML, data, process
completion and containment. Existing private assessment defaults are unchanged;
the public route never falls back to private reference packages.

Export receives only the submitted Python and read-only data, in a non-root,
networkless container. Inspectors receive XML and no candidate Python or nuclear
data. Transport receives admitted XML in a separate container, without candidate
Python or reference access. Phase budgets, cleanup requirements and zero automatic
retries remain unchanged.

## Separate public demonstration reference

The [reference source](../examples/reflective_pin_cell/reference_model.py) is a
new, literal transcription of the fully specified
[public synthetic task](../prompts/cases/reflective_pin_cell.md). It uses flat annular cells bounded by a composite reflective box. The
[candidate fixture](../examples/reflective_pin_cell/candidate.py) uses explicit
bounded annular cells. Neither was copied from a private historical reference.

Reference sampling is 25,000 particles, 800 batches, 200 inactive batches,
two generations per batch, seed 19 and one thread: 30 million active histories.
The candidate retains the task's 10,000 particles, 400 batches, 100 inactive,
two generations per batch and seed 1: 6 million active histories.

The small [reference package](../examples/reflective_pin_cell/reference/) retains
source/task/runtime/data identities, calculation metadata, final XML, k/entropy
histories, fidelity observations and a hash inventory. It omits HDF5/statepoints.
Generation uses the same existing factory/inspection/transport components and
requires passing physical/settings checks and the existing numerical-quality
screens before writing the package.

This is a **computational reproduction fixture**, not an experimental benchmark,
independent scientific certification or replacement for the historical private
reference suite. Shared OpenMC/data/model biases remain. Finite probes and an
entropy drift screen do not establish universal geometry validity or convergence.
The existing ±150 pcm criterion and scoring weights are unchanged and remain
internal, uncalibrated design choices.

Maintainers can generate a separate new package with the documented
`python3 -B -m reproducibility.reference --help` command. This is separate from
normal assessment; the example never regenerates its answer at run time.

## Reports and reproducibility boundaries

The public summary reports repository commit/dirty state, protocol, runtime,
data/reference/candidate/XML identities, named scientific checks, contract and
native completion, candidate/reference k-effective, comparison, score, independent
verification status, timing and limitations.

Raw local receipts under `assessment/` contain operational host paths and
container details. Share the allowlisted `report.json`/`report.md` summaries;
do not publish raw receipts indiscriminately.

| Level | Scope |
|---|---|
| Public code/tests | Portable standard-library controls |
| Public prompt/preparation | Public task and budgeted prompt preparation |
| One native public example | This ARM64/OpenMC 0.15.3 computational fixture |
| Live LLM authoring | Separate provider authentication and runtime required |
| Historical Request-16 replay | Not publicly reproducible; raw/private dependencies absent |

The published Request-16 results and their limitations are unchanged. This
example does not reconstruct any of the 150 historical sessions.

See the [recorded validation and limitations](reproducibility-v1/VALIDATION.md).
