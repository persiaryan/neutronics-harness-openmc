"""Independent literal task oracles for the six public computational tasks.

This module never imports reference implementations or OpenMC.
"""
import math
import random

from evaluation.scientific.records import close

SPECS = {
    'reflective_pin_cell': dict(shape='pin', active=[-.63,-.63,-.63,.63,.63,.63],
        outer=[-.63,-.63,-.63,.63,.63,.63], mesh=[10,10,1], n=1, guides=[],
        point=[.15,0.,0.], batches=400, boundary='reflective'),
    'reflected_7x7': dict(shape='lattice', active=[-4.41,-4.41,-30.,4.41,4.41,30.],
        outer=[-12.41,-12.41,-40.,12.41,12.41,40.], mesh=[7,7,12], n=7,
        guides=[(1,1),(1,5),(5,1),(5,5)], point=[.15,0.,18.], batches=300, boundary='vacuum'),
    'moderated_cylinder': dict(shape='cylinder', active=[-12.,-12.,-25.,12.,12.,25.],
        outer=[-20.,-20.,-33.,20.,20.,33.], mesh=[12,12,10], point=[3.,0.,10.],
        batches=400, boundary='vacuum'),
    'two_composition_5x5': dict(shape='lattice', active=[-3.15,-3.15,-25.,3.15,3.15,25.],
        outer=[-10.15,-10.15,-33.,10.15,10.15,33.], mesh=[5,5,10], n=5, guides=[],
        mapping=['BBBBB','BAAAB','BAAAB','BAAAB','BBBBB'], point=[.15,0.,12.], batches=400, boundary='vacuum'),
    'axially_zoned_5x5': dict(shape='lattice', active=[-3.15,-3.15,-30.,3.15,3.15,30.],
        outer=[-11.15,-11.15,-40.,11.15,11.15,40.], mesh=[5,5,12], n=5, guides=[],
        zones=[-10.,10.], point=[.15,0.,20.], batches=400, boundary='vacuum'),
    'asymmetric_5x5': dict(shape='lattice', active=[-3.15,-3.15,-30.,3.15,3.15,30.],
        outer=[-8.15,-10.15,-38.,13.15,9.15,42.], mesh=[5,5,12], n=5,
        guides=[(0,1),(2,4),(4,0)], point=[.15,0.,18.], batches=400, boundary='vacuum'),
}


def materials(case):
    water = dict(density=.997, atoms={'H1':2.,'O16':1.}, sab=[['c_H_in_H2O',1.]])
    if case == 'moderated_cylinder':
        return {'mixture':dict(density=3., atoms={'U235':.04,'U238':.96,'O16':12.,'H1':20.},
                               sab=[['c_H_in_H2O',1.]]), 'water':water}
    result = {'zirconium':dict(density=6.55, atoms={'Zr90':.5145,'Zr91':.1122,'Zr92':.1715,'Zr94':.1738,'Zr96':.028}, sab=[]),
              'water':water}
    if case in ('two_composition_5x5','axially_zoned_5x5'):
        result['fuel_A'] = dict(density=10.4, atoms={'U235':.02,'U238':.98,'O16':2.}, sab=[])
        result['fuel_B'] = dict(density=10.4, atoms={'U235':.04,'U238':.96,'O16':2.}, sab=[])
    else:
        result['fuel'] = dict(density=10.4, atoms={'U235':.04,'U238':.96,'O16':2.}, sab=[])
    return result


def in_box(point, bounds):
    return all(bounds[i] <= point[i] <= bounds[i+3] for i in range(3))


def expected(case, point):
    s = SPECS[case]; x,y,z = point
    if not in_box(point,s['outer']): return 'outside'
    if s['shape'] == 'cylinder':
        if math.hypot(x,y) > 20.: return 'outside'
        return 'mixture' if math.hypot(x,y) < 12. and -25. < z < 25. else 'water'
    if not in_box(point,s['active']): return 'water'
    n=s['n']; half=(n-1)/2
    column=min(n-1,math.floor((x-s['active'][0])/1.26))
    row=min(n-1,math.floor((s['active'][4]-y)/1.26))
    radius=math.hypot(x-(column-half)*1.26,y-(half-row)*1.26)
    if (row,column) in s['guides']:
        return 'zirconium' if .5 < radius < .56 else 'water'
    if radius < .4096:
        if 'mapping' in s: return 'fuel_'+s['mapping'][row][column]
        if 'zones' in s: return 'fuel_B' if -10. < z < 10. else 'fuel_A'
        return 'fuel'
    return 'void' if radius < .418 else 'zirconium' if radius < .475 else 'water'


def probes(case):
    s=SPECS[case]; points=[]; groups=[]
    def add(group,p): points.append([float(v) for v in p]);groups.append(group)
    if s['shape']=='cylinder':
        for radius in (0.,6.,11.9999,12.0001,16.,19.9999,20.0001):
            for z in (-33.0001,-32.9999,-25.0001,-24.9999,0.,24.9999,25.0001,32.9999,33.0001):
                for i in range(16):
                    angle=.13+2*math.pi*i/16
                    add('interfaces',(radius*math.cos(angle),radius*math.sin(angle),z))
    else:
        n=s['n']; half=(n-1)/2; height=s['active'][5]
        heights=[-height+.0001,0.,height-.0001]
        if 'zones' in s: heights.extend([-10.0001,-9.9999,9.9999,10.0001])
        for row in range(n):
            for column in range(n):
                cx,cy=(column-half)*1.26,(half-row)*1.26
                radii=(0.,.25,.4999,.5001,.53,.5599,.5601,.6) if (row,column) in s['guides'] else (
                    0.,.2,.4095,.4097,.414,.4179,.4181,.45,.4749,.4751,.6)
                for z in heights:
                    for r in radii:
                        for a in (.21,1.71,3.31,4.71):
                            add('interfaces',(cx+r*math.cos(a),cy+r*math.sin(a),z))
                for z in (-height-.0001,height+.0001): add('axial_ends',(cx,cy,z))
                for z in (-height/2,0.,height/2): add('material_map',(cx+.15,cy,z))
    if s['shape']!='cylinder':
        for axis in range(3):
            for side in (0,3):
                bound=s['outer'][axis+side]
                for offset in (-.0001,.0001):
                    for a,b in ((.123,.321),(-.51,.47)):
                        p=[a,b,.177];p[axis]=bound+offset;add('outer_faces',p)
    rng=random.Random(8172026)
    for _ in range(1400): add('domain_samples',[rng.uniform(s['outer'][i],s['outer'][i+3]) for i in range(3)])
    if s['shape']=='lattice':
        for _ in range(400): add('active_samples',[rng.uniform(s['active'][i],s['active'][i+3]) for i in range(3)])
    if len(points)>12000: raise ValueError('Inspector point budget exceeded')
    return points,groups


def check_materials(case, observed):
    specs=materials(case); roles={}; checks=[]
    for m in observed:
        actual=m['atom_fractions']; role='unknown'
        for name,spec in specs.items():
            target={n:v/sum(spec['atoms'].values()) for n,v in spec['atoms'].items()}
            if set(actual)==set(target) and all(close(actual[n],v) for n,v in target.items()): role=name;break
        roles[str(m['id'])]=role
        checks.append(dict(field='composition',material_id=m['id'],passed=role!='unknown',actual=actual,role=role))
        if role=='unknown': continue
        spec=specs[role]
        for field,actual,target in [('density',m['density_g_cm3'],spec['density']),('thermal_scattering',m['sab'],spec['sab']),('forced_isotropic',m['isotropic'],[])]:
            ok=close(actual,target) if field=='density' else actual==target
            checks.append(dict(field=field,material_id=m['id'],actual=actual,expected=target,passed=ok))
    checks.append(dict(field='required_material_roles',passed=set(roles.values())==set(specs),actual=sorted(set(roles.values())),expected=sorted(specs)))
    return roles,checks
