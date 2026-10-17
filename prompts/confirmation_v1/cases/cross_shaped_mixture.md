# Cross-shaped fuel-moderator body, version 1

All lengths are in cm. These are synthetic models, not experimental systems.
Use the listed nuclides and relative atom amounts directly; no natural-element
substitutions. Enrichment means the uranium atom fraction. Unless explicitly
overridden below, every material and every material-filled cell is at 293.6 K.

Materials, densities and relative atom amounts:

- Mixture: density 3.0 g/cm3; U235:0.04, U238:0.96, O16:12.0, H1:20.0.
  This is a prescribed UO2/water mixture; do not recompute its density.
- Water: density 0.997 g/cm3; H1:2.0, O16:1.0.

Apply c_H_in_H2O to all hydrogen in Water and Mixture. A void contains no
material. No components or materials beyond those specified below are present.

Mixture occupies the union of two rectangular prisms:
- x in [-5,5], y in [-1,1], z in [-15,15];
- x in [-1,1], y in [-5,5], z in [-15,15].
Their common central volume is one physical Mixture volume, not two
superposed material regions. There is no internal wall at their junction.
The outer domain is x,y in [-9,9], z in [-22,22].
Water fills the rest of that domain. All six outer faces are vacuum.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied
ENDF/B-VIII.1 data. Use nearest-temperature lookup with a 1 K tolerance and
a settings default temperature of 293.6 K.
Set 10,000 particles per generation, two generations per batch, 400 batches,
100 inactive batches, and seed 1.
The initial spatial source is uniform over the box with lower-left
(-5,-5,-15) and upper-right (5,5,15), rejecting points outside
fissionable material. Directions are isotropic and energies follow a Watt
spectrum with a=988000 eV and b=2.249e-6 /eV.
Use a regular entropy mesh with dimensions (10,10,10), lower-left
(-5,-5,-15) and upper-right (5,5,15).
Request the final statepoint at batch 400. All internal interfaces are
transmissive. No depletion, thermal feedback, extra tallies, plots, unspecified
components, or tuning toward criticality. Representation, helper names and
cell decomposition are your choice; preserve the stated material partition.
