"""Explicit continuation at 067; retain source-capability incident 066 unscored."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import confirmation_resume_051 as prior
from builder.context import write_json
from evaluation.benchmark_suite.suite_checks import settings_checks
from evaluator.transport_input import accepted_export
from experiments.run import atomic_json

base=prior.base
read,sha,now,require=prior.read,prior.sha,prior.now,prior.require
VERSION='confirmation-resume-067-v1'
CONTROLLER=Path(__file__).resolve()
POLICY='Explicit reviewed continuation after 066; future incident stopping unchanged.'


def domain_witness(xml):
    """Literal local geometry witness, never a general domain/source grader."""
    root=ET.fromstring(xml)
    geometry=root.find('geometry')
    require(geometry is not None,'Missing geometry')
    cell_nodes=geometry.findall('cell')
    cells={c.get('id'):c for c in cell_nodes}
    surface_nodes=geometry.findall('surface')
    surfaces={s.get('id'):s for s in surface_nodes}
    require(len(cell_nodes)==len(cells)==2 and set(cells)=={'1','2'}
            and len(surface_nodes)==len(surfaces)==7,'Unexpected cell or surface inventory')
    for id,material,region in [('1','1','1 -2 3 -4 5 -6 -7'),('2','2','1 -2 3 -4 5 -6 7')]:
        cell=cells[id]
        require(cell.get('material')==material and cell.get('region')==region
                and cell.get('universe')=='1' and cell.get('fill') is None
                and not any(k in cell.attrib for k in ('rotation','translation')),
                'Domain geometry differs from reviewed witness')
    for id,kind,coeffs in [('1','x-plane',[-2.54]),('2','x-plane',[2.54]),
            ('3','y-plane',[-2.54]),('4','y-plane',[2.54]),('5','z-plane',[-1.]),
            ('6','z-plane',[1.]),('7','z-cylinder',[0.,0.,1.27])]:
        surface=surfaces[id]
        require(surface.get('type')==kind
                and [float(v) for v in surface.get('coeffs','').split()]==coeffs,
                'Domain surface differs from reviewed witness')
    materials=root.findall('materials/material')
    nuclides={m.get('id'):{n.get('name') for n in m.findall('nuclide')} for m in materials}
    require(len(materials)==2 and nuclides=={'1':{'U235','U238'},'2':{'H1','O16'}},
            'Domain materials differ from reviewed witness')
    sources=root.findall('settings/source')
    require(len(sources)==1,'Source inventory changed')
    source=sources[0];constraints=source.find('constraints');space=source.find('space')
    require(constraints is not None and len(source.findall('constraints'))==1
            and len(constraints)==2 and not constraints.attrib
            and source.findtext('constraints/domain_type')=='cell'
            and source.findtext('constraints/domain_ids')=='1'
            and space is not None and space.get('type')=='box'
            and [float(v) for v in space.findtext('parameters','').split()]==
                [-1.27,-1.27,-1.,1.27,1.27,1.], 'Source domain differs from reviewed witness')
    return dict(selected_cell='1',selected_material='U235/U238',other_material='water H1/O16',
        cylinder_radius_cm=1.27,z_bounds_cm=[-1.,1.],
        accepted_geometric_set='source box intersect uranium cylinder',
        scope='Local XML geometry witness; no generic source-equivalence qualification.')


def diagnose(previous,m,row):
    a=previous/row['path']/'runs'/row['case']/'assessment'
    value=base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
    require(read(a/'revised-verdict.json')==value,'066 verdict changed')
    v=value['verdict'];report=read(a/'report.json')
    require(v['evidence_status']=='coherent' and v['score'] is None
            and v['strict_correct'] is False and v['diagnostic_score']['status']=='unscored'
            and v['diagnostic_score']['reason']=='Unassessed evidence: physics_settings'
            and report['status']=='assessed' and report.get('stop') is None
            and report['cleanup_confirmed'] is True,'066 is not the reviewed unscored result')
    require(all(g['passed'] is True for g in v['gates'].values())
            and v['checks']['physics_settings']==dict(physics=None,sampling=None,source=None,
                                                      entropy_mesh_and_output=None)
            and all(x is True for group,checks in v['checks'].items() for x in checks.values()
                    if group!='physics_settings'), 'Another failed or unresolved obligation')
    xml,_=accepted_export(a/'export')
    require(xml==(a/'transport/model.xml').read_bytes(),'Transport XML differs from export')
    fidelity=read(a/'export-fidelity.json')
    observed=settings_checks(row['case'],ET.fromstring(xml),read(a/'assignment.json')['sampling'])
    require(observed==fidelity['settings'],'Settings evidence changed')
    require(observed['unassessed_options']==['constraints/domain_type','constraints/domain_ids']
            and len(observed['checks'])==30
            and [c for c in observed['checks'] if c['passed'] is not True]==[
                dict(field='source_fissionable',actual=False,expected=True,passed=False)],
            'Source-capability signature changed')
    witness=domain_witness(xml)
    return dict(format='confirmation-066-capability-diagnosis-v1',assignment='066',
        classification='coherent_unscored_source_domain_capability_limit',score=None,
        cause='Domain restrictions unsupported; explicit fissionable flag not recognized; settings aggregation remains null.',
        witness=witness,
        limits='Geometric-domain correspondence only. Generic OpenMC rejection/distribution semantics require separate qualification.',
        assessed_model_failure=False,source_repaired=False,criterion_changed=False,
        cleanup_confirmed=True,native_completion_verified=True,
        settings_elementary_checks=30,settings_elementary_passes=29,
        unsupported_options=observed['unassessed_options'],
        evidence_sha256={name:sha(a/name) for name in
            ('candidate.py','report.json','review.json','revised-verdict.json','export-fidelity.json',
             'transport/model.xml','transport/openmc-process.json')},
        new_model_calls=0,new_native_transports=0,new_xml_observer_executions=0)


def terminal_prefix(previous,m):
    p=read(previous/'progress.json');rows=p['rows']
    require(p['state']=='stopped' and p['reason']==
            'Unscored evaluation incident; pause before next slot','Expected stopped 066 incident')
    require(len(rows)==240 and [r['state'] for r in rows]==
            ['finished']*29+['incident']+['finished']*8+['incident']+
            ['finished']*10+['incident']+['finished']*15+['incident']+['pending']*174,
            'Expected exactly 066 consumed assignments')
    for original,row in zip(m['rows'],rows):
        require(all(original[k]==row[k] for k in base.migration.IMMUTABLE_ROW),
                'Assignment identity or order changed')
    ancestor=base.bound(m['resumption_051']['previous_manifest']).parent
    inherited,_=prior.terminal_prefix(ancestor,read(ancestor/'manifest.json'))
    require(rows[:50]==inherited[:50],'Earlier consumed prefix changed')
    for row in rows[50:65]:
        value=base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
        path=previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'
        require(Path(row['verdict_path'])==path and read(path)==value
                and row['decision']==value['decision']
                and row['score']==value['verdict']['score']
                and row['strict_correct'] is value['verdict']['strict_correct'],
                'Consumed result contradicts reconstruction')
    row=rows[65]
    require((row['id'],row['case'],row['model'],row['arm'])==
            ('066','indc107_reflective_pin','gpt-5.6-luna','D')
            and row['reason']=='Unscored evaluation incident; pause before next slot'
            and 'score' not in row,'066 operational result changed')
    require(sum(r.get('strict_correct') is True for r in rows[:66])==57
            and sum(r.get('strict_correct') is False for r in rows[:66])==5,
            'Consumed outcome counts changed')
    return deepcopy(rows),diagnose(previous,m,row)


def prepare(output,previous):
    output,previous=Path(output).resolve(),Path(previous).resolve()
    require(not output.exists(),'Use a fresh continuation directory')
    require(previous not in output.parents,'Prepare outside previous evidence')
    proof=prior.check(previous);old=read(previous/'manifest.json')
    rows,diagnosis=terminal_prefix(previous,old)
    inventory=base.migration.inventory(previous)
    output.mkdir(parents=True)
    for row in old['rows']:
        for name in base.prepared_files(previous/row['path']):
            target=output/row['path']/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((previous/row['path']/name).read_bytes())
    shutil.copytree(previous/'reference-reviews',output/'reference-reviews')
    write_json(output/'previous-evidence-sha256.json',inventory)
    write_json(output/'incident-066.json',diagnosis)
    m=deepcopy(old)
    m['resumption_067']=dict(format=VERSION,created=now(),controller=base.binding(CONTROLLER),
        previous_manifest=base.binding(previous/'manifest.json'),
        previous_progress=base.binding(previous/'progress.json'),
        previous_launch=base.binding(previous/'resumption-051-launch.json'),
        previous_inventory=base.binding(output/'previous-evidence-sha256.json'),
        diagnosis=base.binding(output/'incident-066.json'),previous_readiness=proof,
        consumed_prefix_ids=[r['id'] for r in rows[:66]],remaining_sessions=174,
        maximum_new_model_requests=2784,original_maximum_model_requests=3840,
        retained_066_outcome='consumed_unscored',policy=POLICY,automatic_retries=0)
    write_json(output/'manifest.json',m)
    (output/'manifest.sha256').write_text(sha(output/'manifest.json')+'\n')
    write_json(output/'launch.json',dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')))
    atomic_json(output/'progress.json',dict(state='prepared_not_dispatched',rows=rows))
    require(base.migration.inventory(previous)==inventory,'Previous evidence changed')
    return m


def check(output):
    output=Path(output).resolve();m=read(output/'manifest.json');r=m['resumption_067']
    require((output/'manifest.sha256').read_text().strip()==sha(output/'manifest.json'),
            'Manifest changed')
    require(r['format']==VERSION and (r['remaining_sessions'],r['maximum_new_model_requests'],
        r['original_maximum_model_requests'],r['automatic_retries'])==(174,2784,3840,0)
        and r['retained_066_outcome']=='consumed_unscored' and r['policy']==POLICY,
        'Continuation policy or budgets changed')
    require(base.bound(r['controller'])==CONTROLLER,'Controller changed')
    previous=base.bound(r['previous_manifest']).parent
    require(base.bound(r['previous_progress'])==previous/'progress.json'
            and base.bound(r['previous_launch'])==previous/'resumption-051-launch.json',
            'Previous segment binding changed')
    inventory=read(base.bound(r['previous_inventory']))
    require(base.migration.inventory(previous)==inventory,'Previous evidence changed')
    proof=prior.check(previous);require(proof==r['previous_readiness'],'Previous readiness changed')
    old=read(previous/'manifest.json');expected=deepcopy(old);expected['resumption_067']=r
    require(m==expected,'Frozen experiment changed')
    rows,diagnosis=terminal_prefix(previous,old)
    require(r['consumed_prefix_ids']==[x['id'] for x in rows[:66]]
            and read(base.bound(r['diagnosis']))==diagnosis,'Prefix or diagnosis changed')
    for row in m['rows']:
        require(base.prepared_files(output/row['path'])==base.prepared_files(previous/row['path']),
                'Prepared inputs changed')
    require(read(output/'launch.json')==dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')),
        'Legacy launch protection changed')
    require(base.migration.inventory(previous)==inventory,'Evidence changed during check')
    return dict(status='passed',consumed=66,protocol_success=57,evaluated_failure=5,
        unscored=4,retained_039_score=None,retained_050_score=None,retained_066_score=None,pending=174,
        maximum_new_model_requests=2784,previous_evidence_files_verified=len(inventory),
        previous_evidence_unchanged=True,live_dispatched=(output/'resumption-067-launch.json').exists(),
        new_model_calls=0,new_native_transports=0)


def fresh_progress(output,m):
    require(not (output/'resumption-067-launch.json').exists(),'Continuation already consumed')
    previous=base.bound(m['resumption_067']['previous_manifest']).parent
    expected=read(previous/'progress.json')['rows'];p=read(output/'progress.json')
    require(p==dict(state='prepared_not_dispatched',rows=expected),'Progress not fresh')
    for row in p['rows']:
        require(not (output/row['path']/'runs').exists()
                and not (output/row['path']/'summary.json').exists(),'Execution already present')
    return p


def dispatch(output,maximum_requests):
    output=Path(output).resolve()
    require(maximum_requests==2784,'Declare the 2784-request continuation ceiling')
    m=read(output/'manifest.json');progress=fresh_progress(output,m);readiness=check(output)
    previous=Path(m['resumption_067']['previous_manifest']['path']).parent
    launch=dict(format=VERSION,started=now(),output=str(output),
        manifest_sha256=sha(output/'manifest.json'),maximum_new_model_requests=2784,
        controller_sha256=sha(CONTROLLER))
    with (previous.parent/(previous.name+'-resume-067-claim.json')).open('x') as stream:
        json.dump(launch,stream,indent=2)
    write_json(output/'readiness.json',readiness)
    write_json(output/'resumption-067-launch.json',launch)
    progress.update(state='running',started=launch['started']);atomic_json(output/'progress.json',progress)
    active=None
    try:
        for row in progress['rows'][66:]:
            base.bound(m['resumption_067']['controller']);base.guard(output,m,row)
            active=row;row.update(state='started',started=now());atomic_json(output/'progress.json',progress)
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
    p.add_argument('action',choices=('prepare','check','run'));p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous',type=Path);p.add_argument('--maximum-model-requests',type=int)
    a=p.parse_args()
    if a.action=='prepare':
        if not a.previous:p.error('Specify --previous')
        print(prepare(a.output,a.previous)['resumption_067']['format'])
    elif a.action=='check':print(json.dumps(check(a.output),indent=2))
    else:
        value=dispatch(a.output,a.maximum_model_requests);print(value['state'])
        if value['state']!='complete':raise SystemExit(1)


if __name__=='__main__':main()
