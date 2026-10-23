# INDC-USA-107 problem 1: reflective axial-slice variant, version 1

All lengths are in cm. Construct the computational variant specified here,
derived from mit-crpg/benchmarks, commit
ba41bee54320ada0b4ac39a0dd2ca3c1d090a450,
indc-usa-107/openmc/problem1. This is not a claim to reproduce an experimental
measurement or the original spectral-tally benchmark.

The original transverse geometry and material recipes are retained. Its
axially unbounded model is represented here by the explicitly prescribed
reflective slice z in [-1,1]. The temperature, initial-source constraints,
entropy mesh and run settings below are explicit harness requirements.

Materials, densities and relative atom amounts:
- Uranium metal: density 18.8 g/cm3; U235:0.98, U238:99.02.
  These are relative atom amounts (0.98 atom percent U235), not mass enrichment.
  There is no oxygen or other nuclide in this material.
- Water: density 1.0 g/cm3; H1:2.0, O16:1.0.
Apply c_H_in_H2O to all hydrogen in Water.
All materials and material-filled cells are at 293.6 K.

The outer domain is x,y in [-2.54,2.54], z in [-1,1].
A centered uranium-metal cylinder r<1.27, parallel to z, spans the full slice.
Water fills every remaining part of the outer domain outside this cylinder.
There is no cladding, void gap, axial reflector material or additional component.
All six outer faces are reflective with effective albedo 1.
All internal interfaces are transmissive.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied
ENDF/B-VIII.1 data. Use nearest-temperature lookup with a 1 K tolerance and
a settings default temperature of 293.6 K.
Set 10,000 particles per generation, two generations per batch, 400 batches,
100 inactive batches, and seed 1.
The initial spatial source is uniform over the box with lower-left
(-1.27,-1.27,-1) and upper-right (1.27,1.27,1), rejecting points outside
fissionable material. Directions are isotropic and energies follow a Watt
spectrum with a=988000 eV and b=2.249e-6 /eV.
Use a regular entropy mesh with dimensions (8,8,1), lower-left
(-2.54,-2.54,-1) and upper-right (2.54,2.54,1).
Request the final statepoint at batch 400. No depletion, thermal feedback,
extra tallies, plots, unspecified components or tuning toward criticality.
Representation, helper names and cell decomposition are your choice;
preserve the stated material partition.
