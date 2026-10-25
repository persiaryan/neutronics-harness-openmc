# Representation evaluator revision v1

The prospective `factory-assessment-confirmation-v2-representation-v1` route
addresses representation-dependent geometry/source coverage and separates
demonstrated nonconformity from score completeness. It is explicit opt-in for
the twelve confirmation tasks. Default protocols and the weighted rubric retain
their existing rules; the 240 original outcomes remain 202/20/18. No campaign
candidate is repaired, replayed or reassessed by these controls.

## Critical path

`candidates.run.evaluate()` independently exports the final model once. The
prospective route selects `boundary_worker_v3.py`, then runs a separate
`source_domains_worker_v1.py` against the same XML and public probe points.
`candidates.representation.assess()` compares accepted support with the public
requirements. Its `fidelity_checks()` localizes unknown source options rather
than blanking unrelated sampling/physics/entropy checks. Existing native transport
and numerical/weighted scoring follow. `representation.conclusion()` reports
conformance, evaluation completeness and score completeness independently.
`candidates.verify` reconstructs all of this from retained receipts.

The new source phase has its own 120-second inspection limit, using the existing
inspection budget per phase; no authoring/provider budget changes. Reports use
`private-candidate-diagnostic-v6`. Assignment metadata binds the new observer
and fidelity implementation. Observation definitions distinguish the route;
historical receipts cannot be relabeled as prospective ones.

The reference implementation identity changes deliberately. Old sealed references
are not silently admitted under the new code. A new full assessment requires a
separately qualified reference package bound to the current implementation.
Historical assessment/review uses its original checkout and verifier. The
prelaunch INDC compatibility exception is not extended to this revision.

## Geometry

V3 retains the v2 Boolean reduction and limits, in a separate standalone worker.
Conservative bounds for both signs of each nonplanar halfspace are propagated
into every occurrence, including complements. Disjointness can establish a
sign throughout an open arrangement cell; overlapping bounding boxes never
establish occupancy. This repairs the asymmetric pruning that removed a pin
cell while leaving the same cylinder undecidable inside background water.

Complete arrangement occupancy can refute an explicit finite-box requirement
with empty, unbounded or nonbox shape evidence. Unresolved curved predicates
remain unknown. The observer still does not certify nonoverlap, arbitrary
hierarchies, periodic coupling, curved external faces or face edges/corners.

## Accepted source support

OpenMC 0.15.3 resamples the proposal subject to the intersection of domain and
fissionable constraints. The comparator supports qualified uniform box/Cartesian
proposals, resampling, and flat untransformed material/void cells. Cell/material
restrictions are interpreted through the loaded physical inventory. Exact
equality of accepted and fissile cell sets is a sufficient positive proof.
Known omitted/extra support can be refuted by an interior witness inside the
proposal. Absence of a counterexample never proves an unmatched cell-set identity.
Support identity alone does not prove a nonempty accepted distribution; native
input/execution gates remain required for a complete assessment.

Fissionability labels are limited to the benchmark's matched uranium fuel,
mixture, water and zirconium recipes. Unknown compositions, unresolved hierarchy,
universe restrictions, duplicate/malformed constraints and unsupported semantics
remain unassessed. Extra restrictions can invalidate a positive equivalence;
a known omitted fuel region remains false even alongside such an unknown.

Primary implementation authority:
[OpenMC spatial rejection](https://github.com/openmc-dev/openmc/blob/v0.15.3/src/source.cpp#L226),
[external-source sampling API](https://github.com/openmc-dev/openmc/blob/v0.15.3/openmc/lib/core.py),
[native surface-distance selection](https://github.com/openmc-dev/openmc/blob/v0.15.3/src/cell.cpp#L910).

## Conformance and score

A known false requirement yields `nonconforming` even if another required check
is unknown and the unchanged weighted score is null. Known mismatches remain
listed. Otherwise unknown checks yield `indeterminate`; complete matching checks
yield `conforming_within_protocol`, explicitly limited by finite coverage.
Missing/contradictory execution evidence or uncertain cleanup cannot establish
a conformance verdict. This is diagnostic research output, not safety approval.

## Independent controls and commands

[CONTROLS.md](../../evaluation/representation/CONTROLS.md) gives dimensions,
the independent set identity, positive-volume counterexamples and sampling rules.
The public controls do not import campaign models or private references.

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B -m evaluation.representation.qualify --output scratch/representation-v3
python3 -B -m evaluation.representation.qualify --family source --output scratch/representation-source
python3 -B -m evaluation.representation.qualify --observer v2 --output scratch/representation-v2
python3 -B -m evaluation.representation.qualify --verify --output scratch/representation-v3
python3 -B -m evaluation.representation.qualify --verify --family source --output scratch/representation-source
python3 -B -m evaluation.representation.native --output scratch/representation-native --data-index "$DATA_INDEX"
python3 -B -m evaluation.representation.native --verify --output scratch/representation-native --data-index "$DATA_INDEX"
```

Use fresh output directories. The v2 command intentionally returns nonzero when
it fails the new coverage requirements; its read-only verifier can still confirm
that this negative result faithfully reconstructs the retained execution.
Native commands require the pinned local OpenMC 0.15.3 images and nuclear data.
The source-law/crossing controller mounts only read-only data, stages unchanged
Python bindings in tmpfs beside a link to the pinned native library, and retains
worker, binary/binding hashes, process outcome, containment, data hashes and
cleanup evidence. No provider authentication is used.

After separate reference qualification, select the route explicitly:

```sh
python3 -B -m evaluation.candidates.run --case indc107_reflective_pin \
  --candidate "$CANDIDATE" --reference "$REFERENCE_PACKAGE" --data-index "$DATA_INDEX" \
  --evaluator-protocol factory-assessment-confirmation-v2-representation-v1 \
  --output scratch/prospective-assessment
python3 -B -m evaluation.candidates.verify --assessment scratch/prospective-assessment \
  --reference "$REFERENCE_PACKAGE" --data-index "$DATA_INDEX"
```

## Results and limits

The [versioned public result summary](representation-evaluator-results-v1.json) records the actual portable/native checks,
retained report digests, observed order dependence and unsuccessful pilot-control
attempts. These are development/qualification observations, not independent new
agent-study results. Full prospective assessment execution with newly sealed
references, human scientific review, statistical calibration and a new study
remain separate work. No efficacy or global geometry-validity claim follows.

On 2026-10-24 the final XML controls passed 16/16 geometry requirements with v3
and 14/14 source-support requirements. V2 established conformity for only two
of the seven equivalent water representations; v3 established it for all seven.
The injected interior hole and unbounded domain remain detected. The overlap
control demonstrates the separate probe's detection, not a new global proof.

The native library controls passed ten source cases, with 4,096 samples and
seed 41 each. All six equivalent encodings produced the same position digest;
the four wrong-domain controls sampled the expected different regions. Four
coincident-face crossing controls also completed their intended qualification:

| Lower-face representation | Observed native outcome | Boundary interpretation |
|---|---|---|
| Two vacuum planes, either order | Leakage 1, zero reported uncertainty | Supported uniform vacuum behavior |
| Transmission plane first | Exit 255 with the specific lost-particle diagnostic | Indeterminate conflicting behavior |
| Vacuum plane first | Leakage 1, zero reported uncertainty | Indeterminate conflicting behavior |

This is direct evidence that CSG volume equality alone does not establish the
same transport operator for conflicting coincident surfaces. The new observer
retains conservative unknowns in both conflicting orders.

The four earlier native-control attempts remain retained: three were blocked
by driver/runtime-fixture setup errors; the fourth sampled sources successfully
but attempted to serialize undefined, unrequested eigenvalue estimators in a
fixed-source crossing control. Those crossing outputs receive no qualification
credit. The final attempt extracts only the defined leakage observable and its
retained evidence is reconstructed from execution receipts by the read-only verifier.

The same AI assistant authored controls and implementation; their literal/set
oracles are separate from the observer, but independent human review is pending.

The subsequent [qualification follow-through](representation-followthrough-v1.md)
records explicit retained-reference requalification and fixed end-to-end native
controls. This document's public JSON remains the original milestone snapshot.
