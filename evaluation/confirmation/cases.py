"""Literal physical expectations, independent of private reference constructors."""
import hashlib
import itertools
import json
import math
import random
from pathlib import Path

from prompts.confirmation import TASKS, suite

ROOT = Path(__file__).resolve().parents[2]
OUTER = [
    [-7,-7,-25,9,7,25], [-6,-5,-24,6,5,24], [-5,-5,-22,5,5,22],
    [-7,-5,-25,7,5,25], [-9,-9,-22,9,9,22], [-2.54,-2.54,-1,2.54,2.54,1],
    [-8,-7,-26,8,7,26], [-6,-6,-25,6,6,25], [-8,-1,-1,8,1,1],
    [-10,-10,-18,10,10,18], [-1.3,-.63,-.63,1.3,.63,.63],
    [-6,-6,-24,6,6,24],
]
HEIGHTS = [18,18,16,18,15,1,20,18,1,12,.63,18]
POINTS = [[.1,0,0],[.1,0,0],[-1.2,-.8,0],[-3.7,-.65,0],
          [0,0,0],[0,0,0],[0,0,0],[-1.2,-1.3,0],[0,0,0],[0,0,0],
          [-.55,0,0],[0,0,0]]
MATERIALS = {
    'fuel_A': dict(density=10.4,atoms={'U235':.02,'U238':.98,'O16':2.},sab=[]),
    'fuel_B': dict(density=10.4,atoms={'U235':.04,'U238':.96,'O16':2.},sab=[]),
    'mixture': dict(density=3.,atoms={'U235':.04,'U238':.96,'O16':12.,'H1':20.},sab=[['c_H_in_H2O',1.]]),
    'zirconium': dict(density=6.55,atoms={'Zr90':.5145,'Zr91':.1122,'Zr92':.1715,'Zr94':.1738,'Zr96':.028},sab=[]),
    'water': dict(density=.997,atoms={'H1':2.,'O16':1.},sab=[['c_H_in_H2O',1.]]),
}


def definitions():
    from evaluation.confirmation.indc107 import verify_source
    verify_source()
    inventory, _ = suite()
    result = {}
    for i, record in enumerate(inventory['tasks']):
        source = record['source_box']
        mesh = record['entropy_mesh']
        result[record['id']] = dict(shape='confirmation', outer=OUTER[i],
            active=source['lower_left']+source['upper_right'],
            source_bounds=source['lower_left']+source['upper_right'],
            entropy_bounds=mesh['lower_left']+mesh['upper_right'],mesh=mesh['dimensions'],
            point=POINTS[i],batches=400,boundary='reflective' if i in (5,10) else 'mixed' if i==8 else 'vacuum',
            source_path='prompts/'+record['path'],source_sha256=record['sha256'],
            version=record['version'])
    return result


SPECS = definitions()


def materials(case):
    i=TASKS.index(case)
    if i==5:
        return dict(uranium_metal=dict(density=18.8,atoms={'U235':.98,'U238':99.02},sab=[]),
                    water=dict(density=1.,atoms={'H1':2.,'O16':1.},sab=[['c_H_in_H2O',1.]]))
    roles=(['fuel_A','fuel_B','zirconium','water'] if i==3 else
           ['mixture','water'] if i in (4,6,9) else
           ['fuel_B','water'] if i==8 else ['fuel_B','zirconium','water'])
    return {r:MATERIALS[r] for r in roles}


def centers(case):
    i=TASKS.index(case)
    if i==1:return [(0,0),(1.4,0),(-1.4,0),(.7,1.2),(-.7,1.2),(.7,-1.2),(-.7,-1.2)]
    if i==2:return [(-1.5,-.8),(1.5,-.8),(0,1.6)]
    if i==3:return [(c+d,y) for c in (-3.2,3.2) for d in (-.65,.65) for y in (-.65,.65)]
    if i in (7,11):return list(itertools.product((-1.3,0,1.3),repeat=2))
    if i==10:return [(-.65,0),(.65,0)]
    if i==5:return [(0,0)]
    if i==9:return [(0,0)]
    return []


def inside(point, bounds):
    return all(bounds[a] < point[a] < bounds[a+3] for a in range(3))


def expected(case, point):
    i=TASKS.index(case); x,y,z=point
    if not inside(point,OUTER[i]):return 'outside'
    if i==0:
        if abs(y)<4 and abs(z)<18:
            d=min(abs(x-c) for c in (-3,-1.5,0,1.5,3))
            if d<.25:return 'fuel_B'
            if d<.27:return 'void'
            if d<.32:return 'zirconium'
    elif i in (1,2,3,7,10,11):
        if abs(z)<HEIGHTS[i]:
            for cx,cy in centers(case):
                r=math.hypot(x-cx,y-cy)
                if i==2:
                    if r<.18:return 'water'
                    if r<.55:return 'fuel_B'
                    if r<.56:return 'void'
                    if r<.62:return 'zirconium'
                elif i==7 and cx==cy==0:
                    if r<.50:return 'water'
                    if r<.56:return 'zirconium'
                else:
                    if r<.4096:return 'fuel_A' if i==3 and cx<0 else 'fuel_B'
                    if r<.418:return 'void'
                    if r<.475:return 'zirconium'
            if i==7 and max(abs(x),abs(y))<2.22 and max(abs(x),abs(y))>2.10:
                return 'zirconium'
    elif i==4:
        if abs(z)<15 and ((abs(x)<5 and abs(y)<1) or (abs(x)<1 and abs(y)<5)):return 'mixture'
    elif i==5:
        if math.hypot(x,y)<1.27:return 'uranium_metal'
    elif i==6:
        limits=(4,3) if -20<z<-6 else (2,3) if -6<=z<6 else (2,1.5) if 6<=z<20 else (0,0)
        if abs(x)<limits[0] and abs(y)<limits[1]:return 'mixture'
    elif i==8:
        if abs(x)<1.5:return 'fuel_B'
    elif i==9 and abs(z)<12:
        if math.hypot(x,y)<4:return 'mixture'
        if math.hypot(x,y)<4.2:return 'void'
    return 'water'


def temperature(case, point):
    return 600. if case=='dual_temperature_pin_pair' and point[0]>0 and expected(case,point)=='fuel_B' else 293.6


def probes(case):
    """Fixed interface witnesses plus bounded deterministic interior sampling."""
    i=TASKS.index(case); bounds=OUTER[i]; h=HEIGHTS[i]
    points=[];groups=[]
    def add(group,p):
        points.append([float(v) for v in p]);groups.append(group)
    # Axial and material-map checks use material-interior witnesses, never exact interfaces.
    for p in [POINTS[i]]+[[cx+.1,cy,0] for cx,cy in centers(case)]:
        add('material_map',p)
        for z in (-h-.0001,-h+.0001,h-.0001,h+.0001):add('axial_ends',[p[0],p[1],z])
    if centers(case):
        radii=([0,.1,.1799,.1801,.4,.5499,.5501,.5599,.5601,.6199,.6201] if i==2 else
               [0,.9,1.2699,1.2701,1.8,2.53] if i==5 else
               [0,2,3.9999,4.0001,4.1,4.1999,4.2001,8] if i==9 else
               [0,.2,.4095,.4097,.414,.4179,.4181,.45,.4749,.4751,.4999,.5001,.5599,.5601])
        for cx,cy in centers(case):
            for r,a,z in itertools.product(radii,(.21,1.71,3.31,4.71),(-h+.001,0,h-.001)):
                add('interfaces',[cx+r*math.cos(a),cy+r*math.sin(a),z])
    # Planar features: witness both sides, with transverse points inside every segment.
    planes = {
        0: [[c+d for c in (-3,-1.5,0,1.5,3) for d in (-.32,-.27,-.25,.25,.27,.32)],[-4,4],[-18,18]],
        4: [[-5,-1,1,5],[-5,-1,1,5],[-15,15]],
        6: [[-4,-2,2,4],[-3,-1.5,1.5,3],[-20,-6,6,20]],
        7: [[-2.22,-2.1,2.1,2.22],[-2.22,-2.1,2.1,2.22],[-18,18]],
        8: [[-1.5,1.5],[],[]],
    }.get(i)
    if planes:
        mids=[]
        for axis in range(3):
            edges=sorted(set([bounds[axis],bounds[axis+3]]+planes[axis]))
            mids.append([(a+b)/2 for a,b in zip(edges,edges[1:])])
        for axis in range(3):
            other=[a for a in range(3) if a!=axis]
            for c,eps,u,v in itertools.product(planes[axis],(-.0001,.0001),mids[other[0]],mids[other[1]]):
                p=[0.,0.,0.];p[axis]=c+eps;p[other[0]]=u;p[other[1]]=v;add('interfaces',p)
    for axis,side,eps in itertools.product(range(3),(0,3),(-.0001,.0001)):
        p=[.123,.321,.177];p[axis]=bounds[axis+side]+eps;add('outer_faces',p)
    rng=random.Random(20261018+i)
    for _ in range(1400):add('domain_samples',[rng.uniform(bounds[a],bounds[a+3]) for a in range(3)])
    if len(points)>12000:raise ValueError('Confirmation probe budget exceeded')
    return points,groups


def requirements(case):
    spec=SPECS[case]
    if hashlib.sha256((ROOT/spec['source_path']).read_bytes()).hexdigest()!=spec['source_sha256']:
        raise ValueError('Confirmation specification changed')
    bounds=[[spec['outer'][a],spec['outer'][a+3]] for a in range(3)]
    rows=[]
    for axis in range(3):
        bc=('reflective' if spec['boundary']=='reflective' or (spec['boundary']=='mixed' and axis>0) else 'vacuum')
        for side,j in (('lower',0),('upper',1)):
            properties=dict(coordinate_cm=bounds[axis][j],boundary_type=bc)
            if bc=='reflective':properties['effective_albedo']=1.
            for name,value in properties.items():
                rows.append(dict(id=f'outer.{axis}.{side}.{name}',selector=dict(kind='root_box_face',
                    axis=axis,side=side,domain_bounds_cm=bounds,location_comparison={'kind':'exact'}),
                    property=name,expected=value,comparison={'kind':'exact'},
                    observations_needed=['established_root_domain','participating_face','effective_'+name]))
    return dict(format='boundary-task-requirements-v1',case=case,
        source=dict(path=spec['source_path'],sha256=spec['source_sha256'],clauses='Geometry, boundaries and material partition in the public task.'),
        requirements=rows)
