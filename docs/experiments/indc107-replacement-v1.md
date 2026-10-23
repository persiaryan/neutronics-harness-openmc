# INDC-USA-107 problem 1: frozen computational replacement

The owner selected this public case before any evaluated A/D generations.
It replaces perforated_mixture_block in region-confirmation-candidates-v3.
The previous release manifest and task remain unchanged under confirmation_v1;
all failed qualification results remain operator evidence.

## Frozen upstream source

Repository: https://github.com/mit-crpg/benchmarks
Commit: ba41bee54320ada0b4ac39a0dd2ca3c1d090a450
Directory: indc-usa-107/openmc/problem1

Original geometry, materials, settings, spectral tally, repository README and
license are retained byte-for-byte under evaluation/upstream/indc_usa_107_p1.
Its manifest records upstream paths, sizes, SHA-256 digests and explicit adaptations.
The evaluator checks the manifest digest and every original file; its identity
includes these assets. Git fetch and extraction receipts stay operator-local.
This is a computation derived from the public inputs, not an experimental
validation or a reproduced literature eigenvalue.

## Physical statement and adaptations

The transverse geometry is a centered uranium-metal cylinder, radius 1.27 cm,
inside a square of pitch 5.08 cm. Uranium has density 18.8 g/cm3 and relative
atom amounts U235:0.98, U238:99.02. Water has density 1.0 g/cm3, H1:2, O16:1,
with c_H_in_H2O. There is no oxide, cladding or gap.

The upstream geometry is axially unbounded. The explicit task variant uses
z=-1 to +1 cm with reflective axial faces; all six exterior faces reflect.
This translation-invariant slice is the chosen representation, to be checked
numerically under the harness rather than assumed identical to an external
published result. All materials and cells are prescribed at 293.6 K.

Upstream sampling is replaced by the existing harness sampling, explicit seed,
fissionable source resampling, isotropic/Watt specification and an 8x8x1 entropy
mesh. The original source box is retained. The upstream spectral-flux tally is
archived but excluded from this eigenvalue/model-construction task.
The complete public statement is prompts/confirmation_v2/cases/indc107_reflective_pin.md.

This is an external control, not a claim of geometric difficulty equivalent to
the retired perforated-body transfer task. The twelve-task suite now contains
four reuse, three transfer, four original control tasks and one external control.
No A/D result has guided this replacement.

## Independent evaluation and verification

The literal oracle checks the metal/water partition, radial interfaces,
temperature, data recipes, full axial slice and all reflective faces.
Analytic volumes are 2*pi*1.27^2 cm3 of metal and 2*5.08^2 minus that value
of water. A finite set of points remains a bounded diagnostic, not a global proof.

Existing export/inspection/transport images, workers, rubric and numerical margins
are unchanged. The new model must pass correct, cell-order and injected shared-region
mutation XML controls; five fixed native reference runs; independent reconstruction
of those runs; and a fresh reference-as-candidate assessment.

The eleven retained tasks have identical source statements, versions, complete
finite point lists, expected material/temperature maps and face requirements.
They were reconstructed with the original frozen code before extension. The
compatibility-indc107-v1.json rule accepts only the two exact prior generation
identities, the known previous suite hash and those eleven unchanged contracts.
It checks unchanged common evaluator/criteria files, exact extended cases code
and frozen new upstream assets. No original reference or assessment is resealed,
relabeled, repaired or silently rescored. Original generation identities remain
visible in current reconstruction reports.

## Local native qualification

Use fresh output directories; no provider calls, retries or replacement seeds.

~~~sh
python3 -B -m evaluation.confirmation.controls \
  --sources scratch/confirmation-reference-sources-v3 \
  --output scratch/indc107-native-v1/controls \
  --data-index "$DATA_INDEX" --cases indc107_reflective_pin

python3 -B -m evaluation.confirmation.qualify \
  --sources scratch/confirmation-reference-sources-v3 \
  --output scratch/indc107-native-v1/references \
  --data-index "$DATA_INDEX" --cases indc107_reflective_pin
~~~

The operator reference is separate from public builder inputs.
The numerical qualification keeps the predeclared three primary seeds and
two initialization controls, unchanged thresholds, single-thread native execution
and 1800-second transport cap. A failure remains a failure/inconclusive result;
it does not trigger tolerance relaxation or seed selection.

Scientific review, sample-size justification, real provider delivery controls
and A/D dispatch remain distinct. This implementation does not launch them.

## Independent upstream-input construction

The final candidate is a second implementation: it loads the byte-exact pinned
geometry/material XML, normalizes the g/cc unit alias to g/cm3, applies the
explicit reflective axial slice and the declared harness settings. The reference
constructor expresses the same problem separately in Python. The sixth native
transport compares this upstream-input candidate with the three-seed reference
mean, rather than submitting the same constructor twice. It retains its own
fresh export, inspections, transport and independent evidence review.

## Completed implementation checkpoint, 2026-10-18

All 461 portable tests passed. The replacement's three native XML controls
passed, as did the five fixed reference transports and independent reconstruction.
The separate candidate importing the frozen upstream XML passed the full final
assessment with score 100 and coherent retained evidence. All six planned
transports completed; no retry, seed replacement or tolerance change was used.
Numerical values and raw grading evidence stay in ignored operator artifacts
under scratch/indc107-native-v1, outside public builder inputs.

The complete forty-control matrix was independently reconstructed for the revised
suite. All twelve retained/reference cases and twelve final assessments pass
the technical readiness check. A fresh 240-slot manifest was prepared without
dispatch; provider qualification, scientific review and sample-size justification
remain pending. The retired perforated-block task, its inconclusive result and
all previous source/evidence versions remain preserved.
