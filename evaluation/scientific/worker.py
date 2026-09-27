"""Trusted, mount-free OpenMC Python inspector. Input/output are bounded JSON.

This file runs via python -I -B -c in a fresh container, never on the host.
It loads only inline materials and CSG, not Model/settings/plots or Python code.
"""
import json
import math
from numbers import Real
import sys
import xml.etree.ElementTree as ET

import numpy as np
import openmc


def scalar_temperature(value):
    """Finite scalar or singleton real sequence; no distributed-instance choice."""
    if value is None:
        return None, 'missing_effective_temperature'
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            return None, 'distributed_or_empty_temperature'
        value = value[0]
    if isinstance(value, bool) or not isinstance(value, Real):
        return None, 'unsupported_temperature_type'
    value = float(value)
    if not math.isfinite(value):
        return None, 'nonfinite_temperature'
    return value, None


def inspect(payload):
    if openmc.__version__ != '0.15.3':
        raise RuntimeError('Inspector requires OpenMC 0.15.3')
    root = ET.fromstring(payload['xml'])  # Host has already applied bounded XML admission.
    materials = openmc.Materials.from_xml_element(root.find('materials'))
    material_nodes = {int(node.get('id')): node for node in root.findall('materials/material')}
    # OpenMC 0.15.3 src/material.cpp requires nuclides or macroscopic data.
    # A void is a cell with fill=None, not a Material with an empty composition.
    # Check before any density conversion (including for unused materials).
    findings = [{'code': 'material_requires_nuclides_or_macroscopic',
                 'material_id': material.id, 'nuclide_count': 0,
                 'macroscopic_present': False}
                for material in materials
                if not material.nuclides and material_nodes[material.id].find('macroscopic') is None]
    if findings:
        return {'status': 'invalid_model', 'openmc_version': openmc.__version__,
                'findings': findings}
    geometry = openmc.Geometry.from_xml_element(root.find('geometry'), materials)
    default = float(root.findtext('settings/temperature_default', '293.6'))
    records = []
    for material in materials:
        atoms = material.get_nuclide_atom_densities()
        total = sum(atoms.values())
        node = material_nodes[material.id]
        records.append({'id': material.id, 'density_g_cm3': material.get_mass_density(),
                        'atom_fractions': {n: a/total for n,a in atoms.items()},
                        'sab': sorted([[s.get('name'), float(s.get('fraction', '1'))] for s in node.findall('sab')]),
                        'isotropic': list(material.isotropic)})

    # Collect every reachable boundary, including cells missed by the probes.
    surfaces, seen = {}, set()
    def inventory(universe, transformed=False, depth=0):
        if depth > 32:
            raise ValueError('Geometry nesting exceeds supported depth')
        key = (id(universe), transformed)
        if key in seen:
            return
        seen.add(key)
        if isinstance(universe, openmc.RectLattice):
            for child in universe.get_unique_universes().values():
                inventory(child, True, depth+1)
        elif isinstance(universe, openmc.Universe):
            for cell in universe.cells.values():
                if cell.region is not None:
                    for s in cell.region.get_surfaces().values():
                        if s.boundary_type != 'transmission':
                            surfaces[(s.id, transformed)] = {
                                'id': s.id, 'type': s.type, 'coefficients': s.coefficients,
                                'boundary': s.boundary_type, 'transformed': transformed}
                if cell.fill_type in {'universe','lattice'}:
                    inventory(cell.fill, transformed or cell.translation is not None or cell.rotation is not None, depth+1)
                elif cell.fill_type not in {'material','void'}:
                    raise ValueError('Distributed material fills are not supported')
        else:
            raise ValueError('Only ordinary universes and rectangular lattices are supported')
    inventory(geometry.root_universe)

    temperature_limits = {}

    def walk(universe, point, depth=0):
        if depth > 32:
            raise ValueError('Geometry recursion exceeds supported depth')
        if isinstance(universe, openmc.RectLattice):
            index, local = universe.find_element(point)
            child = (universe.universes[universe.get_universe_index(index)]
                     if universe.is_valid_index(index) else universe.outer)
            return ('missing', []) if child is None else walk(child, np.asarray(local), depth+1)
        cells = [c for c in universe.cells.values() if point in c]
        if not cells:
            return ('outside' if depth == 0 else 'missing', [])
        leaves, state = [], 'ok' if len(cells) == 1 else 'overlap'
        for cell in cells[:16]:
            if cell.fill_type in {'material','void'}:
                temperature = cell.temperature
                if temperature is None and cell.fill is not None:
                    temperature = cell.fill.temperature
                if temperature is None:
                    temperature = default
                temperature, cause = scalar_temperature(temperature)
                if cause:
                    temperature_limits[cell.id] = dict(cell_id=cell.id, cause=cause)
                leaves.append([None if cell.fill is None else cell.fill.id, temperature])
            else:
                local = np.array(point, copy=True)
                if cell.translation is not None:
                    local -= cell.translation
                if cell.rotation is not None:
                    local = cell.rotation_matrix.dot(local)
                child_state, child_leaves = walk(cell.fill, local, depth+1)
                if child_state != 'ok' and state != 'overlap':
                    state = child_state
                leaves.extend(child_leaves[:16])
        return state, leaves[:16]

    observations = [walk(geometry.root_universe, np.asarray(point)) for point in payload['points']]
    return {'status': 'inspected', 'openmc_version': openmc.__version__,
            'materials': records, 'nontransmission_surfaces': list(surfaces.values()),
            'observations': observations,
            'temperature_limitations': list(temperature_limits.values())}


if __name__ == '__main__':
    try:
        payload = json.loads(sys.stdin.buffer.read(4_000_001))
        if len(payload['points']) > 12000:
            raise ValueError('Too many probe points')
        result = inspect(payload)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, ZeroDivisionError, RecursionError) as exc:
        result = {'status': 'unsupported_or_invalid', 'error_type': type(exc).__name__, 'error': str(exc)[:1000]}
    print(json.dumps(result, separators=(',', ':'), allow_nan=False))
