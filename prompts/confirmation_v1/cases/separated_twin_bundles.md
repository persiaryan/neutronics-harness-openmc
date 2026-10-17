# Separated twin finite bundles, version 1

All lengths are in cm. These are synthetic models, not experimental systems.
Use the listed nuclides and relative atom amounts directly; no natural-element
substitutions. Enrichment means the uranium atom fraction. Unless explicitly
overridden below, every material and every material-filled cell is at 293.6 K.

Materials, densities and relative atom amounts:

- Fuel A: density 10.4 g/cm3; U235:0.02, U238:0.98, O16:2.0.
- Fuel B: density 10.4 g/cm3; U235:0.04, U238:0.96, O16:2.0.
- Zirconium: density 6.55 g/cm3; Zr90:0.5145, Zr91:0.1122,
  Zr92:0.1715, Zr94:0.1738, Zr96:0.0280.
- Water: density 0.997 g/cm3; H1:2.0, O16:1.0.

Apply c_H_in_H2O to all hydrogen in Water. A void contains no
material. No components or materials beyond those specified below are present.

Each ordinary pin has fuel at radius r<0.4096, a void gap at
0.4096<r<0.4180, and Zirconium at 0.4180<r<0.4750, measured from its own axis.
All pin axes are parallel to z. There are no end caps, plena or grids.

There are two 2x2 pin bundles centered at x=-3.2 and x=+3.2, y=0.
For a bundle with center c, its four pin axes are at
(x,y)=(c-0.65,-0.65),(c+0.65,-0.65),(c-0.65,+0.65),(c+0.65,+0.65).
All four left-bundle pins use Fuel A; all four right-bundle pins use Fuel B.
All pins span z in [-18,18].
The outer domain is x in [-7,7], y in [-5,5], z in [-25,25].
Water fills all remaining space, including the region separating the bundles
and the axial end regions. There are no bundle wrappers or dividing walls.
All six outer faces are vacuum.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied
ENDF/B-VIII.1 data. Use nearest-temperature lookup with a 1 K tolerance and
a settings default temperature of 293.6 K.
Set 10,000 particles per generation, two generations per batch, 400 batches,
100 inactive batches, and seed 1.
The initial spatial source is uniform over the box with lower-left
(-4.4,-1.2,-18) and upper-right (4.4,1.2,18), rejecting points outside
fissionable material. Directions are isotropic and energies follow a Watt
spectrum with a=988000 eV and b=2.249e-6 /eV.
Use a regular entropy mesh with dimensions (16,5,12), lower-left
(-4.4,-1.2,-18) and upper-right (4.4,1.2,18).
Request the final statepoint at batch 400. All internal interfaces are
transmissive. No depletion, thermal feedback, extra tallies, plots, unspecified
components, or tuning toward criticality. Representation, helper names and
cell decomposition are your choice; preserve the stated material partition.
