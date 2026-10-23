# Stepped axial fuel-moderator stack, version 1

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

Mixture occupies three contiguous axial sections:
- z in [-20,-6]: x in [-4,4], y in [-3,3];
- z in [-6,6]: x in [-2,2], y in [-3,3];
- z in [6,20]: x in [-2,2], y in [-1.5,1.5].
The sections touch directly on their common footprint: no gaps, walls or caps.
At each axial level, Water fills the area outside that section.
The outer domain is x in [-8,8], y in [-7,7], z in [-26,26].
Water also fills both axial end regions. All six outer faces are vacuum.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied
ENDF/B-VIII.1 data. Use nearest-temperature lookup with a 1 K tolerance and
a settings default temperature of 293.6 K.
Set 10,000 particles per generation, two generations per batch, 400 batches,
100 inactive batches, and seed 1.
The initial spatial source is uniform over the box with lower-left
(-4,-3,-20) and upper-right (4,3,20), rejecting points outside
fissionable material. Directions are isotropic and energies follow a Watt
spectrum with a=988000 eV and b=2.249e-6 /eV.
Use a regular entropy mesh with dimensions (8,6,16), lower-left
(-4,-3,-20) and upper-right (4,3,20).
Request the final statepoint at batch 400. All internal interfaces are
transmissive. No depletion, thermal feedback, extra tallies, plots, unspecified
components, or tuning toward criticality. Representation, helper names and
cell decomposition are your choice; preserve the stated material partition.
