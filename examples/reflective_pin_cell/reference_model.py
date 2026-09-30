"""Separate public-specification transcription for the demonstration reference.

This is a computational reference, not an experimental benchmark. No historical
reference code or result is used. A composite box bounds flat annular cells, within the existing observer
coverage. Sampling is stronger and uses a separate seed.
"""
import openmc


def build_model():
    # Literal composition from the public specification, not the evaluator.
    materials = []
    for name, density, atoms in (
        ("fuel", 10.4, {"U235": .04, "U238": .96, "O16": 2.}),
        ("clad", 6.55, {"Zr90": .5145, "Zr91": .1122, "Zr92": .1715, "Zr94": .1738, "Zr96": .028}),
        ("moderator", .997, {"H1": 2., "O16": 1.}),
    ):
        m = openmc.Material(name=name, temperature=293.6)
        m.set_density("g/cm3", density)
        for nuclide, fraction in atoms.items():
            m.add_nuclide(nuclide, fraction, "ao")
        materials.append(m)
    materials[2].add_s_alpha_beta("c_H_in_H2O")
    a = openmc.ZCylinder(r=.4096)
    b = openmc.ZCylinder(r=.418)
    c = openmc.ZCylinder(r=.475)
    bounds = openmc.model.RectangularParallelepiped(
        -.63, .63, -.63, .63, -.63, .63, boundary_type="reflective")
    geometry = openmc.Geometry([
        openmc.Cell(fill=materials[0], region=-a & -bounds),
        openmc.Cell(region=+a & -b & -bounds),
        openmc.Cell(fill=materials[1], region=+b & -c & -bounds),
        openmc.Cell(fill=materials[2], region=+c & -bounds)])
    s = openmc.Settings()
    s.run_mode = "eigenvalue"
    s.particles = 25000
    s.batches = 800
    s.inactive = 200
    s.generations_per_batch = 2
    s.seed = 19
    s.temperature = dict(default=293.6, method="nearest", tolerance=1.)
    s.source = openmc.IndependentSource(
        space=openmc.stats.Box([-.63]*3, [.63]*3),
        angle=openmc.stats.Isotropic(), energy=openmc.stats.Watt(988000., 2.249e-6),
        constraints={"fissionable": True})
    entropy = openmc.RegularMesh()
    entropy.dimension = [10,10,1]
    entropy.lower_left, entropy.upper_right = [-.63]*3, [.63]*3
    s.entropy_mesh = entropy
    s.statepoint = dict(batches=[800])
    return openmc.Model(geometry=geometry, materials=openmc.Materials(materials), settings=s)
