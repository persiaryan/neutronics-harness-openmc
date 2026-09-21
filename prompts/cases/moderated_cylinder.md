# Finite homogenized fuel-moderator cylinder, version 1

This is a specified synthetic mixture and geometry, not an experimental system.
All lengths are in cm. All materials are at 293.6 K. Use the listed
isotopes and relative atom amounts without natural-element substitutions.
U235 enrichment is the uranium atom fraction, not a mass fraction. All water
hydrogen uses c_H_in_H2O thermal scattering.

The homogeneous fuel-moderator mixture has density 3.0 g/cm3, with relative
atom amounts U235:0.04, U238:0.96, O16:12.0, H1:20.0. These amounts represent
UO2 plus ten H2O formula units; use them directly as atom amounts at the stated
mixture density, without recomputing the density. Apply c_H_in_H2O to its hydrogen.
The surrounding light water has density 0.997 g/cm3 and atom amounts H1:2.0,
O16:1.0, also with c_H_in_H2O. There are no other materials.

The mixture fills a right circular cylinder centered on the z axis, radius
12.0, z from -25.0 to +25.0. The complete outer domain is another coaxial
cylinder, radius 20.0, z from -33.0 to +33.0. Water fills all space inside the
outer cylinder and outside the mixture, including the axial end regions.
The outer cylindrical wall and both outer end planes are vacuum boundaries.
Mixture/water interfaces are transmissive. There is no vessel wall or cladding.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied ENDF/B-VIII.1
data and nearest-temperature lookup with a 1 K tolerance. Use 10,000 particles
per generation, two generations per batch, 400 batches, 100 inactive batches,
and seed 1. The initial source is uniform in the box with lower-left (-12,-12,-25)
and upper-right (12,12,25), rejecting points outside fissionable material. Directions
are isotropic; energies follow a Watt spectrum with a=988000 eV and
b=2.249e-6 /eV. Use a regular entropy mesh of dimensions (12,12,10) over that same
box. Request the final statepoint at batch 400. No depletion, thermal feedback,
extra tallies, plots, unspecified components or tuning toward criticality.
