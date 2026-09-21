Create a continuous-energy eigenvalue model of this finite three-dimensional
system. The requested observable is the combined k-effective estimator and its
one-standard-deviation Monte Carlo uncertainty, obtained by the later transport
calculation. Include the source-entropy mesh specified below.

All lengths are in cm. The origin is at the center of the active lattice.
All materials are at 293.6 K. Use nearest-temperature lookup with a 1 K
tolerance. Use only the isotopes listed below.

Materials, with relative atom amounts:

| Material | Density (g/cm3) | Relative atom amounts |
|---|---:|---|
| UO2 fuel | 10.4 | U235: 0.04, U238: 0.96, O16: 2.0 |
| Zirconium | 6.55 | Zr90: 0.5145, Zr91: 0.1122, Zr92: 0.1715, Zr94: 0.1738, Zr96: 0.0280 |
| Unborated light water | 0.997 | H1: 2.0, O16: 1.0 |

The U235 fraction is 4% of uranium atoms, not mass. Apply `c_H_in_H2O`
thermal scattering to hydrogen in all water. Fuel-to-cladding gaps are void.

The active lattice is 7 by 7 with pitch 1.26 along x and y. It occupies
x and y from -4.41 to +4.41, and z from -30 to +30. For zero-based row and
column indices, position centers are x = (column - 3) * 1.26 and
y = (3 - row) * 1.26. The first row is at the largest y coordinate.

There are 45 fuel pins and four water-filled guide tubes. Guide tubes replace
fuel pins at (row, column) = (1,1), (1,5), (5,1), (5,5), equivalently
at (x,y) = (+/-2.52, +/-2.52). This top-down map uses F for a fuel pin and G
for a guide tube:

FFFFFFF
FGFFFGF
FFFFFFF
FFFFFFF
FFFFFFF
FGFFFGF
FFFFFFF

Each fuel pin consists of concentric cylinders parallel to z:

- Fuel radius: 0.4096.
- Void gap: radius 0.4096 to 0.4180.
- Zirconium cladding: radius 0.4180 to 0.4750.
- The remainder of the lattice position is water.

Each guide tube consists of concentric cylinders parallel to z:

- Water bore radius: 0.5000.
- Zirconium wall: radius 0.5000 to 0.5600.
- The remainder of the lattice position is water.

All pins and guide tubes terminate at z = +/-30. There are no end caps,
plena, grids, assembly wrapper, control rods, boron, or homogenized components.
Outside the active lattice, fill the enclosing rectangular box with water:
x and y from -12.41 to +12.41, and z from -40 to +40. This gives 8 cm of
lateral water and 10 cm of axial water. All six outer faces are vacuum
boundaries. Internal surfaces are transmissive. There are no reflective or
periodic boundaries.

Sampling settings:

- Eigenvalue calculation; 10,000 particles per generation.
- Two generations per batch; 300 batches; 100 inactive batches.
- Random seed: 1.
- Initial spatial source: uniform in the active box, restricted to fissionable
  material by rejection sampling.
- Initial directions: isotropic.
- Initial energy: Watt distribution with a = 988,000 eV and b = 2.249e-6 /eV.
- Shannon entropy mesh: 7 by 7 by 12, spanning the active box.
- Save a statepoint at batch 300 with the eigenvalue and source histories.

No depletion, thermal feedback, photon transport, heating tallies, or adjustment
toward criticality is requested.
