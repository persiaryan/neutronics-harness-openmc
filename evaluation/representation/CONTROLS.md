# Prospective evaluator controls

These are handwritten public synthetic models, not campaign candidates or
private reference constructors. Expected results follow the geometry below.
Native runs must retain XML, worker/process identity and containment/cleanup
receipts. Portable tests alone do not qualify OpenMC behavior.

## Independent geometric oracle

The domain D is (-4,4) x (-4,4) x (-3,3) cm. The active slab is -2<z<2.
Eight concentric pins have centers on {-0.7,0,0.7} squared except the origin;
radii are 0.2, 0.24 and 0.3 cm. The central channel has radii 0.2 and 0.3.
These disjoint cylinders lie strictly inside the square I of half-width 1.3.
The wrapper is E minus I, where E has half-width 1.4. Thus P is contained
in I, I in E, E in D. In the active slab the water identity is exactly

    D \ (P union (E \ I)) = (I \ P) union (D \ E).

Outside the active slab the whole domain is water. The compact complement,
complement of all individually excluded layers, and partitioned constructions
therefore define the same material field. Renumbering and declaration-order
changes preserve all references. This argument does not rely on a point grid.

Removing the lower water slab creates a positive-volume missing domain;
(-3,-3,-2.5) is an interior witness. Omitting its lower axial bound adds water
outside D, witnessed by (-3,-3,-3.5). Moving the x lower face to -4.25 changes
the domain despite unchanged IDs. A separate water box inside water creates
an overlap at (-3.25,-3.25,0); its union is still D, so the boundary observer
alone must not claim to certify nonoverlap. A separate all-cell probe detects it.
Subtracting that same interior box from water creates a positive-volume hole:
the enclosing bounding box stays unchanged, but the root domain is not a box.
Reversing conjunction terms and moving the compact complement before the outer
planes is a separate equivalence control, independent of declaration order.

## Coincident planes

The lower z face is duplicated with equal vacuum behavior or conflicting
transmission behavior. Both Boolean term orders are included. Equal effective
properties permit a boundary verdict; conflicting properties remain unknown.
No convenient boundary value is selected from the inventory. Native transport
selection is a separate observation and must never replace this conservative
rule without a separately qualified interpretation.

## Source oracle

The proposal is uniform in (-1,1) x (-0.9,0.9) squared. Two fuel slabs occupy
-0.8<x<-0.2 and 0.2<x<0.8, with -1<y,z<1, inside a water box of half-width 2.
Both fuel cells use the same uranium material. The accepted law is the proposal
conditioned on their union. Equal cell sets prove the same accepted support;
finite witnesses only refute an identity. Material labels in these synthetic
controls are literal: material 1 is uranium, 2 water, 3 zirconium. The production
comparator obtains labels from matched benchmark compositions, never names/IDs.

Fourteen source controls include explicit fissile rejection, both fuel cells,
the fuel material, redundant restrictions, complete renumbering, water selection,
omitted fuel, extra water, an unchanged ID reassigned to water, unsupported
universe constraints, additional unknown restrictions and duplicate fields.

The native sampling control uses 4,096 sites and seed 41. Equivalent supported
forms must produce identical retained position streams in this pinned runtime;
all sites must be in fuel and the left fraction between 0.35 and 0.65. This
wide diagnostic screen and finite stream agreement do not prove arbitrary law
equivalence. Negative controls must actually sample water or omit the right slab.

For coincident planes, a separate void fixed-source problem sends 20 histories
straight to the lower face. Equal vacuum behavior must produce leakage 1 with
zero reported uncertainty. Conflicting behavior may complete or produce the
specific native lost-particle diagnostic; unrelated crashes/timeouts fail the
control. The observed order dependence does not upgrade an unknown face verdict.

All qualification commands refuse existing output directories, retain failures,
make zero provider calls and never read or rescore campaign candidates.
