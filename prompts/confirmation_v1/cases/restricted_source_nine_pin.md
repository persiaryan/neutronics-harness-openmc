# Nine-pin assembly with a restricted initial source, version 1

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

Nine Fuel B pins form a 3x3 square grid with x,y in {-1.3,0,1.3}.
All pins span z in [-18,18].
The outer domain is x,y in [-6,6], z in [-24,24].
Water fills everything outside the pin envelopes, including both axial ends.
All six outer faces are vacuum.
The initial source and entropy mesh below have deliberately different extents:
use the restricted source box exactly, without expanding it to the assembly.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied
ENDF/B-VIII.1 data. Use nearest-temperature lookup with a 1 K tolerance and
a settings default temperature of 293.6 K.
Set 10,000 particles per generation, two generations per batch, 400 batches,
100 inactive batches, and seed 1.
The initial spatial source is uniform over the box with lower-left
(-0.1,-0.1,-5) and upper-right (0.1,0.1,5), rejecting points outside
fissionable material. Directions are isotropic and energies follow a Watt
spectrum with a=988000 eV and b=2.249e-6 /eV.
Use a regular entropy mesh with dimensions (6,6,12), lower-left
(-1.95,-1.95,-18) and upper-right (1.95,1.95,18).
Request the final statepoint at batch 400. All internal interfaces are
transmissive. No depletion, thermal feedback, extra tallies, plots, unspecified
components, or tuning toward criticality. Representation, helper names and
cell decomposition are your choice; preserve the stated material partition.
