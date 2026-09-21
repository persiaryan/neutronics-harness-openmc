# Two-composition finite 5x5 lattice, version 1

This is a synthetic assembly construction task.
All lengths are in cm. All materials are at 293.6 K. Use the listed
isotopes and relative atom amounts without natural-element substitutions.
U235 enrichment is the uranium atom fraction, not a mass fraction. All water
hydrogen uses c_H_in_H2O thermal scattering.

Fuel A has density 10.4 g/cm3 and atom amounts U235:0.02, U238:0.98, O16:2.0.
Fuel B has density 10.4 g/cm3 and atom amounts U235:0.04, U238:0.96, O16:2.0.
Zirconium has density 6.55 g/cm3 and relative atom amounts Zr90:0.5145,
Zr91:0.1122, Zr92:0.1715, Zr94:0.1738, Zr96:0.0280. Light water has density
0.997 g/cm3 and atom amounts H1:2.0, O16:1.0.

There are 25 pins on a 5x5 square lattice of pitch 1.26. Centers are
x=(column-2)*1.26 and y=(2-row)*1.26 for zero-based indices. The active box
is x,y in [-3.15,+3.15], z in [-25,+25]. The following map assigns fuel
composition; rows run from +y to -y and columns from -x to +x:

```
BBBBB
BAAAB
BAAAB
BAAAB
BBBBB
```

There are no guide tubes. The outer box is x,y in [-10.15,+10.15] and
z in [-33,+33].
Fuel pins have fuel radius 0.4096, a void gap from radius 0.4096 to 0.4180,
and zirconium cladding from radius 0.4180 to 0.4750. Each pin's remaining
lattice-position area is water. Every cylindrical interface is transmissive.
Pins terminate at the active axial ends; no end caps, plena, grids or wrapper
are present. Water fills the entire outer domain outside the active box.
All six outer plane faces are vacuum, and every internal plane is transmissive.

Use OpenMC 0.15.3 continuous-energy eigenvalue mode with the supplied ENDF/B-VIII.1
data and nearest-temperature lookup with a 1 K tolerance. Use 10,000 particles
per generation, two generations per batch, 400 batches, 100 inactive batches,
and seed 1. The initial source is uniform in the box with lower-left (-3.15,-3.15,-25)
and upper-right (3.15,3.15,25), rejecting points outside fissionable material. Directions
are isotropic; energies follow a Watt spectrum with a=988000 eV and
b=2.249e-6 /eV. Use a regular entropy mesh of dimensions (5,5,10) over that same
box. Request the final statepoint at batch 400. No depletion, thermal feedback,
extra tallies, plots, unspecified components or tuning toward criticality.
