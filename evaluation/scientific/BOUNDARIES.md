# Effective external boundaries, observation version 2

The qualified scope is uniform effective behavior over each open face/property,
using conservative possible contributors. Historical qualification is recoverable
from the checkpoint/archive. Current executable controls live in
`tests/fixtures/boundary_controls.py`; `boundary_scope.py` reports all six tasks.

A fresh mount-free, networkless OpenMC 0.15.3 process loads retrieved XML using
OpenMC's object model. It receives no task requirements, reference, expected value,
score or candidate Python. Both assistance and final assessment use this primitive;
final assessment regenerates and reinspects its own artifacts.

## Separate responsibilities

1. `boundary_worker_v2.inspect`: physical observations and coverage only.
2. `boundaries.record`: verify retained input, worker, process and containment
   receipts. `boundaries.requirements`: load versioned public-task requirements.
3. `boundaries.compare`: per-requirement comparison with evidence references.
4. `candidates.boundary_assessment.evaluate`: score eligibility adapter.
   `scoring.score` applies the v2 70-point rubric and unchanged hard gates.

`factory-assessment-boundaries-v3` selects this path explicitly. It uses the same
`factory-serial-v1` budgets, plus one separately bounded 120-second boundary
inspection after the protocol's sole independent factory export. The report format is
`private-candidate-diagnostic-v4`; observation and comparison versions and the
expanded requirement digest are bound in its assignment. The independent verifier
reconstructs these comparisons from retained receipts. No old report is upgraded.
Historical protocols are available through their checkpoints. The closed matched
pilot remains at `bb52be4` on `experiment/matched-pilot-v2-01`; its v1 observations
and v2 assessment outcomes are not upgraded. The unchanged v1 comparator can read
both observation versions, but current receipt verification accepts only the
current worker/manifest. Full historical verification uses the original checkout.
V3 corrects representation-dependent boundary coverage; scoring remains the v2
70-point rubric, with no reproducibility points or changed physical thresholds.

## Supported representation and coverage

The supported subject is the six open planar faces of a finite, axis-aligned
**root CSG domain established as one box**. Coordinates are in cm in the root
frame; outward directions and tangential face extents are explicit. X/Y/Z planes
and axis-aligned general planes, including signed/scaled equations, are supported.
The geometric selector uses the whole domain extent and axis/side, never names,
IDs or the reference's cell organization.

The worker reads OpenMC's region objects. It divides axes at declared plane
coordinates. For each open arrangement cell, a loaded region's conservative
`bounding_box` can establish disjointness; finite bounds are rounded outward.
An overlapping box NEVER proves occupancy. NaN bounds provide no pruning.
Remaining halfspaces are reduced using exact Boolean identities: constants,
flattening, complementary literals and absorption. Unresolved non-plane signs
remain independent. Occupancy must be constant over all remaining assignments,
and the occupied arrangement cells must form a bounded complete box. Thus interior
holes cannot be hidden by enclosing boxes. This is sufficient symbolic reasoning,
not sampling, a second OpenMC parser, or a general CSG solver.

Only residual expressions needing enumeration encounter the unchanged 16-atom
guard. A reduced literal/conjunction/disjunction has an exact truth-set result
without enumeration (e.g. a consistent 25-literal conjunction is satisfiable,
but does not establish universal occupancy). Limits are 65,536 arrangement cells,
65,536 cumulative enumerated assignments, and 4,000,000 measured work units across
preparation, reduction, evaluation and participation. Unlike v1's estimated
state-times-node guard, work units count instrumented node/term visits and cell
checks; they do not count every Python operation. The unchanged 120-second process
deadline also bounds parsing, OpenMC bounds calculation and collection operations.

Coverage separately records the estimated unreduced global assignment count,
actual arrangement visits, enumerated assignments, reduction/query work and
bound-based eliminations. `max_residual_atoms` includes syntactically solved
queries, not just those requiring enumeration. Limit details give the actual
guard, configured bound, attempted amount, phase and exploration status. Worker
elapsed time is diagnostic; controller elapsed includes setup/cleanup. A limit
leaves the affected obligation indeterminate. A completed domain proof is retained
if a later face-participation limit prevents face observations.

Face participation is checked separately after domain occupancy. Bounding-box
containment does not prove face behavior or absence of overlaps. Face contributors
are conservative possible root-cell contributors. A proved
empty root cell cannot supply a face. Coincident surfaces with the same effective
property are equivalent for that property; conflicting values remain ambiguous.
Cells filled by a universe/lattice or carrying a transform that may meet a face
make the affected behavior unresolved. An unrelated filled/transformed region
strictly inside the outer box does not invalidate other external-face properties.

The scope excludes face edges/corners, periodic coupling, curved external faces,
general hierarchy interpretation, source convergence, materials, overlap/gap
certification, and global geometry validity. No point, segment, plot or
geometry-debug tool was added. The old finite geometry checks remain separate.
Nonexternal nontransmission behavior not qualified here remains an explicit
score-eligibility limitation, preserving the previous task restriction without
claiming new semantic coverage. Its presence does not erase external-face verdicts.

## Effective properties and provenance

Each observation retains the artifact digest, observer/OpenMC versions, surface
geometry, boundary type, effective albedo when applicable, domain participation,
coverage/limitations, and surface/cell references for traversal and evidence.
IDs are not physical matching criteria. XML attribute presence is recorded
separately from loaded values. Original Python arguments are not reconstructed.

The authority is the pinned implementation:
[Surface loading/export](https://github.com/openmc-dev/openmc/blob/v0.15.3/openmc/surface.py)
and [native boundary behavior](https://github.com/openmc-dev/openmc/blob/v0.15.3/src/boundary_condition.cpp).
Reflection, white and periodic boundaries have an albedo scalar; vacuum and
transmission do not. Periodic pairing remains unsupported even when its scalar
can be observed. Export can omit a near-unity albedo and loading then yields 1.
The observer describes those retrieved XML semantics, not lost author intent.

## Requirements and verdicts

`boundary_requirements_v1.json` contains literal public-task transcriptions for
the five box tasks, source paths/hashes/clauses, domain extents and expected
boundary properties. The cylinder is explicitly outside this protocol. A small
expansion produces one record per face/property, for example:

```json
{
  "id": "outer.0.lower.effective_albedo",
  "selector": {"kind": "root_box_face", "axis": 0, "side": "lower",
    "domain_bounds_cm": [[-0.63,0.63],[-0.63,0.63],[-0.63,0.63]],
    "location_comparison": {"kind": "exact"}},
  "property": "effective_albedo", "expected": 1.0,
  "comparison": {"kind": "exact"},
  "observations_needed": ["established_root_domain", "participating_face", "effective_effective_albedo"]
}
```

The enclosing requirement package supplies the public source for every record;
each verdict repeats it. Current task rules are exact on loaded finite values,
including normalized plane positions. The same comparator supports a declared
absolute tolerance; no hidden albedo tolerance exists. Qualification also compares
white boundaries with expected albedo 0.25, rather than hard-coding reflection/1.

| Meaning | Treatment |
|---|---|
| `conformity_established` | Evidence establishes this specific supported requirement |
| `nonconforming` | A matched, observed property violates its declared rule |
| `no_defect_observed` | Negative evidence within finite coverage; not conformity and never sufficient for a passing requirement |
| `indeterminate` | Required observations/interpretation are unavailable; cause retained |

This symbolic boundary capability ordinarily yields the first, second or fourth
verdict. It does not manufacture a `no_defect_observed` assertion for uninspected
physics. That weaker meaning still describes the separate finite geometry gate.
Missing fields/faces, unmatched domain location, ambiguous coincident values,
unsupported filled faces, unresolved domain shape and exhausted coverage have
distinct causes. Execution interruption or missing receipts is an evidence/runtime
problem, not a demonstrated model violation. Unknown required checks leave the
unchanged rubric unscored; known mismatches remain visible beside those unknowns.

The current protocol compares the sole final artifact directly with task requirements. No
repeat-export stability check contributes to eligibility or score.

## Qualification and remaining blind spots

| Counterexample/control | General property | Missing capability addressed |
|---|---|---|
| Albedo 0.5 and other albedos | Effective interaction behavior | Loaded albedo observation and explicit comparison |
| Empty-cell reflective decoy | A declaration must participate in the domain | Root-domain/face participation evidence |
| Renamed/reordered IDs, scaled plane, split cell | Physical equivalence within scope | Matching independent of representation identity |
| Coincident conflicting surfaces, transformed fill | Limits must remain visible | Per-property/per-face indeterminate causes |
| Localized overlap from audit | Geometry validity beyond finite probes | Still missing; deliberately not addressed by this slice |

The qualifications use actual factory-produced, retrieved XML and fresh workers.
They include default/explicit normalized values, wrong types, varied albedos,
periodic limitations, curved domains and an unrelated internal transformation.
These controls search for shared blind spots but do not prove observer completeness.
The frozen references remain internally qualified only; no new reference review,
statistical calibration, harness-benefit claim or model campaign is implied.

The bounded correction qualification and unchanged-artifact reviews remain in the
private research evidence, outside this source snapshot. They are boundary-only
reviews, not reassessments of pilot scores or evidence of A/B improvement.
The portable public tests do not rerun these native controls.
