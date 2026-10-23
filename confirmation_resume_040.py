"""Prepare/check the explicitly reviewed continuation at 040; run is separate."""
import argparse
import ast
from copy import deepcopy
import itertools
import json
import math
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

import confirmation_resume_031 as prior
from evaluation.scientific import boundaries
from evaluator.transport_input import accepted_export
from experiments.run import atomic_json
from builder.context import write_json

base=prior.base
read,sha,now,require=prior.read,prior.sha,prior.now,prior.require
VERSION='confirmation-resume-040-v1'
CONTROLLER=Path(__file__).resolve()


def diagnose(previous,m,row):
    """Reconstruct evidence and a local analytic witness; do not grade or repair."""
    a=previous/row['path']/'runs'/row['case']/'assessment'
    value=base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
    require(read(a/'revised-verdict.json')==value, '039 derived verdict changed')
    v=value['verdict'];report=read(a/'report.json')
    require(v['evidence_status']=='coherent' and v['score'] is None
            and v['strict_correct'] is False and v['diagnostic_score']['status']=='unscored'
            and report['status']=='assessed' and report.get('stop') is None
            and report['cleanup_confirmed'] is True, '039 is not the reviewed unscored assessment')
    require(all(g['passed'] is True for g in v['gates'].values())
            and v['checks']['geometry']['boundaries'] is None
            and all(x is True for group,checks in v['checks'].items() for name,x in checks.items()
                    if (group,name)!=('geometry','boundaries')), 'Another unresolved or failed obligation')
    xml,_=accepted_export(a/'export')
    image=read(a/'export-boundaries/manifest.json')['image_id']
    observation=boundaries.record(a/'export-boundaries',xml,image=image)
    cause='root_domain_not_resolved_by_supported_abstraction'
    require(observation['domain']==dict(status='indeterminate',cause=cause)
            and observation['faces']==[] and observation['limitations']==[cause]
            and 'limit' not in observation['coverage'], 'Different boundary failure')
    comparison=report['fidelity']['boundaries']
    require(len(comparison['verdicts'])==12 and all(
        r['verdict']=='indeterminate' and r['cause']==cause for r in comparison['verdicts']),
        'Boundary requirements or cause changed')
    # Reconstruct the 43rd axis-plane arrangement and its water expression.
    geometry=ET.fromstring(xml).find('geometry')
    surfaces={int(s.get('id')):s for s in geometry.findall('surface')}
    types=('x-plane','y-plane','z-plane')
    coords=[sorted({float(s.get('coeffs')) for s in surfaces.values() if s.get('type')==kind})
            for kind in types]
    index=next(i for number,i in enumerate(itertools.product(
        *(range(len(c)+1) for c in coords)),1) if number==43)
    edges=[[-math.inf,*c,math.inf] for c in coords]
    box=[[edges[i][index[i]],edges[i][index[i]+1]] for i in range(3)]
    require(box==[[-6.,-2.22],[-6.,-2.22],[-18.,18.]], 'Analytic witness region changed')
    tree=ast.parse(boundaries.WORKER.read_text())
    reducer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='junction')
    namespace={}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[reducer],type_ignores=[])),
                 str(boundaries.WORKER),'exec'),namespace)
    def combine(op,items):return namespace['junction'](op,items,lambda *args:None)
    water=next(c for c in geometry.findall('cell') if c.get('id')=='28')
    tokens=re.findall(r'-?\d+|[()|]',water.get('region'))
    pos=0
    def primary():
        nonlocal pos
        token=tokens[pos];pos+=1
        if token=='(':
            expr=union()
            require(tokens[pos]==')','Malformed XML witness');pos+=1
            return expr
        sid=int(token);surface=surfaces[abs(sid)]
        if surface.get('type') in types:
            axis=types.index(surface.get('type'));coord=float(surface.get('coeffs'))
            return (index[axis]>coords[axis].index(coord))==(sid>0)
        return ('atom',abs(sid),sid>0)
    def intersection():
        items=[]
        while pos<len(tokens) and tokens[pos] not in (')','|'):items.append(primary())
        return combine('and',items)
    def union():
        nonlocal pos
        items=[intersection()]
        while pos<len(tokens) and tokens[pos]=='|':
            pos+=1;items.append(intersection())
        return combine('or',items)
    expr=union()
    ids=(11,14,17,20,23,26,29,32,34)
    require(pos==len(tokens) and expr==('and',tuple(('atom',sid,True) for sid in ids)),
            'Witness is not the nine independent exterior literals')
    certificate=[]
    for sid in ids:
        surface=surfaces[sid]
        require(surface.get('type')=='z-cylinder','Noncylindrical witness')
        x,y,r=map(float,surface.get('coeffs').split())
        dx=max(box[0][0]-x,0,x-box[0][1]);dy=max(box[1][0]-y,0,y-box[1][1])
        distance=math.hypot(dx,dy)
        require(distance>r,'Exterior condition not established throughout witness')
        certificate.append(dict(surface_id=sid,minimum_distance_cm=distance,radius_cm=r))
    require(observation['coverage']['analysis']['arrangement_cells_visited']==43,
            'Retained worker stopped elsewhere')
    return dict(format='confirmation-039-capability-diagnosis-v1',assignment='039',
        classification='coherent_unscored_boundary_abstraction_limit',score=None,
        assessed_model_failure=False,criterion_changed=False,source_repaired=False,
        native_completion_verified=True,cleanup_confirmed=True,
        boundary_assertions_indeterminate=12,cause=cause,no_coverage_limit_reached=True,
        witness=dict(visit=43,index=list(index),bounds_cm=box,reduced_expression=json.loads(json.dumps(expr)),
                     abstract_possible_values=[False,True],cylinder_exterior_certificate=certificate,
                     physical_water_occupancy_throughout_witness=True),
        limits='Local analytic witness explains observer uncertainty; it is not a new general boundary grader or full-model certification.',
        evidence_sha256={name:sha(a/name) for name in
            ('candidate.py','report.json','review.json','revised-verdict.json',
             'export-boundaries/stdout.json','export-boundaries/worker.py')},
        new_model_calls=0,new_native_transports=0,new_xml_observer_executions=0)


def terminal_prefix(previous,m):
    progress=read(previous/'progress.json');rows=progress['rows']
    require(progress['state']=='stopped' and
            progress['reason']=='Unscored evaluation incident; pause before next slot',
            'Expected stopped unscored assessment')
    require(len(rows)==240 and [r['state'] for r in rows]==
            ['finished']*29+['incident']+['finished']*8+['incident']+['pending']*201,
            'Expected exactly 039 consumed assignments')
    for original,row in zip(m['rows'],rows):
        require(all(original[k]==row[k] for k in base.migration.IMMUTABLE_ROW),
                'Assignment identity or order changed')
    ancestor=base.bound(m['resumption']['previous_manifest']).parent
    ancestor_rows,_=prior.terminal_prefix(ancestor,read(ancestor/'manifest.json'))
    require(rows[:30]==ancestor_rows[:30],'Earlier consumed outcomes changed')
    for row in rows[30:38]:
        value=base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
        target=previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'
        require(Path(row['verdict_path'])==target and read(target)==value
                and row['decision']==value['decision']
                and row['score']==value['verdict']['score']
                and row['strict_correct'] is value['verdict']['strict_correct'],
                'Consumed result contradicts reconstruction')
    row=rows[38]
    require((row['id'],row['case'],row['model'],row['arm'])==
            ('039','wrapped_eight_pin_channel','gpt-5.6-sol','A')
            and row['reason']=='Unscored evaluation incident; pause before next slot'
            and 'score' not in row, '039 operational incident changed')
    require(sum(r.get('strict_correct') is True for r in rows[:39])==33
            and sum(r.get('strict_correct') is False for r in rows[:39])==4,
            'Consumed outcome counts changed')
    return deepcopy(rows),diagnose(previous,m,row)


def prepare(output,previous):
    output,previous=Path(output).resolve(),Path(previous).resolve()
    require(not output.exists(),'Use a fresh continuation directory')
    require(previous not in output.parents,'Prepare outside previous evidence')
    proof=prior.check(previous)
    old=read(previous/'manifest.json')
    rows,diagnosis=terminal_prefix(previous,old)
    before=base.migration.inventory(previous)
    output.mkdir(parents=True)
    for row in old['rows']:
        for name in base.prepared_files(previous/row['path']):
            destination=output/row['path']/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes((previous/row['path']/name).read_bytes())
    shutil.copytree(previous/'reference-reviews',output/'reference-reviews')
    write_json(output/'previous-evidence-sha256.json',before)
    write_json(output/'incident-039.json',diagnosis)
    manifest=deepcopy(old)
    manifest['resumption_040']=dict(format=VERSION,created=now(),controller=base.binding(CONTROLLER),
        previous_manifest=base.binding(previous/'manifest.json'),
        previous_progress=base.binding(previous/'progress.json'),
        previous_launch=base.binding(previous/'resumption-launch.json'),
        previous_inventory=base.binding(output/'previous-evidence-sha256.json'),
        diagnosis=base.binding(output/'incident-039.json'),previous_readiness=proof,
        consumed_prefix_ids=[r['id'] for r in rows[:39]],remaining_sessions=201,
        maximum_new_model_requests=3216,original_maximum_model_requests=3840,
        policy='Explicit reviewed continuation after 039; future incident stopping unchanged.',
        retained_039_outcome='consumed_unscored',automatic_retries=0)
    write_json(output/'manifest.json',manifest)
    (output/'manifest.sha256').write_text(sha(output/'manifest.json')+'\n')
    write_json(output/'launch.json',dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')))
    atomic_json(output/'progress.json',dict(state='prepared_not_dispatched',rows=rows))
    require(base.migration.inventory(previous)==before,'Previous evidence changed')
    return manifest


def check(output):
    output=Path(output).resolve()
    m=read(output/'manifest.json');r=m['resumption_040']
    require((output/'manifest.sha256').read_text().strip()==sha(output/'manifest.json'),
            'Continuation manifest changed')
    require(r['format']==VERSION and (r['remaining_sessions'],r['maximum_new_model_requests'],
            r['original_maximum_model_requests'],r['automatic_retries'])==(201,3216,3840,0)
            and r['retained_039_outcome']=='consumed_unscored'
            and r['policy']=='Explicit reviewed continuation after 039; future incident stopping unchanged.',
            'Continuation policy or budgets changed')
    require(base.bound(r['controller'])==CONTROLLER,'Controller changed')
    previous=base.bound(r['previous_manifest']).parent
    require(base.bound(r['previous_progress'])==previous/'progress.json'
            and base.bound(r['previous_launch'])==previous/'resumption-launch.json',
            'Previous segment binding changed')
    inventory=read(base.bound(r['previous_inventory']))
    require(base.migration.inventory(previous)==inventory,'Previous evidence changed')
    proof=prior.check(previous)
    require(proof==r['previous_readiness'],'Previous readiness changed')
    old=read(previous/'manifest.json');expected=deepcopy(old);expected['resumption_040']=r
    require(m==expected,'Frozen experiment parameters changed')
    rows,diagnosis=terminal_prefix(previous,old)
    require(r['consumed_prefix_ids']==[x['id'] for x in rows[:39]]
            and read(base.bound(r['diagnosis']))==diagnosis,'Prefix or diagnosis changed')
    for row in m['rows']:
        require(base.prepared_files(output/row['path'])==base.prepared_files(previous/row['path']),
                'Prepared input bytes changed')
    require(read(output/'launch.json')==dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')),
        'Legacy launch protection changed')
    require(base.migration.inventory(previous)==inventory,'Evidence changed during check')
    return dict(status='passed',consumed=39,protocol_success=33,evaluated_failure=4,
        unscored=2,retained_039_score=None,pending=201,maximum_new_model_requests=3216,
        previous_evidence_files_verified=len(inventory),previous_evidence_unchanged=True,
        live_dispatched=(output/'resumption-040-launch.json').exists(),
        new_model_calls=0,new_native_transports=0)


def fresh_progress(output,m):
    require(not (output/'resumption-040-launch.json').exists(),'Continuation already consumed')
    previous=base.bound(m['resumption_040']['previous_manifest']).parent
    expected=read(previous/'progress.json')['rows'];p=read(output/'progress.json')
    require(p==dict(state='prepared_not_dispatched',rows=expected),'Progress not fresh')
    for row in p['rows']:
        require(not (output/row['path']/'runs').exists()
                and not (output/row['path']/'summary.json').exists(),'Execution already present')
    return p


def dispatch(output,maximum_requests):
    output=Path(output).resolve()
    require(maximum_requests==3216,'Declare the 3216-request continuation ceiling')
    m=read(output/'manifest.json');progress=fresh_progress(output,m);readiness=check(output)
    previous=Path(m['resumption_040']['previous_manifest']['path']).parent
    launch=dict(format=VERSION,started=now(),output=str(output),
        manifest_sha256=sha(output/'manifest.json'),maximum_new_model_requests=3216,
        controller_sha256=sha(CONTROLLER))
    with (previous.parent/(previous.name+'-resume-040-claim.json')).open('x') as stream:
        json.dump(launch,stream,indent=2)
    write_json(output/'readiness.json',readiness)
    write_json(output/'resumption-040-launch.json',launch)
    progress.update(state='running',started=launch['started']);atomic_json(output/'progress.json',progress)
    active=None
    try:
        for row in progress['rows'][39:]:
            base.bound(m['resumption_040']['controller']);base.guard(output,m,row)
            active=row;row.update(state='started',started=now())
            atomic_json(output/'progress.json',progress)
            value=base.assess(output,m,row);v=value['verdict']
            row.update(state='finished',finished=now(),score=v['score'],strict_correct=v['strict_correct'],
                decision=value['decision'],
                verdict_path=str(output/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'))
            active=None;atomic_json(output/'progress.json',progress)
            print(json.dumps(dict(id=row['id'],state='finished',score=row['score'],
                                  strict_correct=row['strict_correct'])),flush=True)
        progress.update(state='complete',finished=now())
    except BaseException as exc:
        if active is not None:active.update(state='incident',finished=now(),reason=str(exc))
        progress.update(state='stopped',finished=now(),reason=str(exc))
        if not isinstance(exc,Exception):raise
    finally:atomic_json(output/'progress.json',progress)
    return progress


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','check','run'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path)
    p.add_argument('--maximum-model-requests',type=int)
    a=p.parse_args()
    if a.action=='prepare':
        if not a.previous:p.error('Specify --previous')
        print(prepare(a.output,a.previous)['resumption_040']['format'])
    elif a.action=='check':print(json.dumps(check(a.output),indent=2))
    else:
        value=dispatch(a.output,a.maximum_model_requests);print(value['state'])
        if value['state']!='complete':raise SystemExit(1)


if __name__=='__main__':main()
