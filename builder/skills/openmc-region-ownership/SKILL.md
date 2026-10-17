---
name: openmc-region-ownership
description: Preserve reused OpenMC CSG regions when deriving other regions; use while constructing or revising shared intersections, unions, and their complements.
---

# Preserve reused OpenMC regions

Procedure version: openmc-region-ownership-v1. Applies to OpenMC 0.15.3.

Python assignment does not copy an OpenMC region. Intersections and unions are
mutable: `&=` on an Intersection and `|=` on a Union change the existing object.
Another variable, or a cell already referring to that object, sees that change.

When a region must retain its meaning for reuse, treat it and its shared
components as read-only. Derive new expressions with `&` or `|` rather than
mutating the reused object in place. For example:

```python
# Risk: derived also changes base when base is an Intersection.
derived = base
derived &= constraint
outside = domain & ~base

```

Instead, start from the original, unmodified base and construct a new expression:

```python
derived = base
derived = derived & constraint
outside = domain & ~base
```

Before finalizing geometry, follow aliases of regions reused in complements or
assigned to cells and check their later mutations, including shared children.
A new outer expression is not a deep copy of all its components.

In-place construction can be intentional when the object is not shared or
needed in its previous form; it is not automatically an error. Do not apply
`clone()` indiscriminately: it also clones surfaces and assigns new surface IDs.

This procedure preserves construction intent; it does not establish geometry
validity, specification conformity, or numerical correctness. Continue using
the declared construction/export workflow and retain its actual outcomes.
