"""Handwritten public controls, independent of campaign models and references.

Geometry is defined by literal dimensions below. The oracle is the set identity
in CONTROLS.md, plus explicit positive-volume witnesses for injected defects.
No candidate, historical verdict, private reference or observer is imported.
"""
from copy import deepcopy
import itertools
import xml.etree.ElementTree as ET


def materials():
    root = ET.Element('model')
    section = ET.SubElement(root, 'materials')
    for mid, density, atoms in [(1, 10.4, [('U235', .04), ('U238', .96), ('O16', 2.)]),
                                (2, .997, [('H1', 2.), ('O16', 1.)]),
                                (3, 6.55, [('Zr90', 1.)])]:
        m = ET.SubElement(section, 'material', id=str(mid))
        ET.SubElement(m, 'density', units='g/cm3', value=str(density))
        for name, value in atoms:
            ET.SubElement(m, 'nuclide', name=name, ao=str(value))
    ET.SubElement(root, 'geometry')
    ET.SubElement(root, 'settings')
    return root


def surface(root, sid, kind, coefficients, boundary=None):
    node = ET.SubElement(root.find('geometry'), 'surface', id=str(sid), type=kind,
                         coeffs=' '.join(map(str, coefficients)))
    if boundary is not None:
        node.set('boundary', boundary)


def cell(root, cid, region, material):
    return ET.SubElement(root.find('geometry'), 'cell', id=str(cid), universe='1',
                         material=str(material), region=region)


def box(root, first, lower, upper, boundary=None):
    terms = []
    for a, axis in enumerate('xyz'):
        for side, coordinate in enumerate((lower[a], upper[a])):
            sid = first + 2*a + side
            surface(root, sid, axis+'-plane', [coordinate], boundary)
            terms.append(str(sid) if side == 0 else '-'+str(sid))
    return ' '.join(terms)


def wrapped(style='compact'):
    root = materials()
    domain = box(root, 1, [-4, -4, -3], [4, 4, 3], 'vacuum')
    surface(root, 7, 'z-plane', [-2]); surface(root, 8, 'z-plane', [2])
    active = '7 -8'
    occupied = []
    regions = []
    cid = 0
    for i, (x, y) in enumerate(p for p in itertools.product((-.7, 0, .7), repeat=2) if p != (0, 0)):
        a = 9+3*i
        for offset, radius in enumerate((.2, .24, .3)):
            surface(root, a+offset, 'z-cylinder', [x, y, radius])
        for region, material in [(f'-{a} {active}', 1), (f'{a} -{a+1} {active}', 'void'),
                                  (f'{a+1} -{a+2} {active}', 3)]:
            cid += 1; cell(root, cid, region, material); regions.append(region)
        occupied.append(f'-{a+2} {active}')
    surface(root, 33, 'z-cylinder', [0, 0, .2])
    surface(root, 34, 'z-cylinder', [0, 0, .3])
    for region, material in [(f'-33 {active}', 2), (f'33 -34 {active}', 3)]:
        cid += 1; cell(root, cid, region, material); regions.append(region)
    occupied.append(f'-34 {active}')
    # Only the x/y faces define the wrapper; reuse the active axial planes.
    for first, radius in ((35, 1.3), (39, 1.4)):
        for offset, (kind, coordinate) in enumerate((('x-plane', -radius), ('x-plane', radius),
                                                    ('y-plane', -radius), ('y-plane', radius))):
            surface(root, first+offset, kind, [coordinate])
    inner = '35 -36 37 -38'; envelope = '39 -40 41 -42'
    wrapper = f'{envelope} ~({inner}) {active}'
    cell(root, 27, wrapper, 3)
    if style in ('compact', 'nested'):
        excluded = occupied if style == 'compact' else regions
        water = domain+' ~('+' | '.join('('+r+')' for r in [*excluded, wrapper])+')'
        cell(root, 28, water, 2)
    else:
        pin_union = ' | '.join('('+r+')' for r in occupied)
        cell(root, 28, f'{inner} {active} ~({pin_union})', 2)
        cell(root, 29, f'{domain} ~({envelope}) {active}', 2)
        cell(root, 30, f'{domain} -7', 2)
        cell(root, 31, f'{domain} 8', 2)
    return root


def renumber(root):
    """Change IDs, cell order and surface declaration order together."""
    import re
    root = deepcopy(root); geometry = root.find('geometry')
    mapping = {int(s.get('id')): 1000+7*int(s.get('id')) for s in geometry.findall('surface')}
    for s in geometry.findall('surface'):
        s.set('id', str(mapping[int(s.get('id'))]))
    for c in geometry.findall('cell'):
        c.set('id', str(500+11*int(c.get('id'))))
        c.set('region', re.sub(r'-?\d+', lambda m: ('-' if m[0][0]=='-' else '')+
                              str(mapping[abs(int(m[0]))]), c.get('region')))
    geometry[:] = list(reversed(list(geometry)))
    return root


def boundary_controls():
    rows = []
    def add(name, root, expected, witness=None):
        rows.append(dict(id=name, xml=ET.tostring(root), expected=expected, witness=witness))
    for style in ('compact', 'nested', 'partitioned'):
        model = wrapped(style)
        add(style, model, 'conformity_established')
        add(style+'-renumbered', renumber(model), 'conformity_established')
    gap = wrapped('partitioned')
    gap.find('geometry').remove(gap.find("geometry/cell[@id='30']"))
    add('missing-lower-slab', gap, 'nonconforming', [-3., -3., -2.5])
    unbounded = wrapped('partitioned')
    unbounded.find("geometry/cell[@id='30']").set('region', '1 -2 3 -4 -7')
    add('unbounded-lower-water', unbounded, 'nonconforming', [-3., -3., -3.5])
    moved = wrapped('partitioned')
    moved.find("geometry/surface[@id='1']").set('coeffs', '-4.25')
    add('moved-face', moved, 'nonconforming', [-4.1, 0., 0.])
    overlap = wrapped('partitioned')
    cell(overlap, 90, box(overlap, 100, [-3.5, -3.5, -.5], [-3., -3., .5]), 2)
    add('localized-overlap', overlap, 'geometry_overlap', [-3.25, -3.25, 0.])
    for behavior in ('vacuum', 'transmission'):
        for order in ('first', 'last'):
            root = materials(); domain = box(root, 1, [-4, -4, -3], [4, 4, 3], 'vacuum')
            surface(root, 70, 'z-plane', [-3], behavior)
            region = '70 '+domain if order == 'first' else domain+' 70'
            cell(root, 1, region, 2)
            add('coincident-'+behavior+'-'+order, root,
                'conformity_established' if behavior == 'vacuum' else 'indeterminate')
    return rows


def specification():
    bounds = [[-4, 4], [-4, 4], [-3, 3]]
    requirements = []
    for axis in range(3):
        for side, i in [('lower', 0), ('upper', 1)]:
            for prop, value in [('coordinate_cm', bounds[axis][i]), ('boundary_type', 'vacuum')]:
                requirements.append(dict(id=f'{axis}.{side}.{prop}', property=prop, expected=value,
                    comparison=dict(kind='exact'), observations_needed=['established domain', 'face behavior'],
                    selector=dict(kind='root_box_face', axis=axis, side=side, domain_bounds_cm=bounds,
                                  location_comparison=dict(kind='exact'))))
    return dict(format='boundary-task-requirements-v1', source=dict(path='evaluation/representation/CONTROLS.md'),
                requirements=requirements)
