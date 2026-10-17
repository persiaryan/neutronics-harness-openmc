# Mixture block with three water channels, version 1

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

Start with a Mixture block x in [-5,5], y in [-4,4], z in [-15,15].
Three circular cylindrical channels, each radius 0.60 and parallel to z,
pass through the full block height, centered at (x,y)=(-3,0),(0,0),(3,0).
The channels contain Water instead of Mixture and have no tube walls.
The outer domain is x in [-9,9], y in [-8,8], z in [-22,22].
Water fills the channels and every part of the outer domain outside the
perforated block. There are no end plates. All six outer faces are vacuum.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied
ENDF/B-VIII.1 data. Use nearest-temperature lookup with a 1 K tolerance and
a settings default temperature of 293.6 K.
Set 10,000 particles per generation, two generations per batch, 400 batches,
100 inactive batches, and seed 1.
The initial spatial source is uniform over the box with lower-left
(-5,-4,-15) and upper-right (5,4,15), rejecting points outside
fissionable material. Directions are isotropic and energies follow a Watt
spectrum with a=988000 eV and b=2.249e-6 /eV.
Use a regular entropy mesh with dimensions (10,8,10), lower-left
(-5,-4,-15) and upper-right (5,4,15).
Request the final statepoint at batch 400. All internal interfaces are
transmissive. No depletion, thermal feedback, extra tallies, plots, unspecified
components, or tuning toward criticality. Representation, helper names and
cell decomposition are your choice; preserve the stated material partition.
