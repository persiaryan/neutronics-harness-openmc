"""Reference-free flat-cell inventory and strict-interior source witnesses.

Runs only inside the isolated XML inspector. No cross sections or Python model
are loaded. It never infers material fissionability from nuclide names.
"""
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET

import openmc


def inspect(payload):
    if openmc.__version__!='0.15.3':
        raise RuntimeError('Source-domain inspector requires OpenMC 0.15.3')
    xml=payload['xml']; root=ET.fromstring(xml)
    materials=openmc.Materials.from_xml_element(root.find('materials'))
    geometry=openmc.Geometry.from_xml_element(root.find('geometry'), materials)
    result=dict(status='inspected', observer_version='source-domain-observation-v1',
                openmc_version=openmc.__version__, model_xml_sha256=hashlib.sha256(xml.encode()).hexdigest(),
                cells=[], witnesses=[], limitations=[])
    cells=list(geometry.root_universe.cells.values())
    if (len(cells)!=len(root.findall('geometry/cell')) or root.find('geometry/lattice') is not None or
        any(c.fill_type not in ('material','void') or c.region is None or c.translation is not None or c.rotation is not None for c in cells)):
        result['limitations'].append('requires_flat_untransformed_material_cells')
        return result
    result['cells']=[dict(id=c.id, material_id=None if c.fill is None else c.fill.id) for c in cells]
    for i, point in enumerate(payload['points']):
        if len(point)!=3 or any(not math.isfinite(v) for v in point):
            raise ValueError('Invalid witness point')
        selected=[c for c in cells if point in c.region]
        if len(selected)!=1:
            continue
        # A witness away from every region surface is interior, rather than a
        # zero-measure surface convention. Unqualified surfaces yield no witness.
        values=[float(s.evaluate(point)) for c in cells for s in c.region.get_surfaces().values()]
        if not all(math.isfinite(v) and abs(v)>1e-8 for v in values):
            continue
        c=selected[0]
        result['witnesses'].append(dict(point_index=i, point=point, cell_id=c.id,
            material_id=None if c.fill is None else c.fill.id))
    result['coverage']=dict(queried_points=len(payload['points']), strict_interior_witnesses=len(result['witnesses']),
                           method='flat loaded-cell inventory and finite interior counterexamples',
                           global_geometry_validity='not_assessed')
    return result


if __name__=='__main__':
    try:
        payload=json.loads(sys.stdin.buffer.read(4_000_001))
        if len(payload['points'])>12000:
            raise ValueError('Too many witness points')
        result=inspect(payload)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, ZeroDivisionError, RecursionError) as exc:
        result=dict(status='unsupported_or_invalid', error_type=type(exc).__name__, error=str(exc)[:1000])
    print(json.dumps(result, separators=(',', ':'), allow_nan=False))
