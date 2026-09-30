"""Handwritten reproduction fixture for prompts/cases/reflective_pin_cell.md.

No reference results, private packages or host paths. The evaluator invokes this
factory in isolation and owns the single authoritative export.
"""
import openmc


def build_model():
    fuel = openmc.Material(name="UO2", temperature=293.6)
    fuel.set_density("g/cm3", 10.4)
    fuel.add_nuclide("U235", 0.04)
    fuel.add_nuclide("U238", 0.96)
    fuel.add_nuclide("O16", 2.0)
    clad = openmc.Material(name="zirconium", temperature=293.6)
    clad.set_density("g/cm3", 6.55)
    for name, amount in (("Zr90", .5145), ("Zr91", .1122), ("Zr92", .1715),
                         ("Zr94", .1738), ("Zr96", .0280)):
        clad.add_nuclide(name, amount)
    water = openmc.Material(name="light water", temperature=293.6)
    water.set_density("g/cm3", .997)
    water.add_nuclide("H1", 2.)
    water.add_nuclide("O16", 1.)
    water.add_s_alpha_beta("c_H_in_H2O")
    r1, r2, r3 = (openmc.ZCylinder(r=r) for r in (.4096, .4180, .4750))
    xm, xp = (openmc.XPlane(x0=x, boundary_type="reflective") for x in (-.63, .63))
    ym, yp = (openmc.YPlane(y0=y, boundary_type="reflective") for y in (-.63, .63))
    zm, zp = (openmc.ZPlane(z0=z, boundary_type="reflective") for z in (-.63, .63))
    box = +xm & -xp & +ym & -yp & +zm & -zp
    cells = [
        openmc.Cell(fill=fuel, region=box & -r1),
        openmc.Cell(region=box & +r1 & -r2),
        openmc.Cell(fill=clad, region=box & +r2 & -r3),
        openmc.Cell(fill=water, region=box & +r3),
    ]
    settings = openmc.Settings()
    settings.run_mode = "eigenvalue"
    settings.particles, settings.batches, settings.inactive = 10000, 400, 100
    settings.generations_per_batch, settings.seed = 2, 1
    settings.temperature = {"method": "nearest", "tolerance": 1.0, "default": 293.6}
    settings.source = openmc.IndependentSource(
        space=openmc.stats.Box((-.63, -.63, -.63), (.63, .63, .63)),
        angle=openmc.stats.Isotropic(),
        energy=openmc.stats.Watt(a=988000., b=2.249e-6),
        constraints={"fissionable": True})
    mesh = openmc.RegularMesh()
    mesh.dimension = (10, 10, 1)
    mesh.lower_left, mesh.upper_right = (-.63, -.63, -.63), (.63, .63, .63)
    settings.entropy_mesh = mesh
    settings.statepoint = {"batches": [400]}
    return openmc.Model(geometry=openmc.Geometry(cells),
                        materials=openmc.Materials([fuel, clad, water]), settings=settings)
