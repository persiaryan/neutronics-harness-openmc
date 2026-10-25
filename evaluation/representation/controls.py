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
    reordered=wrapped('compact')
    for c in reordered.findall('geometry/cell'):
        region=c.get('region')
        if '(' not in region:
            c.set('region',' '.join(reversed(region.split())))
    water=reordered.find("geometry/cell[@id='28']")
    domain,complement=water.get('region').split(' ~(',1)
    water.set('region','~('+complement+' '+' '.join(reversed(domain.split())))
    add('compact-reordered-terms',reordered,'conformity_established')
    gap = wrapped('partitioned')
    gap.find('geometry').remove(gap.find("geometry/cell[@id='30']"))
    add('missing-lower-slab', gap, 'nonconforming', [-3., -3., -2.5])
    unbounded = wrapped('partitioned')
    unbounded.find("geometry/cell[@id='30']").set('region', '1 -2 3 -4 -7')
    add('unbounded-lower-water', unbounded, 'nonconforming', [-3., -3., -3.5])
    moved = wrapped('partitioned')
    moved.find("geometry/surface[@id='1']").set('coeffs', '-4.25')
    add('moved-face', moved, 'nonconforming', [-4.1, 0., 0.])
    hole=wrapped('compact')
    removed=box(hole,100,[-3.5,-3.5,-.5],[-3.,-3.,.5])
    water=hole.find("geometry/cell[@id='28']")
    water.set('region',water.get('region')+' ~('+removed+')')
    add('interior-water-hole',hole,'nonconforming',[-3.25,-3.25,0.])
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


SOURCE_POINTS=[[-.5,.25,.1],[.5,.25,.1],[0.,.25,.1]]


def source_model(*, kind=None, ids=None, flag=False):
    root=materials()
    domain=box(root, 1, [-2,-2,-2], [2,2,2], 'vacuum')
    left=box(root, 10, [-.8,-1,-1], [-.2,1,1])
    right=box(root, 20, [.2,-1,-1], [.8,1,1])
    cell(root,1,left,1); cell(root,2,right,1)
    cell(root,3,f'{domain} ~(({left}) | ({right}))',2)
    settings=root.find('settings')
    for tag,value in [('run_mode','eigenvalue'),('particles',100),('batches',4),('inactive',1),('seed',41)]:
        ET.SubElement(settings,tag).text=str(value)
    source=ET.SubElement(settings,'source',type='independent',particle='neutron')
    space=ET.SubElement(source,'space',type='box')
    ET.SubElement(space,'parameters').text='-1 -.9 -.9 1 .9 .9'
    constraints=ET.SubElement(source,'constraints')
    ET.SubElement(constraints,'rejection_strategy').text='resample'
    if flag: ET.SubElement(constraints,'fissionable').text='true'
    if kind is not None:
        ET.SubElement(constraints,'domain_type').text=kind
        ET.SubElement(constraints,'domain_ids').text=' '.join(map(str,ids))
    return root


def source_controls():
    rows=[]
    def add(name,root,expected,labels=None):
        rows.append(dict(id=name,xml=ET.tostring(root),expected=expected,
                         material_fissionability=labels or {1:True,2:False,3:False}))
    add('fissionable-flag',source_model(flag=True),True)
    add('all-fuel-cells',source_model(kind='cell',ids=[1,2]),True)
    add('fuel-material',source_model(kind='material',ids=[1]),True)
    add('redundant-fuel-domain',source_model(kind='cell',ids=[1,2],flag=True),True)
    add('all-cells-with-filter',source_model(kind='cell',ids=[1,2,3],flag=True),True)
    add('water-domain',source_model(kind='cell',ids=[3]),False)
    add('missing-fuel-cell',source_model(kind='cell',ids=[1]),False)
    add('extra-water-cell',source_model(kind='cell',ids=[1,2,3]),False)
    changed=renumber(source_model(kind='cell',ids=[1,2]))
    changed.find('settings/source/constraints/domain_ids').text='511 522'
    for m in changed.findall('materials/material'): m.set('id',str(int(m.get('id'))+100))
    for c in changed.findall('geometry/cell'): c.set('material',str(int(c.get('material'))+100))
    add('renumbered-cells-and-materials',changed,True,{101:True,102:False,103:False})
    wrong=source_model(kind='cell',ids=[1])
    wrong.find("geometry/cell[@id='1']").set('id','93')
    wrong.find("geometry/cell[@id='3']").set('id','1')
    add('same-id-now-water',wrong,False)
    unknown=source_model(kind='universe',ids=[1])
    add('unsupported-universe-domain',unknown,None)
    unknown=source_model(kind='cell',ids=[1,2])
    ET.SubElement(unknown.find('settings/source/constraints'),'energy_bounds').text='1 2'
    add('unknown-extra-restriction',unknown,None)
    wrong=source_model(kind='cell',ids=[1])
    ET.SubElement(wrong.find('settings/source/constraints'),'energy_bounds').text='1 2'
    add('known-omission-with-unknown',wrong,False)
    duplicate=source_model(kind='cell',ids=[1,2])
    ET.SubElement(duplicate.find('settings/source/constraints'),'domain_ids').text='3'
    add('duplicate-domain-field',duplicate,None)
    return rows
