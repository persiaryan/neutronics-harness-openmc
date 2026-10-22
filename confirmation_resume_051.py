"""Explicit continuation after consumed unscored 050; preparation never dispatches."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import confirmation_resume_040 as prior
from builder.context import write_json
from evaluation.scientific import boundaries
from evaluator.transport_input import accepted_export
from experiments.run import atomic_json

base=prior.base
read,sha,now,require=prior.read,prior.sha,prior.now,prior.require
VERSION='confirmation-resume-051-v1'
CONTROLLER=Path(__file__).resolve()
POLICY='Explicit reviewed continuation after 050; future incident stopping unchanged.'


def geometry_signature(xml):
    """Geometry only; effective temperatures are checked independently."""
    g=ET.fromstring(xml).find('geometry')
    require(g is not None,'Missing geometry')
    return dict(
        surfaces={s.get('id'):{k:v for k,v in s.attrib.items() if k!='name'}
                  for s in g.findall('surface')},
        cells={c.get('id'):{k:v for k,v in c.attrib.items() if k not in ('name','temperature')}
               for c in g.findall('cell')})


def observation_signature(observation):
    value=deepcopy(observation)
    value.pop('model_xml_sha256',None)
    value['coverage']['analysis'].pop('elapsed_seconds',None)
    return value


def diagnose(previous,m,row):
    a=previous/row['path']/'runs'/row['case']/'assessment'
    value=base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
    require(read(a/'revised-verdict.json')==value,'050 verdict changed')
    v=value['verdict'];report=read(a/'report.json')
    require(v['evidence_status']=='coherent' and v['score'] is None
            and v['strict_correct'] is False and v['diagnostic_score']['status']=='unscored'
            and report['status']=='assessed' and report.get('stop') is None
            and report['cleanup_confirmed'] is True,'050 is not the reviewed unscored result')
    require(all(g['passed'] is True for g in v['gates'].values())
            and v['checks']['geometry']['boundaries'] is None
            and all(x is True for group,cs in v['checks'].items() for name,x in cs.items()
                    if (group,name)!=('geometry','boundaries')),
            'Another failed or unresolved obligation')
    ancestor=base.bound(m['resumption_040']['previous_manifest']).parent
    older=ancestor/m['rows'][38]['path']/'runs/wrapped_eight_pin_channel/assessment'
    # The old controller reconstructs the original 039 certificate independently.
    original=prior.diagnose(ancestor,read(ancestor/'manifest.json'),m['rows'][38])
    xml,_=accepted_export(a/'export');old_xml,_=accepted_export(older/'export')
    require(geometry_signature(xml)==geometry_signature(old_xml),'050 geometry differs from reviewed 039')
    image=read(a/'export-boundaries/manifest.json')['image_id']
    observation=boundaries.record(a/'export-boundaries',xml,image=image)
    old_observation=boundaries.record(older/'export-boundaries',old_xml,image=image)
    require(observation_signature(observation)==observation_signature(old_observation),
            '050 boundary observation differs from reviewed 039')
    return dict(format='confirmation-050-capability-diagnosis-v1',assignment='050',
        classification='coherent_unscored_boundary_abstraction_limit',score=None,
        same_geometry_as_039=True,same_boundary_observation_as_039=True,
        ignored_geometry_metadata=['cell/surface names','separately checked effective cell temperatures'],
        witness=original['witness'],cause=original['cause'],
        limits=original['limits'],boundary_assertions_indeterminate=12,
        assessed_model_failure=False,source_repaired=False,criterion_changed=False,
        cleanup_confirmed=True,native_completion_verified=True,
        evidence_sha256={name:sha(a/name) for name in
            ('candidate.py','report.json','review.json','revised-verdict.json',
             'export-boundaries/stdout.json','export-boundaries/worker.py')},
        new_model_calls=0,new_native_transports=0,new_xml_observer_executions=0)


def terminal_prefix(previous,m):
    p=read(previous/'progress.json');rows=p['rows']
    require(p['state']=='stopped' and p['reason']==
            'Unscored evaluation incident; pause before next slot','Expected stopped 050 incident')
    require(len(rows)==240 and [r['state'] for r in rows]==
            ['finished']*29+['incident']+['finished']*8+['incident']+
            ['finished']*10+['incident']+['pending']*190,'Expected exactly 050 consumed assignments')
    for original,row in zip(m['rows'],rows):
        require(all(original[k]==row[k] for k in base.migration.IMMUTABLE_ROW),
                'Assignment identity or order changed')
    ancestor=base.bound(m['resumption_040']['previous_manifest']).parent
    inherited,_=prior.terminal_prefix(ancestor,read(ancestor/'manifest.json'))
    require(rows[:39]==inherited[:39],'Earlier consumed prefix changed')
    for row in rows[39:49]:
        value=base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
        path=previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'
        require(Path(row['verdict_path'])==path and read(path)==value
                and row['decision']==value['decision']
                and row['score']==value['verdict']['score']
                and row['strict_correct'] is value['verdict']['strict_correct'],
                'Consumed result contradicts reconstruction')
    row=rows[49]
    require((row['id'],row['case'],row['model'],row['arm'])==
            ('050','wrapped_eight_pin_channel','gpt-5.6-sol','A')
            and row['reason']=='Unscored evaluation incident; pause before next slot'
            and 'score' not in row,'050 operational result changed')
    require(sum(r.get('strict_correct') is True for r in rows[:50])==43
            and sum(r.get('strict_correct') is False for r in rows[:50])==4,
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
    write_json(output/'incident-050.json',diagnosis)
    m=deepcopy(old)
    m['resumption_051']=dict(format=VERSION,created=now(),controller=base.binding(CONTROLLER),
        previous_manifest=base.binding(previous/'manifest.json'),
        previous_progress=base.binding(previous/'progress.json'),
        previous_launch=base.binding(previous/'resumption-040-launch.json'),
        previous_inventory=base.binding(output/'previous-evidence-sha256.json'),
        diagnosis=base.binding(output/'incident-050.json'),previous_readiness=proof,
        consumed_prefix_ids=[r['id'] for r in rows[:50]],remaining_sessions=190,
        maximum_new_model_requests=3040,original_maximum_model_requests=3840,
        retained_050_outcome='consumed_unscored',policy=POLICY,automatic_retries=0)
    write_json(output/'manifest.json',m)
    (output/'manifest.sha256').write_text(sha(output/'manifest.json')+'\n')
    write_json(output/'launch.json',dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')))
    atomic_json(output/'progress.json',dict(state='prepared_not_dispatched',rows=rows))
    require(base.migration.inventory(previous)==inventory,'Previous evidence changed')
    return m


def check(output):
    output=Path(output).resolve();m=read(output/'manifest.json');r=m['resumption_051']
    require((output/'manifest.sha256').read_text().strip()==sha(output/'manifest.json'),
            'Manifest changed')
    require(r['format']==VERSION and (r['remaining_sessions'],r['maximum_new_model_requests'],
        r['original_maximum_model_requests'],r['automatic_retries'])==(190,3040,3840,0)
        and r['retained_050_outcome']=='consumed_unscored' and r['policy']==POLICY,
        'Continuation policy or budgets changed')
    require(base.bound(r['controller'])==CONTROLLER,'Controller changed')
    previous=base.bound(r['previous_manifest']).parent
    require(base.bound(r['previous_progress'])==previous/'progress.json'
            and base.bound(r['previous_launch'])==previous/'resumption-040-launch.json',
            'Previous segment binding changed')
    inventory=read(base.bound(r['previous_inventory']))
    require(base.migration.inventory(previous)==inventory,'Previous evidence changed')
    proof=prior.check(previous);require(proof==r['previous_readiness'],'Previous readiness changed')
    old=read(previous/'manifest.json');expected=deepcopy(old);expected['resumption_051']=r
    require(m==expected,'Frozen experiment changed')
    rows,diagnosis=terminal_prefix(previous,old)
    require(r['consumed_prefix_ids']==[x['id'] for x in rows[:50]]
            and read(base.bound(r['diagnosis']))==diagnosis,'Prefix or diagnosis changed')
    for row in m['rows']:
        require(base.prepared_files(output/row['path'])==base.prepared_files(previous/row['path']),
                'Prepared inputs changed')
    require(read(output/'launch.json')==dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')),
        'Legacy launch protection changed')
    require(base.migration.inventory(previous)==inventory,'Evidence changed during check')
    return dict(status='passed',consumed=50,protocol_success=43,evaluated_failure=4,
        unscored=3,retained_039_score=None,retained_050_score=None,pending=190,
        maximum_new_model_requests=3040,previous_evidence_files_verified=len(inventory),
        previous_evidence_unchanged=True,live_dispatched=(output/'resumption-051-launch.json').exists(),
        new_model_calls=0,new_native_transports=0)


def fresh_progress(output,m):
    require(not (output/'resumption-051-launch.json').exists(),'Continuation already consumed')
    previous=base.bound(m['resumption_051']['previous_manifest']).parent
    expected=read(previous/'progress.json')['rows'];p=read(output/'progress.json')
    require(p==dict(state='prepared_not_dispatched',rows=expected),'Progress not fresh')
    for row in p['rows']:
        require(not (output/row['path']/'runs').exists()
                and not (output/row['path']/'summary.json').exists(),'Execution already present')
    return p


def dispatch(output,maximum_requests):
    output=Path(output).resolve()
    require(maximum_requests==3040,'Declare the 3040-request continuation ceiling')
    m=read(output/'manifest.json');progress=fresh_progress(output,m);readiness=check(output)
    previous=Path(m['resumption_051']['previous_manifest']['path']).parent
    launch=dict(format=VERSION,started=now(),output=str(output),
        manifest_sha256=sha(output/'manifest.json'),maximum_new_model_requests=3040,
        controller_sha256=sha(CONTROLLER))
    with (previous.parent/(previous.name+'-resume-051-claim.json')).open('x') as stream:
        json.dump(launch,stream,indent=2)
    write_json(output/'readiness.json',readiness)
    write_json(output/'resumption-051-launch.json',launch)
    progress.update(state='running',started=launch['started']);atomic_json(output/'progress.json',progress)
    active=None
    try:
        for row in progress['rows'][50:]:
            base.bound(m['resumption_051']['controller']);base.guard(output,m,row)
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
        print(prepare(a.output,a.previous)['resumption_051']['format'])
    elif a.action=='check':print(json.dumps(check(a.output),indent=2))
    else:
        value=dispatch(a.output,a.maximum_model_requests);print(value['state'])
        if value['state']!='complete':raise SystemExit(1)


if __name__=='__main__':main()
