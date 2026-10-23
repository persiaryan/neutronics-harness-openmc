"""Explicit final continuation at 237; preserve provider/relay incident 236."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

import confirmation_resume_133 as prior
from builder import openmc_python, region_skill
from builder.context import request_setup, request_inventory, sha256, write_json
from builder.relay import validate_request
from builder.route import condition_prompt, CONDITIONS
from builder.run import verify_container
from prompts.prepare import build_prompt
from experiments.run import atomic_json

base=prior.base
read,sha,now,require=prior.read,prior.sha,prior.now,prior.require
VERSION='confirmation-resume-237-v1'
CONTROLLER=Path(__file__).resolve()
POLICY=prior.POLICY
POLICY_DOCUMENT=prior.POLICY_DOCUMENT
OPERATIONAL_POLICY=prior.OPERATIONAL_POLICY
assess=prior.assess
persist=prior.persist
EXPECTED_ERROR='HTTP 200, Content-Type: <missing>; Upstream reported error; response body not forwarded'


def diagnose(previous,m,row):
    """Qualify retained execution metadata, without retry or assessment."""
    folder=previous/row['path']/'runs'/row['case'];b=folder/'builder'
    result,upstream,manifest=(read(b/name) for name in
        ('result.json','upstream-06.json','manifest.json'))
    require(result['status']=='failed' and result['error_type']=='RuntimeError'
            and result['error']==EXPECTED_ERROR and result['request_count']==6
            and result['cleanup_confirmed'] is True
            and result['host_candidate_execution']=='not_run'
            and result['evaluator_validation']=='not_run','236 incident signature changed')
    require(upstream['reader_version']=='responses-completion-deadline-v1'
            and upstream['http_status']==200 and upstream['content_type']=='<missing>'
            and upstream['stream_validation']=='failed' and upstream['completion_observed'] is False
            and upstream['phase']=='body' and upstream['stop_reason']=='invalid_stream'
            and upstream['last_event_type']=='error' and upstream['response_bytes_read']==34210
            and 'response_bytes_forwarded' not in upstream,'236 stream metadata changed')
    require({p.name for p in b.glob('request-*.json')}==
            {f'request-{i:02d}.json' for i in range(1,7)}
            and {p.name for p in b.glob('upstream-*.json')}==
            {f'upstream-{i:02d}.json' for i in range(1,7)}
            and {p.name for p in b.glob('response-*.sse')}==
            {f'response-{i:02d}.sse' for i in range(1,6)}
            and not (folder/'assessment').exists()
            and not (folder/'candidate.py').exists(),'236 response or assessment inventory changed')
    assistance=base.campaign.ARMS['D']
    require(manifest['case']=='cylindrical_void_sleeve'
            and manifest['model']=='gpt-5.6-sol' and manifest['assistance']==assistance
            and manifest['condition']==CONDITIONS[assistance] and manifest['mode']=='subscription'
            and (manifest['max_requests'],manifest['wall_seconds'])==(16,600)
            and manifest['request_budget_profile']=='authoring-requests-16-v1'
            and manifest['image_id']==openmc_python.IMAGE_ID,'236 assignment changed')
    for field,snapshot,source in (
        ('controller_sha256','controller-source.py','builder/run.py'),
        ('relay_sha256','relay-source.py','builder/relay.py'),
        ('entry_sha256','runtime-source.py','builder/runtime/entry.py')):
        require(manifest[field]==sha(b/snapshot)==sha(source),'236 implementation changed')
    info=read(b/'container.json')
    verify_container(info,openmc_python.IMAGE_ID);openmc_python.verify_image(info,True)
    openmc_python.verify_probe(read(b/'environment-probe.json'),True)
    region_skill.verify(b,manifest,assistance)
    prompt=condition_prompt(build_prompt(row['case']),assistance,
                            request_budget='authoring-requests-16-v1')
    require((b/'prompt.txt').read_bytes()==prompt.encode()
            and manifest['prompt_sha256']==sha256(prompt.encode()),'236 prompt changed')
    setup=m['request_setups']['gpt-5.6-sol']
    require(manifest['required_request_setup']==setup,'236 required setup changed')
    for i in range(1,7):
        body=read(b/f'request-{i:02d}.json')
        validate_request(body,'gpt-5.6-sol')
        require(request_setup(body)==setup and read(b/f'setup-{i:02d}.json')==
                dict(matched=True,expected_sha256=sha256(json.dumps(setup,sort_keys=True).encode()))
                and request_inventory(body)==read(b/f'inventory-{i:02d}.json'),
                '236 request setup or inventory changed')
        if i==1:
            require(region_skill.initial_context(body,prompt,assistance),
                    '236 preloaded procedure delivery changed')
        if i<6:
            completed=read(b/f'upstream-{i:02d}.json')
            require(completed['stream_validation']=='passed'
                    and completed['completion_observed'] is True
                    and completed['last_event_type']=='response.completed'
                    and completed['response_bytes_forwarded']==len((b/f'response-{i:02d}.sse').read_bytes()),
                    'Earlier completed response changed')
    life=read(b/'lifecycle.json')
    require(life['state']=='removed' and life['container_name']==manifest['container_name']
            and life['container_id']==info['Id'],'236 cleanup not confirmed')
    return dict(format='confirmation-236-stream-diagnosis-v1',assignment='236',
        classification='provider_adapter_stream_error_before_final_submission',score=None,
        model_failure_established=False,requests_consumed=6,
        completed_responses=5,rejected_response_bytes_read=34210,
        rejected_response_completed=False,raw_rejected_stream_retained=False,
        cleanup_confirmed=True,assessment_executed=False,source_repaired=False,
        limits='Retained event type is error; rejected raw bytes are absent, so exact provider/relay root cause is unresolved.',
        action='Preserve 236 consumed and unscored; no retry or adapter change; start at 237.',
        evidence_sha256=base.migration.inventory(b),
        new_model_calls=0,new_native_transports=0,new_xml_observer_executions=0)


def terminal_prefix(previous,m):
    p=read(previous/'progress.json');rows=p['rows']
    require(p['state']=='stopped' and p['reason']=='Builder incomplete; slot consumed',
            'Expected stopped builder incident 236')
    require(len(rows)==240 and rows[235]['state']=='incident'
            and all(r['state']=='pending' for r in rows[236:]),
            'Expected exactly 236 consumed assignments')
    for original,row in zip(m['rows'],rows):
        require(all(original[k]==row[k] for k in base.migration.IMMUTABLE_ROW),
                'Assignment identity or order changed')
    ancestor=base.bound(m['resumption_133']['previous_manifest']).parent
    inherited,_=prior.terminal_prefix(ancestor,read(ancestor/'manifest.json'))
    require(rows[:132]==inherited[:132],'Earlier consumed prefix changed')
    for row in rows[132:235]:
        require(row['state']=='finished' or row.get('disposition')=='deferred_unscored',
                'Unexpected earlier blocking incident')
        a=previous/row['path']/'runs'/row['case']/'assessment'
        value=base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
        require(read(a/'revised-verdict.json')==value
                and Path(row['verdict_path'])==a/'revised-verdict.json'
                and row['decision']==value['decision'],'Consumed verdict identity changed')
        disposition=prior.classify_outcome(read(a/'report.json'),value)
        if row['state']=='finished':
            require(disposition=='scored' and row['score']==value['verdict']['score']
                    and row['strict_correct'] is value['verdict']['strict_correct'],
                    'Consumed scored result changed')
        else:
            require(disposition=='deferred_unscored' and row['score'] is None
                    and row['strict_correct'] is None and row['stop_required'] is False,
                    'Deferred null result changed')
    row=rows[235]
    require((row['id'],row['case'],row['model'],row['arm'],row['repeat'])==
            ('236','cylindrical_void_sleeve','gpt-5.6-sol','D',5)
            and row['reason']=='Builder incomplete; slot consumed'
            and row.get('disposition')=='blocking_incident' and row.get('stop_required') is True
            and 'score' not in row,'236 operational result changed')
    require(sum(r.get('strict_correct') is True for r in rows[:236])==199
            and sum(r.get('strict_correct') is False for r in rows[:236])==19
            and sum(r['state']=='incident' for r in rows[:236])==18,
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
    write_json(output/'incident-236.json',diagnosis)
    m=deepcopy(old)
    m['resumption_237']=dict(format=VERSION,created=now(),controller=base.binding(CONTROLLER),
        previous_manifest=base.binding(previous/'manifest.json'),
        previous_progress=base.binding(previous/'progress.json'),
        previous_launch=base.binding(previous/'resumption-133-launch.json'),
        previous_inventory=base.binding(output/'previous-evidence-sha256.json'),
        diagnosis=base.binding(output/'incident-236.json'),previous_readiness=proof,
        consumed_prefix_ids=[r['id'] for r in rows[:236]],remaining_sessions=4,
        maximum_new_model_requests=64,original_maximum_model_requests=3840,
        retained_236_outcome='consumed_unscored',policy=POLICY,policy_document=base.binding(POLICY_DOCUMENT),
        operational_policy=deepcopy(OPERATIONAL_POLICY),automatic_retries=0)
    write_json(output/'manifest.json',m)
    (output/'manifest.sha256').write_text(sha(output/'manifest.json')+'\n')
    write_json(output/'launch.json',dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')))
    persist(output,dict(state='prepared_not_dispatched',rows=rows))
    require(base.migration.inventory(previous)==inventory,'Previous evidence changed')
    return m


def check(output):
    output=Path(output).resolve();m=read(output/'manifest.json');r=m['resumption_237']
    require((output/'manifest.sha256').read_text().strip()==sha(output/'manifest.json'),
            'Manifest changed')
    require(r['format']==VERSION and (r['remaining_sessions'],r['maximum_new_model_requests'],
        r['original_maximum_model_requests'],r['automatic_retries'])==(4,64,3840,0)
        and r['retained_236_outcome']=='consumed_unscored' and r['policy']==POLICY
        and r['operational_policy']==OPERATIONAL_POLICY
        and base.bound(r['policy_document'])==POLICY_DOCUMENT,
        'Continuation policy or budgets changed')
    require(base.bound(r['controller'])==CONTROLLER,'Controller changed')
    previous=base.bound(r['previous_manifest']).parent
    require(base.bound(r['previous_progress'])==previous/'progress.json'
            and base.bound(r['previous_launch'])==previous/'resumption-133-launch.json',
            'Previous segment binding changed')
    inventory=read(base.bound(r['previous_inventory']))
    require(base.migration.inventory(previous)==inventory,'Previous evidence changed')
    proof=prior.check(previous);require(proof==r['previous_readiness'],'Previous readiness changed')
    old=read(previous/'manifest.json');expected=deepcopy(old);expected['resumption_237']=r
    require(m==expected,'Frozen experiment changed')
    rows,diagnosis=terminal_prefix(previous,old)
    require(r['consumed_prefix_ids']==[x['id'] for x in rows[:236]]
            and read(base.bound(r['diagnosis']))==diagnosis,'Prefix or diagnosis changed')
    for row in m['rows']:
        require(base.prepared_files(output/row['path'])==base.prepared_files(previous/row['path']),
                'Prepared inputs changed')
    require(read(output/'launch.json')==dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')),
        'Legacy launch protection changed')
    require(base.migration.inventory(previous)==inventory,'Evidence changed during check')
    return dict(status='passed',consumed=236,protocol_success=199,evaluated_failure=19,
        unscored=18,retained_039_score=None,retained_050_score=None,retained_066_score=None,retained_117_score=None,retained_118_score=None,retained_119_score=None,retained_120_score=None,retained_132_score=None,retained_236_score=None,pending=4,
        maximum_new_model_requests=64,previous_evidence_files_verified=len(inventory),
        previous_evidence_unchanged=True,live_dispatched=(output/'resumption-237-launch.json').exists(),
        new_model_calls=0,new_native_transports=0)


def fresh_progress(output,m):
    require(not (output/'resumption-237-launch.json').exists(),'Continuation already consumed')
    previous=base.bound(m['resumption_237']['previous_manifest']).parent
    expected=read(previous/'progress.json')['rows'];p=read(output/'progress.json')
    require(p==dict(state='prepared_not_dispatched',rows=expected),'Progress not fresh')
    for row in p['rows']:
        require(not (output/row['path']/'runs').exists()
                and not (output/row['path']/'summary.json').exists(),'Execution already present')
    return p


def dispatch(output,maximum_requests):
    output=Path(output).resolve()
    require(maximum_requests==64,'Declare the 64-request continuation ceiling')
    m=read(output/'manifest.json');progress=fresh_progress(output,m);readiness=check(output)
    previous=Path(m['resumption_237']['previous_manifest']['path']).parent
    launch=dict(format=VERSION,started=now(),output=str(output),
        manifest_sha256=sha(output/'manifest.json'),maximum_new_model_requests=64,
        controller_sha256=sha(CONTROLLER),operational_policy=POLICY,
        policy_document_sha256=sha(POLICY_DOCUMENT))
    with (previous.parent/(previous.name+'-resume-237-claim.json')).open('x') as stream:
        json.dump(launch,stream,indent=2)
    write_json(output/'readiness.json',readiness)
    write_json(output/'resumption-237-launch.json',launch)
    progress.update(state='running',started=launch['started']);atomic_json(output/'progress.json',progress)
    active=None
    try:
        for row in progress['rows'][236:]:
            base.bound(m['resumption_237']['controller'])
            base.bound(m['resumption_237']['policy_document']);base.guard(output,m,row)
            active=row;row.update(state='started',started=now());atomic_json(output/'progress.json',progress)
            value,disposition=assess(output,m,row)
            require(disposition in ('scored','deferred_unscored'),'Unknown operational disposition')
            v=value['verdict']
            row.update(finished=now(),decision=value['decision'],
                verdict_path=str(output/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'))
            if disposition=='scored':
                row.update(state='finished',score=v['score'],strict_correct=v['strict_correct'])
            else:
                row.update(state='incident',score=None,strict_correct=None,
                    disposition='deferred_unscored',stop_required=False,
                    reason='Coherent unscored assessment; diagnosis deferred under '+POLICY,
                    review_status='pending_post_campaign_diagnosis')
            active=None
            persist(output,progress)
            print(json.dumps(dict(id=row['id'],state=row['state'],score=row['score'],
                strict_correct=row['strict_correct'],disposition=disposition)),flush=True)
        progress.update(state='complete',finished=now(),post_campaign_review_required=True)
    except BaseException as exc:
        if active is not None:active.update(state='incident',finished=now(),reason=str(exc),
            disposition='blocking_incident',stop_required=True)
        progress.update(state='stopped',finished=now(),reason=str(exc))
        if not isinstance(exc,Exception):raise
    finally:persist(output,progress)
    return progress


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','check','run'));p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous',type=Path);p.add_argument('--maximum-model-requests',type=int)
    a=p.parse_args()
    if a.action=='prepare':
        if not a.previous:p.error('Specify --previous')
        print(prepare(a.output,a.previous)['resumption_237']['format'])
    elif a.action=='check':print(json.dumps(check(a.output),indent=2))
    else:
        value=dispatch(a.output,a.maximum_model_requests);print(value['state'])
        if value['state']!='complete':raise SystemExit(1)


if __name__=='__main__':main()
