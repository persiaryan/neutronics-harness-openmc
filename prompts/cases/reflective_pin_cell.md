# Reflective UO2 pin cell, version 1

Construct a continuous-energy eigenvalue calculation. This is a fully specified
synthetic pin cell representing a repeating medium, not an experimental case.
All lengths are in cm and all materials are at 293.6 K.

Materials, density in g/cm3 and relative atom amounts:

| Material | Density | Nuclides and relative atom amounts |
|---|---:|---|
| UO2 | 10.4 | U235: 0.04; U238: 0.96; O16: 2.0 |
| Zirconium | 6.55 | Zr90: 0.5145; Zr91: 0.1122; Zr92: 0.1715; Zr94: 0.1738; Zr96: 0.0280 |
| Light water | 0.997 | H1: 2.0; O16: 1.0 |

Four percent enrichment means U235 atoms divided by all uranium atoms. Do not
substitute natural-element expansions. Apply c_H_in_H2O thermal scattering to
the hydrogen in water. There are no other materials.

The domain is the cube x,y,z in [-0.63,+0.63], centered on the origin. Its six
outer plane faces are reflective. A pin is centered at x=y=0, parallel to z,
and spans the full domain height. Its concentric cylindrical regions are:

- Fuel: radius less than 0.4096.
- Void gap: radii 0.4096 to 0.4180.
- Zirconium cladding: radii 0.4180 to 0.4750.
- Water: the rest of the cube outside radius 0.4750.

Every internal cylindrical interface is transmissive. There are no end caps,
plena, guide tubes, additional reflector regions or other components.

Use OpenMC 0.15.3, the supplied ENDF/B-VIII.1 data, and nearest-temperature lookup
with a 1 K tolerance. Set 10,000 particles per generation, two generations per
batch, 400 batches, 100 inactive batches and seed 1. Initialize a uniform spatial
source over the domain cube, rejecting points outside fissionable material,
with isotropic directions and a Watt energy distribution with a=988000 eV and
b=2.249e-6 /eV. Use a regular Shannon entropy mesh with dimensions (10,10,1),
lower-left (-0.63,-0.63,-0.63), upper-right (0.63,0.63,0.63). Request the final
statepoint at batch 400. No depletion, thermal feedback, extra tallies, plots or
adjustment toward criticality is requested.
