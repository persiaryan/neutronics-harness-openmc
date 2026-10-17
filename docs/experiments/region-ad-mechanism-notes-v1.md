# Preliminary source-audit examples from the A/D pilot

Status: explanatory notes during the frozen development pilot. The primary
verdicts below come from independent retained-evidence review. Mechanism labels
are **assistant proposals pending human review**, not confirmed secondary
endpoint annotations and not evidence of an A/D treatment effect.

| Assignment | Setup/arm | Primary protocol result | Source-audit proposal |
|---|---|---|---|
| 004 | Sol/A, two-composition task | Success | In-place region accumulation appears safe in this construction because the needed complement was computed earlier |
| 005 | Luna/A, two-composition task | Geometry failure | Damaging shared-region mutation followed by a late complement |
| 006 | Luna/A, two-composition task | Geometry failure | A different error: complement of cladding annuli rather than full pin envelopes |
| 010 | Sol/A, axially zoned task | Geometry failure | Proposed damaging shared-region mutation and late complement |
| 016 | Luna/D, two-composition task | Geometry failure | The annulus-complement defect also occurs with D |

These examples illustrate the endpoint definition frozen in
[the scientific protocol](../../experiments/region_ad_protocol.json). They are
selected explanatory cases, not a representative sample or a comparative effect
estimate.

## 004: an operator is not a defect verdict

The source aliases the active-box region and narrows it with in-place
intersection while constructing inter-pin water. However, the exterior-water
complement was already constructed before that mutation, and the original box
region is not later reused in its original form.

A separate small OpenMC 0.15.3 control confirms the relevant semantics: an
Intersection alias changes the original object; a complement constructed before
the append remains unchanged; a complement constructed after the append reflects
the changed expression. All four assertions passed, without nuclear data,
candidate execution on the host or neutron transport.

This does not prove all uses of early complements are safe: nested shared
children and later edits still require review. It explains why counting every
alias or `&=` as a failure would misclassify this example.

## 005: the targeted damaging sequence

The active-water accumulator aliases the active box. In-place exclusions modify
that same Intersection. The exterior-water cell is subsequently defined using
the complement of the now-reduced region. Its water domain therefore extends
into pin interiors that should retain their own materials.

Independent all-matching-cell inspection recorded 3003 overlap observations
within its finite probe set. The geometry hard gate failed, and native transport
was not reached. The zero diagnostic score is a model-failure verdict, not a
calculated zero eigenvalue.

The source sequence and independent geometric observation support the proposed
mechanism attribution. Human review of the bound source and artifacts remains
pending.

## 006: another geometric defect

This source builds the union from cladding annuli, then complements that union
to define active water. Removing annuli leaves fuel and gap interiors in the
water domain, creating overlaps. The accumulation uses new Boolean expressions;
this construction does not demonstrate the targeted in-place shared-region
mutation.

It therefore illustrates why complete protocol success remains primary:
eliminating one programming mechanism does not eliminate other geometric errors.

## 010 and 016: different limits of the intervention

In 010, the moderator accumulator aliases the active Intersection, changes it
in place, and a later outer-moderator complement uses that changed meaning.
Independent inspection recorded 6589 overlap observations. This is another
proposed instance of the targeted mechanism, on the axially zoned task.

In 016, D was present, yet the source complemented cladding annuli rather than
full pin envelopes, as in 006. Its region combinations use new Boolean
expressions rather than the targeted shared in-place mutation. The geometry
hard gate failed before transport. This retained failure illustrates a limit
of this particular procedural assistance; it is not silently replaced or
classified as infrastructure trouble.

Neither example alone estimates D's effectiveness. The complete assigned
comparison and pending mechanism review remain necessary.


In 027 (Luna/A, axially zoned task), the same alias → in-place narrowing → late
complement sequence recurs. Independent retained-evidence review confirms a
model-attributed export-inspection failure, with 6589 overlap observations in
the finite probe set and no transport. Its mechanism attribution remains an
assistant proposal pending human review.

The evaluator detects geometric consequences and retains attributable evidence.
The specific Python alias/mutation explanation comes from source review; it is
not an automatic root-cause diagnosis supplied by the geometric evaluator. This
separation is part of the evidence chain, rather than a claim that the observer
recognizes arbitrary programming errors.

## Generic control of shared children

A second isolated OpenMC 0.15.3 control tested four assertions, all passed:
an Intersection alias preserves identity; a binary intersection constructed
before a later append retains its membership; a cell directly referencing the
mutated region observes the change; a union containing that shared Intersection
as a child also observes the change.

This control is retained as `source-audit-controls/shared-child-timing-v1.*`.
It uses neither nuclear data nor transport and executes no candidate. It helps
interpret source timing and nesting; it does not change the frozen criteria,
grade submissions or establish general safety of nonmutating outer operators.

## 025: numerical agreement without complete task conformity

Luna/D's reflective-cell assignment 025 completed native transport and passed the
finite geometry/material checks, the declared k-effective equivalence comparison,
and the statistical and leakage checks. Its independently reconstructed score is
96.4286, but complete protocol success is false: temperature_tolerance was 10 K
(the default), whereas the public task requires 1 K. This is the only failed
settings check. The submitted settings omit an explicit temperature configuration.

The final-source geometry review proposes no targeted shared-region mutation.
This retained failure demonstrates the distinction between numerical agreement
and full task conformity. It does not establish a change in the realized physical
result from that tolerance discrepancy. The candidate is neither repaired nor
credited as a complete success, and D's procedure remains frozen.

## Evidence location and limits

The local study is `scratch/region-ad-pilot-36-v2`. It retains immutable final
sources, assessment reports, independent inspections and source hashes.
`annotations-draft.json` contains line/hash-bound proposals; its endpoint
statuses remain pending. The isolated semantic control is under
`source-audit-controls/complement-timing-v1.*`.

Raw sources, requests, transcripts, references and detailed private evidence are
not published by these notes. The pilot's final analysis, task coverage and
incident accounting must be read before drawing any comparative conclusion.
