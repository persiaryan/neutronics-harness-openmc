# Frozen pilot scoring profile, version 2

The owner selected six required hard gates and a weighted diagnostic score. The
unchanged public tasks request k-effective only. Geometry 20, materials 15,
physics/settings 10, k-effective 15, statistical quality 5, engineering consistency
5 sum to **70 applicable points**. Execution evidence is mandatory, outside the score. Report
`100 * earned_points / 70`. Flux/spectrum 10, reaction-rate/power 10 and other
observables 5 are N/A, with no automatic credit. These weights are research design
choices reflecting the owner's priorities, not empirically established constants.

Required gates: model builds; native OpenMC completes; no detected invalid or
overlapping geometry; required nuclear data available; valid finite statepoint;
required observables present. A demonstrated model-caused gate failure scores zero.
Infrastructure/evaluator failures or insufficient evidence remain unscored. A
candidate requesting isotopes outside the specified task is a candidate defect;
unavailable evaluator-supplied data is infrastructure failure. Finite probes and
successful tracking cannot prove that arbitrary geometry has no overlap everywhere.

Each category averages its named boolean checks equally. Each named check requires
all of its applicable constituent assertions; thousands of water probes cannot
dilute a missing fuel region. `scoring.json` freezes the exact check inventory:

| Category | Operational checks |
|---|---|
| Geometry | Radial/axial interfaces; active extent and material map; domain samples and outer extent; supported effective boundary requirements (with explicit indeterminate eligibility). Cylinder interface probes are partitioned into radial and axial assertions for the first two checks; lattice axial-end/map probes serve the second. |
| Materials | Required isotope compositions/roles and no forced isotropic scattering; mass densities; S(alpha,beta) assignments; material and effective cell temperatures. Equivalent IDs and units are accepted. |
| Physics/settings | Eigenvalue, continuous-energy and prescribed temperature treatment; exact public particle/batch/inactive/generation/seed budget; prescribed source; entropy mesh and final statepoint. Unsupported influential options remain unassessed. |
| k-effective | Entire approximate 95% interval of candidate minus reference lies within +/-150 delta-k pcm. Inconclusive agreement earns no agreement credit; report its interval and status separately. |
| Statistics | Candidate reported standard deviation <=51.961524 pcm; absolute active half-history entropy drift <=0.02 bits. These are precision and diagnostic screens, not convergence proofs. |
| Engineering consistency | Native global leakage estimate finite and within [0,1]; leakage equals zero for the fully reflective pin or is positive for these finite vacuum cases. No restriction that k must be near or below one. This narrow category does not claim power or neutron-balance verification. |

Missing evidence makes the full score unavailable; it does not silently earn or
lose partial credit. Known defects can still be reported individually. A separate
strict-correctness flag requires all gates and checks, so a high weighted score
cannot certify a physically wrong model. The calculator consumes trusted private
assessment records, never builder claims. Independent candidate export, inspection and transport are implemented;
builder observations cannot determine these scores. The cylinder remains
unscored under the current boundary protocol even when it is valid OpenMC.

For independent candidate/reference estimates, `delta=100000*(kc-kr)` and
`sigma=100000*sqrt(sc^2+sr^2)`. Agreement requires
`abs(delta)+1.96*sigma <=150`; resolved discrepancy requires
`abs(delta)-1.96*sigma >150`; otherwise it is inconclusive. Combining independent
standard uncertainties in quadrature follows [NIST TN1297](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-5-combined-standard-uncertainty).
The interval assumes approximate normality and excludes shared data/model bias
and source-convergence bias. Delta-k pcm is not delta-reactivity pcm.

The 150 pcm margin is a pilot reproduction criterion, not a safety limit. The
reference mean sigma target is 30 pcm (one fifth of that margin). Three equal
precision primary seeds give a corresponding single-run target `sqrt(3)*30` pcm.
Primary reference pairs must have |z|<=3. Fixed longer-inactive and point-source
controls must demonstrate equivalence within the same margin. The 0.02-bit entropy
screen is a preregistered pilot diagnostic; [OpenMC's convergence guidance](https://docs.openmc.org/en/stable/methods/eigenvalue.html)
explains why source convergence needs attention beyond k-effective. Retain plots,
all failures and sensitivity intervals. Do not tune a failed reference to obtain
eligibility under this version.

Task aggregation uses equal case weights, with per-case and partition results
also reported. Category weights do not establish task importance. Infrastructure
failures are separately counted and coverage reported; do not quietly drop them
and present the remaining mean as a complete suite score. Repeated matched builder
trials, uncertainty on aggregate outcomes, cost and tool use belong to the future
experiment. Development cases have already informed design; held-out builder
outcomes must not inform harness development before the declared evaluation.

These rules precede S11 transport, but follow exploratory 7x7 results and S10 pin
qualification. They cannot support retrospective causal claims for those trials.
Reference preparation is private. Grading remains disabled pending owner review.

V2 removes both traceability/repeat-export scored checks and the second export.
Frozen reference packages and historical 75-point scores are unchanged. Use
checkpoint/pre-single-export-assessment-v2 to verify v1 reports; v2 refuses them.
