"""Separate boundary extraction receipts, data requirements, and comparison.

No score is assigned here. Requirement comparison never reads a reference model.
"""
import json
import math
from pathlib import Path

from evaluator.evidence import InsufficientEvidence
from evaluator.run import digest
from evaluator.transport_input import read_regular
from evaluation.scientific import inspection
from evaluation.scientific.records import require

VERSION = 'effective-boundary-observation-v2'
COMPARISON = 'effective-boundary-comparison-v1'
WORKER = Path(__file__).with_name('boundary_worker_v2.py')
REQUIREMENTS = Path(__file__).with_name('boundary_requirements_v1.json')
ROOT = Path(__file__).resolve().parents[2]


def observe(xml, output, *, wall_seconds=120):
    return inspection.inspect_xml(xml, [], output, wall_seconds=wall_seconds, capability='effective-boundary-v2')


def record(directory, xml):
    directory = Path(directory)
    read = lambda n: json.loads(read_regular(directory/n))
    manifest=read('manifest.json'); payload=read_regular(directory/'input.json'); worker=WORKER.read_bytes()
    require(manifest['format']=='private-boundary-inspection-v2' and manifest['image_id']==inspection.IMAGE,
            'Unknown boundary observation protocol')
    require(manifest['candidate_python_access'] is False and manifest['nuclear_data_access'] is False and
            manifest['host_mounts'] is False and manifest['native_transport']=='not_run' and manifest['points']==0,
            'Unexpected boundary observation access')
    require(manifest['model_xml_sha256']==digest(xml) and manifest['input_sha256']==digest(payload) and
            json.loads(payload)==dict(xml=xml.decode(),points=[]), 'Boundary observation input changed')
    require(read_regular(directory/'worker.py')==worker and manifest['worker_sha256']==digest(worker),
            'Unqualified boundary observer version')
    require(inspection.verify(read('container-inspect.json'))==read('container-checks.json'), 'Boundary containment changed')
    require(read('execution.json')==dict(exit_code=0,stop_reason=None), 'Boundary observer execution incomplete')
    result,stdout=read('result.json'),read('stdout.json')
    if result['cleanup_confirmed'] is not True or result['status']!='inspected':
        raise InsufficientEvidence('Boundary observer did not complete with confirmed cleanup')
    require(all(result.get(k)==v for k,v in stdout.items()) and stdout['status']=='inspected', 'Boundary result changed')
    require(stdout['observer_version']==VERSION and stdout['openmc_version']=='0.15.3' and
            stdout['model_xml_sha256']==digest(xml), 'Boundary semantic identity changed')
    return stdout


def requirements(case):
    package=json.loads(REQUIREMENTS.read_bytes())
    if case not in package['tasks']:
        raise ValueError('Task has no qualified boundary requirement set')
    task=package['tasks'][case]
    require(digest((ROOT/task['source']['path']).read_bytes())==task['source']['sha256'],
            'Public task changed since boundary requirements were transcribed')
    rows=[]
    for axis in range(3):
        for side,index in [('lower',0),('upper',1)]:
            selector=dict(kind='root_box_face',axis=axis,side=side,domain_bounds_cm=task['domain_bounds_cm'],
                          location_comparison=package['location_comparison'])
            properties=dict(coordinate_cm=task['domain_bounds_cm'][axis][index],boundary_type=task['boundary_type'])
            if task['effective_albedo'] is not None:
                properties['effective_albedo']=task['effective_albedo']
            for prop,value in properties.items():
                rows.append(dict(id=f'outer.{axis}.{side}.{prop}',selector=selector,property=prop,expected=value,
                    comparison=package['location_comparison'] if prop=='coordinate_cm' else package['property_comparison'],
                    observations_needed=['established_root_domain','participating_face','effective_'+prop]))
    return dict(format=package['format'],case=case,source=task['source'],requirements=rows)


def equal(actual, expected, rule):
    if rule=={'kind':'exact'}:
        return type(actual)==type(expected) and actual==expected or (
            type(actual) in (int,float) and type(expected) in (int,float) and actual==expected)
    require(rule.get('kind')=='absolute' and set(rule)=={'kind','tolerance'} and
            type(rule['tolerance']) in (int,float) and math.isfinite(rule['tolerance']) and rule['tolerance']>=0,
            'Unsupported boundary comparison rule')
    return (type(actual) in (int,float) and type(expected) in (int,float) and
            math.isfinite(actual) and abs(actual-expected)<=rule['tolerance'])


def compare(observation, specification):
    # The requirement comparator is unchanged. Reading a historical observation
    # here does not verify its receipts or upgrade it to a current assessment.
    require(observation['observer_version'] in ('effective-boundary-observation-v1',VERSION),
            'Unsupported boundary observations')
    require(specification['format']=='boundary-task-requirements-v1', 'Unsupported boundary requirements')
    surfaces={s['ref']:s for s in observation['surfaces']}
    rows=[]
    for req in specification['requirements']:
        row=dict(requirement_id=req['id'], property=req['property'], expected=req['expected'], rule=req['comparison'],
            source=specification['source'], selector=req['selector'], observations_needed=req['observations_needed'],
            model_xml_sha256=observation['model_xml_sha256'], verdict='indeterminate', cause=None,
            evidence=[], actual=[])
        rows.append(row)
        if observation['domain']['status']!='established':
            row['cause']=observation['domain']['cause']; continue
        sel=req['selector']
        require(sel['kind']=='root_box_face' and sel['axis'] in (0,1,2) and sel['side'] in ('lower','upper'),
                'Unsupported boundary selector')
        faces=[f for f in observation['faces'] if f['axis']==sel['axis'] and f['side']==sel['side']]
        if len(faces)!=1:
            row['cause']='missing_or_ambiguous_face_observation'; continue
        face=faces[0];row['evidence']=[face['ref'],*face['surface_refs']]
        if req['property']=='coordinate_cm':
            row['actual']=[face['coordinate_cm']]
        else:
            require(req['property'] in ('boundary_type','effective_albedo'), 'Unsupported boundary property')
            # Physical matching requires the complete face extent, not its ID.
            bounds=observation['domain']['bounds_cm']
            if any(not equal(x,y,sel['location_comparison']) for a,b in zip(bounds,sel['domain_bounds_cm']) for x,y in zip(a,b)):
                row['cause']='required_domain_location_not_matched'; continue
            if face['limitations']:
                row['cause']=face['limitations'][0]; continue
            if not face['surface_refs'] or any(ref not in surfaces for ref in face['surface_refs']):
                row['cause']='missing_surface_observation'; continue
            selected=[surfaces[ref] for ref in face['surface_refs']]
            row['actual']=[s.get(req['property']) for s in selected]
            if req['property']=='effective_albedo' and any(not s['albedo_applicable'] for s in selected):
                row['cause']='albedo_not_applicable_to_observed_boundary_type'; continue
            if any(v is None for v in row['actual']):
                row['cause']='missing_effective_property_observation'; continue
            if len(set(row['actual']))>1:
                row['cause']='coincident_surfaces_have_ambiguous_behavior'; continue
        row['verdict']='conformity_established' if all(equal(v,req['expected'],req['comparison']) for v in row['actual']) else 'nonconforming'
        if row['verdict']=='nonconforming':
            row['cause']='observed_property_mismatch'
    return dict(format=COMPARISON, requirements_sha256=digest(json.dumps(specification,sort_keys=True).encode()),
        model_xml_sha256=observation['model_xml_sha256'], verdicts=rows,
        coverage=observation['coverage'], global_geometry_verdict='not_assessed')
