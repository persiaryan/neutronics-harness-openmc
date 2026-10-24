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

## Coincident planes

The lower z face is duplicated with equal vacuum behavior or conflicting
transmission behavior. Both Boolean term orders are included. Equal effective
properties permit a boundary verdict; conflicting properties remain unknown.
No convenient boundary value is selected from the inventory. Native transport
selection is a separate observation and must never replace this conservative
rule without a separately qualified interpretation.

All source-domain controls, conformance rules and execution results are
documented with their implementation; none changes frozen campaign verdicts.
