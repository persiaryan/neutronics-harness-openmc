"""Reference-free OpenMC 0.15.3 boundary observer, run only in a fresh container.

Root CSG domain proof is bounded Boolean abstraction, NOT geometric probing.
Loaded region bounds can prove absence, never occupancy. Exact Boolean reduction
precedes bounded residual enumeration. Domain occupancy and face participation
remain separate obligations; overlaps and filled interiors are not certified.
"""
import hashlib
import itertools
import json
import math
import sys
import time
import xml.etree.ElementTree as ET

import openmc

VERSION = 'effective-boundary-observation-v2'
MAX_STATES = 65536
MAX_WORK = 4000000
MAX_ATOMS = 16  # Per residual query, AFTER spatial pruning and exact reduction.


class CoverageLimit(Exception):
    def __init__(self, guard, bound, attempted):
        self.detail = dict(guard=guard, configured_bound=bound, attempted=attempted)


def junction(op, children, tick):
    """Constant folding, flattening, complementary literals and absorption.

    x OR (NOT x AND y) == x OR y, and its dual. No geometric assumptions,
    distribution into DNF, solver dependency, or unrestricted search.
    """
    identity = op == 'and'
    terms = set()
    pending = list(children)
    while pending:
        tick()
        child = pending.pop()
        if isinstance(child, bool):
            if child != identity:
                return child
        elif child[0] == op:
            pending.extend(child[1])
        else:
            terms.add(child)
    while True:
        literals = {t for t in terms if t[0] == 'atom'}
        tick(len(terms))
        opposite = {('atom', t[1], not t[2]) for t in literals}
        if literals & opposite:
            return not identity
        reduced = set(literals)
        for term in terms - literals:
            tick(len(term[1]))
            parts = set(term[1])
            if parts & literals:
                continue  # x OR (x AND y), or x AND (x OR y)
            parts -= opposite
            if not parts:
                return not identity
            if len(parts) == 1:
                only = next(iter(parts))
                if only[0] == op:
                    reduced.update(only[1])
                else:
                    reduced.add(only)
            else:
                reduced.add((term[0], tuple(sorted(parts))))
        if reduced == terms:
            break
        terms = reduced
    if not terms:
        return identity
    return next(iter(terms)) if len(terms) == 1 else (op, tuple(sorted(terms)))


def plane(surface):
    if not isinstance(surface, openmc.Plane):
        return None
    normal = [float(surface.a), float(surface.b), float(surface.c)]
    axes = [i for i, v in enumerate(normal) if v != 0]
    if len(axes) != 1:
        return None
    axis = axes[0]
    return axis, float(surface.d) / normal[axis], 1 if normal[axis] > 0 else -1


def _inspect(payload):
    if openmc.__version__ != '0.15.3':
        raise RuntimeError('Boundary observer requires OpenMC 0.15.3')
    xml = payload['xml']
    root = ET.fromstring(xml)
    materials = openmc.Materials.from_xml_element(root.find('materials'))
    geometry = openmc.Geometry.from_xml_element(root.find('geometry'), materials)
    cells = list(geometry.root_universe.cells.values())
    nodes = {int(n.get('id')): n for n in root.findall('geometry/surface')}
    records, surface_objects = {}, {}
    for cell in cells:
        if cell.region is not None:
            surface_objects.update(cell.region.get_surfaces())
    for sid, s in sorted(surface_objects.items()):
        p = plane(s)
        node = nodes[sid]
        records[sid] = dict(ref='surface:'+str(sid), id=sid, name=s.name,
            geometry=dict(type=s.type, coefficients={k: float(v) for k,v in s.coefficients.items()},
                          axis_plane=None if p is None else dict(axis=p[0], coordinate_cm=p[1])),
            boundary_type=s.boundary_type,
            effective_albedo=float(s.albedo) if s.boundary_type in ('reflective','white','periodic') else None,
            albedo_applicable=s.boundary_type in ('reflective','white','periodic'),
            xml_provenance=dict(boundary_attribute=node.get('boundary'), albedo_attribute=node.get('albedo'),
                meaning='retrieved XML attributes only; original Python arguments are not recoverable'),
            limitations=['periodic_coupling_not_observed'] if s.boundary_type=='periodic' else [])
    result = dict(status='inspected', observer_version=VERSION, openmc_version=openmc.__version__,
        model_xml_sha256=hashlib.sha256(xml.encode()).hexdigest(), surfaces=list(records.values()), faces=[],
        coverage=dict(method='region-bound pruning and exact Boolean reduction over axis-plane arrangements',
            state_limit=MAX_STATES, work_limit=MAX_WORK, global_geometry_validity='not_assessed',
            residual_atom_limit=MAX_ATOMS,
            face_edges_and_corners='excluded', interior_cells_and_curved_boundaries='not assessed',
            xml_surfaces_not_used_by_root=sorted(set(nodes)-set(records))),
        domain=dict(status='indeterminate', cause=None), limitations=[])
    coverage = result['coverage']
    effort = coverage['analysis'] = dict(work_units=0, arrangement_cells_visited=0,
        enumerated_assignments=0, residual_queries=0, max_residual_atoms=0,
        cells_pruned_by_bounds=0, exploration_started=False, phase='preparation')
    def tick(amount=1):
        attempted = effort['work_units'] + amount
        if attempted > MAX_WORK:
            raise CoverageLimit('work_units', MAX_WORK, attempted)
        effort['work_units'] = attempted
    def unknown(cause):
        result['domain'] = dict(status='indeterminate', cause=cause)
        result['limitations'].append(cause)
        return result
    if not cells or any(c.region is None for c in cells):
        return unknown('unbounded_or_unspecified_root_region')
    coordinates = [sorted({p[i] for s in surface_objects.values() if (p:=plane(s)) is not None and p[0]==axis})
                   for axis,i in [(0,1),(1,1),(2,1)]]
    if any(not v or any(not math.isfinite(x) for x in v) for v in coordinates):
        return unknown('axis_plane_enclosure_unavailable')
    atoms = {}
    def atom(s):
        # Other exact surface descriptions can share an abstract sign. No
        # approximate geometry equality, IDs, or names are used in this key.
        key = (s.type, tuple(sorted((k,float(v)) for k,v in s.coefficients.items())))
        if key not in atoms:
            atoms[key] = len(atoms)
        return atoms[key]
    node_count = 0
    def expression(region, negate=False):
        nonlocal node_count
        tick()
        node_count += 1
        if isinstance(region, openmc.Halfspace):
            p = plane(region.surface)
            positive = (region.side == '+') != negate
            if p is not None:
                axis,coord,orientation=p
                return ('plane',axis,coordinates[axis].index(coord),positive==(orientation>0))
            return ('atom',atom(region.surface),positive)
        if isinstance(region, (openmc.Intersection, openmc.Union)):
            conjunction = isinstance(region, openmc.Intersection) != negate
            return ('and' if conjunction else 'or', tuple(expression(n, negate) for n in region))
        if isinstance(region, openmc.Complement):
            return expression(region.node, not negate)
        raise ValueError('Unsupported OpenMC region object')

    def reduce_at(expr, index):
        tick()
        op=expr[0]
        if op=='plane':
            return (index[expr[1]]>expr[2]) == expr[3]
        if op=='atom':
            return expr
        return junction(op, (reduce_at(e,index) for e in expr[1]), tick)

    def possible_values(expr, *, existence=False):
        if isinstance(expr, bool):
            return {expr}
        effort['residual_queries'] += 1
        variables = set()
        def collect(e):
            tick()
            if e[0] == 'atom':
                variables.add(e[1])
            else:
                for child in e[1]:
                    collect(child)
        collect(expr)
        effort['max_residual_atoms'] = max(effort['max_residual_atoms'], len(variables))
        # A reduced literal or a flat junction of literals has both truth values.
        # This is an exact syntactic result, not an enumeration allowance.
        if expr[0] == 'atom' or all(e[0] == 'atom' for e in expr[1]):
            return {False, True}
        if len(variables) > MAX_ATOMS:
            raise CoverageLimit('residual_atoms', MAX_ATOMS, len(variables))
        positions = {v: i for i,v in enumerate(sorted(variables))}
        def evaluate(e, bits):
            tick()
            if e[0] == 'atom':
                return bool(bits & (1 << positions[e[1]])) == e[2]
            values = (evaluate(child,bits) for child in e[1])
            return all(values) if e[0] == 'and' else any(values)
        values = set()
        for bits in range(2**len(variables)):
            if effort['enumerated_assignments'] >= MAX_STATES:
                raise CoverageLimit('enumerated_assignments', MAX_STATES,
                                    effort['enumerated_assignments'] + 1)
            effort['enumerated_assignments'] += 1
            values.add(evaluate(expr,bits))
            if len(values) == 2 or existence and True in values:
                break
        return values

    def local_regions(index):
        for expr, bounds in zip(expressions, region_bounds):
            tick()
            # Bounds are conservative enclosures obtained from OpenMC. Disjoint
            # open arrangement cells cannot contain any point of this region.
            if any(bounds[1][a] <= edges[a][index[a]] or
                   bounds[0][a] >= edges[a][index[a]+1] for a in range(3)):
                effort['cells_pruned_by_bounds'] += 1
                yield False
            else:
                yield reduce_at(expr,index)

    def analyze():
        occupied = set()
        effort['phase'] = 'domain_occupancy'
        for index in itertools.product(*(range(n) for n in shape)):
            effort['exploration_started'] = True
            effort['arrangement_cells_visited'] += 1
            values = possible_values(junction('or', local_regions(index), tick))
            if len(values)>1:
                return unknown('root_domain_not_resolved_by_supported_abstraction')
            if True in values:
                occupied.add(index)
        if not occupied:
            return unknown('empty_root_domain')
        low=[min(i[a] for i in occupied) for a in range(3)]
        high=[max(i[a] for i in occupied) for a in range(3)]
        if any(low[a]==0 or high[a]==shape[a]-1 for a in range(3)):
            return unknown('unbounded_root_domain')
        if len(occupied)!=math.prod(high[a]-low[a]+1 for a in range(3)):
            return unknown('root_domain_is_not_a_single_box')
        bounds=[[coordinates[a][low[a]-1],coordinates[a][high[a]]] for a in range(3)]
        result['domain']=dict(status='established', shape='axis_aligned_box', bounds_cm=bounds,
            scope='union of root cell regions, open-volume domain; no assertion about overlaps or filled hierarchy')
        effort['phase'] = 'face_participation'
        active = set()
        face_cells = {(a,s): set() for a in range(3) for s in ('lower','upper')}
        for index in sorted(occupied):
            for number,expr in enumerate(local_regions(index)):
                if True not in possible_values(expr,existence=True):
                    continue
                active.add(number)
                for axis in range(3):
                    if index[axis] == low[axis]:
                        face_cells[axis,'lower'].add(number)
                    if index[axis] == high[axis]:
                        face_cells[axis,'upper'].add(number)
        active_surface_ids={sid for number in active for sid in cells[number].region.get_surfaces()}
        coverage['proven_inactive_root_surface_ids']=sorted(set(records)-active_surface_ids)
        for (axis,side),numbers in face_cells.items():
            coord=bounds[axis][side=='upper']
            contributors=[cells[n] for n in sorted(numbers)]
            refs=sorted({records[s.id]['ref'] for c in contributors for s in c.region.get_surfaces().values()
                         if (p:=plane(s)) is not None and p[0]==axis and p[1]==coord})
            limitations=[]
            if any(c.fill_type not in ('material','void') or c.translation is not None or c.rotation is not None
                   for c in contributors):
                limitations.append('filled_or_transformed_cell_may_meet_face')
            face=dict(ref=f'root-face:{axis}:{side}', axis=axis, side=side, coordinate_cm=coord,
                outward_normal=[(-1 if side=='lower' else 1) if a==axis else 0 for a in range(3)],
                tangential_bounds_cm={str(a):bounds[a] for a in range(3) if a!=axis},
                participation='root_domain_face', surface_refs=refs,
                root_cell_refs=['cell:'+str(c.id) for c in contributors], limitations=limitations)
            if not refs:
                face['limitations'].append('face_surface_binding_unresolved')
            result['faces'].append(face)
        effort['phase'] = 'complete'
        return result

    try:
        expressions = [expression(c.region) for c in cells]
        region_bounds = []
        for cell in cells:
            tick()
            lower, upper = cell.region.bounding_box
            # Outward rounding can only weaken pruning. Bounds never prove
            # occupancy. NaN bounds are ignored, not interpreted as containment.
            lower = [math.nextafter(float(v), -math.inf) if not math.isnan(v) else -math.inf for v in lower]
            upper = [math.nextafter(float(v), math.inf) if not math.isnan(v) else math.inf for v in upper]
            region_bounds.append((lower,upper))
        shape = [len(v)+1 for v in coordinates]
        edges = [[-math.inf,*v,math.inf] for v in coordinates]
        coverage.update(root_cells=len(cells),surface_records=len(records),region_nodes=node_count,
            nonplane_atoms=len(atoms),plane_coordinate_counts=[len(v) for v in coordinates],
            arrangement_cells=math.prod(shape),
            estimated_global_assignments=math.prod(shape)*(2**len(atoms)))
        if math.prod(shape) > MAX_STATES:
            raise CoverageLimit('arrangement_cells',MAX_STATES,math.prod(shape))
        return analyze()
    except CoverageLimit as exc:
        coverage.update(root_cells=len(cells),region_nodes=node_count,nonplane_atoms=len(atoms))
        coverage['limit'] = dict(exc.detail, phase=effort['phase'],
                                exploration_occurred=effort['exploration_started'])
        # A completed domain proof survives a later participation limit.
        if result['domain']['status'] == 'established':
            result['limitations'].append('coverage_budget_exhausted')
            return result
        return unknown('coverage_budget_exhausted')


def inspect(payload):
    started = time.monotonic()
    result = _inspect(payload)
    result['coverage']['analysis']['elapsed_seconds'] = round(time.monotonic()-started,6)
    return result


if __name__=='__main__':
    try:
        output=inspect(json.load(sys.stdin))
    except Exception as exc:
        output=dict(status='unsupported_or_invalid', error_type=type(exc).__name__, error=str(exc)[:1500])
    print(json.dumps(output,allow_nan=False,separators=(',',':')))
