# Reproducibility Milestone v1: audit and validation

Starting main: `b16e2af81b0031e14b2979db7a78b25599832a0c`.
Branch: `feat/reproducibility-v1`. PR #8 stays closed.

## Audit recorded before implementation

The public portable layer already ran with host Python and no credentials.
Native assessment was blocked on preloaded project-specific images, a flat
external nuclear-data collection, and the historical private six-case reference
index. No frozen public candidate or public reference package existed.

The existing evaluation path was suitable: isolated factory export, admitted
XML, scientific inspection, boundary observation, native transport, fixed
comparison/scoring, then independent retained-evidence verification. The gap
was dependency acquisition and explicit selection, not a missing grader.

The selected task is the unchanged `reflective_pin_cell`, under
`openmc-model-factory-v1`, `factory-serial-v1`, and
`factory-assessment-boundaries-v4-temperature-source-v1`.
This public route does not claim full experimental v7 parity.

## Resolved preparation failures

The Docker store initially had no free overlay capacity. APT signature failures
occurred during the source build. They disappeared after the owner-authorized
unused-build-cache cleanup; signature verification was never disabled.
[Exact cleanup commands and preservation checks](cache-cleanup.json),
[before usage](cache-cleanup-before.txt), and [after usage](cache-cleanup-after.txt)
record Docker's accounting. All 81 pre-existing images, all containers (zero)
and all seven volumes were unchanged during cleanup.

An initial public-reference implementation used a nested pin universe. Existing
material, geometric probes and settings checks passed, but twelve outer-face
boundary-type/albedo requirements remained indeterminate because a filled root
cell could meet the face. Generation stopped before transport. That attempt is
retained locally under `scratch/reproducibility-v1/reference-generation`.
The final reference uses flat cells with the identical physical specification,
within the observer's existing supported coverage. No criterion was bypassed.

## Runtime and data provenance

[The built runtime inventory](runtime-generation.json) binds the public source
recipe, local image and native binary identities, actual Python package versions,
OpenMC 0.15.3, GCC 12.2.0 and HDF5 1.10.8. The build used `--no-cache` and
`--pull`; the Dockerfile has no project-specific base image.

The complete official ENDF/B-VIII.1/NJOY2016.78 archive was streamed from its
public upstream download. Only the ten required tables were retained, outside
Git. The [public acquisition receipt](../../examples/reflective_pin_cell/reference/data-acquisition.json)
records archive, subset and generated-index hashes. No historical/private
reference or data archive supplied those bytes.

Raw development receipts remain local because they contain host paths and
container details. Only explicitly selected metadata is published here.

## Development native check

The public reference passed generation/review with
k-effective **1.4488925454032306 ± 0.00016175366894689348** (one sigma),
40 million total / 30 million active histories, and 1,382.61 seconds including
transport setup/collection. Its active-half entropy difference was
−0.0003487683432386035 bits; leakage was zero.
[Reference review, warning and descriptive histories](reference-review.json)
retain the evidence limits. These checks do not establish nuclear-data accuracy
or convergence by themselves.

The first candidate assessment completed and its independent verifier reported
coherent evidence and verified protocol success. Candidate k-effective was
**1.4481972350919354 ± 0.0003414972628200393**. The candidate-minus-reference
difference was **−69.5310 pcm**, with the existing approximate 95% interval
**[−143.5933, +4.5312] pcm**, inside the unchanged ±150 pcm criterion.
All named implemented checks passed. This is computational agreement under the
declared library/runtime, not experimental validation.

Portable development suite: **313 tests passed**, no skipped tests.
[Baseline comparison](unchanged-science.json) records 65 untouched scientific,
authoring and historical-result files. The scalar/partial score is not a new
rubric and official grading activation remains disabled.

Same-runtime repeat and second fresh-checkout validation are recorded separately
when complete. Do not infer those results from the initial development run.
