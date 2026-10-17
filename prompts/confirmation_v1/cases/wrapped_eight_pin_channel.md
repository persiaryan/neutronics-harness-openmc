# Wrapped eight-pin assembly with central channel, version 1

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

Use a 3x3 square grid with axis coordinates x,y in {-1.3,0,1.3}.
The eight noncentral positions contain Fuel B pins. At (0,0), replace the
ordinary pin by a water channel r<0.50 surrounded by a Zirconium tube
0.50<r<0.56; there is no fuel or void gap at this position.
All pins and the central tube span z in [-18,18].
A square Zirconium wrapper occupies the shell between the square
x,y in [-2.10,2.10] and the square x,y in [-2.22,2.22], over z in [-18,18].
It has no end caps. Water fills the inner square outside all pins and the
central tube, the region outside the wrapper, and both axial end regions.
The outer domain is x,y in [-6,6], z in [-25,25].
All six outer faces are vacuum.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied
ENDF/B-VIII.1 data. Use nearest-temperature lookup with a 1 K tolerance and
a settings default temperature of 293.6 K.
Set 10,000 particles per generation, two generations per batch, 400 batches,
100 inactive batches, and seed 1.
The initial spatial source is uniform over the box with lower-left
(-1.8,-1.8,-18) and upper-right (1.8,1.8,18), rejecting points outside
fissionable material. Directions are isotropic and energies follow a Watt
spectrum with a=988000 eV and b=2.249e-6 /eV.
Use a regular entropy mesh with dimensions (9,9,12), lower-left
(-1.8,-1.8,-18) and upper-right (1.8,1.8,18).
Request the final statepoint at batch 400. All internal interfaces are
transmissive. No depletion, thermal feedback, extra tallies, plots, unspecified
components, or tuning toward criticality. Representation, helper names and
cell decomposition are your choice; preserve the stated material partition.
