# Staggered seven-pin cluster, version 1

All lengths are in cm. These are synthetic models, not experimental systems.
Use the listed nuclides and relative atom amounts directly; no natural-element
substitutions. Enrichment means the uranium atom fraction. Unless explicitly
overridden below, every material and every material-filled cell is at 293.6 K.

Materials, densities and relative atom amounts:

- Fuel B: density 10.4 g/cm3; U235:0.04, U238:0.96, O16:2.0.
- Zirconium: density 6.55 g/cm3; Zr90:0.5145, Zr91:0.1122,
  Zr92:0.1715, Zr94:0.1738, Zr96:0.0280.
- Water: density 0.997 g/cm3; H1:2.0, O16:1.0.

Apply c_H_in_H2O to all hydrogen in Water. A void contains no
material. No components or materials beyond those specified below are present.

Each ordinary pin has fuel at radius r<0.4096, a void gap at
0.4096<r<0.4180, and Zirconium at 0.4180<r<0.4750, measured from its own axis.
All pin axes are parallel to z. There are no end caps, plena or grids.

There are seven Fuel B pins at these exact (x,y) coordinates:
(0,0), (1.4,0), (-1.4,0), (0.7,1.2), (-0.7,1.2),
(0.7,-1.2), (-0.7,-1.2). These coordinates are authoritative; do not replace
1.2 by an exact triangular-lattice height.
Each pin spans z in [-18,18]. The outer domain is
x in [-6,6], y in [-5,5], z in [-24,24].
Water fills everything inside the outer domain outside the complete pin
envelopes, including beyond their axial ends. All six outer faces are vacuum.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied
ENDF/B-VIII.1 data. Use nearest-temperature lookup with a 1 K tolerance and
a settings default temperature of 293.6 K.
Set 10,000 particles per generation, two generations per batch, 400 batches,
100 inactive batches, and seed 1.
The initial spatial source is uniform over the box with lower-left
(-1.9,-1.7,-18) and upper-right (1.9,1.7,18), rejecting points outside
fissionable material. Directions are isotropic and energies follow a Watt
spectrum with a=988000 eV and b=2.249e-6 /eV.
Use a regular entropy mesh with dimensions (8,8,12), lower-left
(-1.9,-1.7,-18) and upper-right (1.9,1.7,18).
Request the final statepoint at batch 400. All internal interfaces are
transmissive. No depletion, thermal feedback, extra tallies, plots, unspecified
components, or tuning toward criticality. Representation, helper names and
cell decomposition are your choice; preserve the stated material partition.
