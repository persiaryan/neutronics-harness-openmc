# Offset finite plate bank, version 1

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

The outer domain is x in [-7,9], y in [-7,7], z in [-25,25].
Five rectangular plates have center coordinates x=-3,-1.5,0,1.5,3,
and each extends over y in [-4,4], z in [-18,18].
For a plate centered at c, Fuel B occupies |x-c|<0.25.
A void gap occupies 0.25<|x-c|<0.27 and Zirconium occupies
0.27<|x-c|<0.32, over exactly the same y,z extent.
Only the two large x-normal faces are clad: no side or axial caps are present.
Water fills every remaining part of the outer domain, including between plates
and beyond their side and axial ends. All six outer faces are vacuum.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied
ENDF/B-VIII.1 data. Use nearest-temperature lookup with a 1 K tolerance and
a settings default temperature of 293.6 K.
Set 10,000 particles per generation, two generations per batch, 400 batches,
100 inactive batches, and seed 1.
The initial spatial source is uniform over the box with lower-left
(-3.25,-4,-18) and upper-right (3.25,4,18), rejecting points outside
fissionable material. Directions are isotropic and energies follow a Watt
spectrum with a=988000 eV and b=2.249e-6 /eV.
Use a regular entropy mesh with dimensions (10,8,12), lower-left
(-3.25,-4,-18) and upper-right (3.25,4,18).
Request the final statepoint at batch 400. All internal interfaces are
transmissive. No depletion, thermal feedback, extra tallies, plots, unspecified
components, or tuning toward criticality. Representation, helper names and
cell decomposition are your choice; preserve the stated material partition.
