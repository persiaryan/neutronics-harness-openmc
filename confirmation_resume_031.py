"""Bounded restart at 031 after the retained stream incident at 030."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

import confirmation_continuation as base
from builder.context import request_setup, write_json
from builder.openmc_python import IMAGE_ID
from builder.relay import validate_request
from builder.route import condition_prompt
from prompts.prepare import build_prompt
from experiments.run import atomic_json
from evaluation.scientific.records import require

VERSION = 'confirmation-resume-031-v1'
CONTROLLER = Path(__file__).resolve()
EXPECTED_ERROR = ('HTTP 200, Content-Type: <missing>; '
                  'Unexpected event in upstream Responses stream')
read, sha, now = base.read, base.sha, base.now


def diagnose(previous, m):
    """Reconstruct only what retained metadata can establish; no provider replay."""
    folder = previous/m['rows'][29]['path']/'runs/cross_shaped_mixture'
    b = folder/'builder'
    result, upstream, manifest = (read(b/name) for name in
        ('result.json','upstream-01.json','manifest.json'))
    require(result['status']=='failed' and result['error_type']=='RuntimeError'
            and result['error']==EXPECTED_ERROR and result['request_count']==1
            and result['cleanup_confirmed'] is True
            and result['host_candidate_execution']=='not_run'
            and result['evaluator_validation']=='not_run', 'Incident signature changed')
    require(upstream['http_status']==200 and upstream['content_type']=='<missing>'
            and upstream['reader_version']=='responses-completion-deadline-v1'
            and upstream['phase']=='body' and upstream['stream_validation']=='failed'
            and upstream['completion_observed'] is False
            and upstream['stop_reason']=='invalid_stream'
            and upstream['last_event_type']=='response.completed'
            and type(upstream['response_bytes_read']) is int
            and upstream['response_bytes_read']>0
            and 'response_bytes_forwarded' not in upstream, 'Stream diagnostic changed')
    require({p.name for p in b.glob('request-*.json')}=={'request-01.json'}
            and {p.name for p in b.glob('upstream-*.json')}=={'upstream-01.json'}
            and not list(b.glob('response-*.sse'))
            and not (folder/'assessment').exists(), 'Unexpected response or assessment evidence')
    require(manifest['case']=='cross_shaped_mixture'
            and manifest['model']=='gpt-5.6-luna'
            and manifest['assistance']==base.campaign.ARMS['A']
            and manifest['mode']=='subscription'
            and (manifest['max_requests'],manifest['wall_seconds'])==(16,600)
            and manifest['image_id']==IMAGE_ID,
            'Incident assignment changed')
    for field, snapshot, source in (
        ('controller_sha256','controller-source.py','builder/run.py'),
        ('relay_sha256','relay-source.py','builder/relay.py'),
        ('entry_sha256','runtime-source.py','builder/runtime/entry.py')):
        require(manifest[field]==sha(b/snapshot)==sha(source), 'Incident implementation changed')
    body = read(b/'request-01.json')
    validate_request(body,'gpt-5.6-luna')
    setup = m['request_setups']['gpt-5.6-luna']
    require(request_setup(body)==setup==manifest['required_request_setup']
            and read(b/'setup-01.json')['matched'] is True, 'Incident request setup changed')
    prompt = condition_prompt(build_prompt('cross_shaped_mixture'),
        base.campaign.ARMS['A'],request_budget='authoring-requests-16-v1')
    require(base.region_skill.initial_context(body,prompt,base.campaign.ARMS['A']),
            'Incident prompt delivery changed')
    lifecycle = read(b/'lifecycle.json')
    require(lifecycle['state']=='removed'
            and lifecycle['container_name']==manifest['container_name'], 'Cleanup unconfirmed')
    files = {name:sha(b/name) for name in
             ('result.json','upstream-01.json','manifest.json','request-01.json',
              'setup-01.json','lifecycle.json','relay-source.py')}
    return dict(format='confirmation-030-stream-diagnosis-v1',assignment='030',
        classification='provider_adapter_stream_protocol_incident',score=None,
        model_failure_established=False, request_setup_matched=True,
        requests_consumed=1, bytes_read=upstream['response_bytes_read'],
        completed_response_validated=False, cleanup_confirmed=True,
        raw_rejected_stream_retained=False, offending_event_identified=False,
        missing_content_type_allowed_by_frozen_relay=True,
        conclusion='Frozen relay rejected the buffered response before delivery; no model assessment.',
        limits='Rejected bytes were not saved. Provider malformation versus overly strict adapter validation is unresolved.',
        action='Retain 030 as consumed unscored incident; resume at 031 without retry or relay change.',
        evidence_sha256=files)


def terminal_prefix(previous, m):
    p = read(previous/'progress.json')
    require(p['state']=='stopped' and p['reason']=='Builder incomplete; slot consumed',
            'Expected the stopped builder incident')
    rows = p['rows']
    require(len(rows)==240, 'Assignment inventory changed')
    for original,row in zip(m['rows'],rows):
        require(all(original[k]==row[k] for k in base.migration.IMMUTABLE_ROW),
                'Assignment identity or order changed')
    require([r['state'] for r in rows]==['finished']*29+['incident']+['pending']*210,
            'Consumed prefix is not exactly 001 through 030')
    require((rows[29]['id'],rows[29]['case'],rows[29]['model'],rows[29]['arm'])==
            ('030','cross_shaped_mixture','gpt-5.6-luna','A')
            and rows[29]['reason']=='Builder incomplete; slot consumed', 'Another incident')
    revised = read(base.bound(m['continuation']['revision']))
    original = read(base.bound(m['continuation']['original_manifest']))
    expected = base.prefix_rows(original,revised,Path(m['continuation']['revision']['path']).parent)
    require(rows[:12]==expected[:12], 'Migrated prefix changed')
    for row in rows[12:29]:
        value = base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
        verdict = previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'
        require(Path(row['verdict_path'])==verdict and read(verdict)==value
                and row['decision']==value['decision']
                and row['score']==value['verdict']['score']
                and row['strict_correct'] is value['verdict']['strict_correct'],
                'Consumed result contradicts reconstruction')
    require(sum(r.get('strict_correct') is True for r in rows[:29])==27
            and sum(r.get('strict_correct') is False for r in rows[:29])==2,
            'Consumed outcome counts changed')
    diagnosis = diagnose(previous,m)
    return deepcopy(rows),diagnosis


def prepare(output, previous):
    output, previous = Path(output).resolve(),Path(previous).resolve()
    require(not output.exists(), 'Resume output must be fresh')
    require(previous not in output.parents, 'Write outside previous campaign')
    proof = base.check(previous)
    m = read(previous/'manifest.json')
    rows,diagnosis = terminal_prefix(previous,m)
    before = base.migration.inventory(previous)
    output.mkdir(parents=True)
    for row in m['rows']:
        folder = previous/row['path']
        for name in base.prepared_files(folder):
            target = output/row['path']/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((folder/name).read_bytes())
    shutil.copytree(previous/'reference-reviews',output/'reference-reviews')
    write_json(output/'previous-evidence-sha256.json',before)
    write_json(output/'incident-030.json',diagnosis)
    manifest = deepcopy(m)
    manifest['resumption'] = dict(format=VERSION,created=now(),
        controller=base.binding(CONTROLLER),
        previous_manifest=base.binding(previous/'manifest.json'),
        previous_progress=base.binding(previous/'progress.json'),
        previous_launch=base.binding(previous/'continuation-launch.json'),
        previous_inventory=base.binding(output/'previous-evidence-sha256.json'),
        diagnosis=base.binding(output/'incident-030.json'),
        remaining_sessions=210,maximum_new_model_requests=3360,
        consumed_prefix_ids=[r['id'] for r in rows[:30]],
        previous_readiness=proof)
    write_json(output/'manifest.json',manifest)
    (output/'manifest.sha256').write_text(sha(output/'manifest.json')+'\n')
    write_json(output/'launch.json',dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')))
    atomic_json(output/'progress.json',dict(state='prepared_not_dispatched',rows=rows))
    require(base.migration.inventory(previous)==before, 'Previous evidence changed during preparation')
    return manifest


def check(output):
    m = read(output/'manifest.json')
    require((output/'manifest.sha256').read_text().strip()==sha(output/'manifest.json'),
            'Resume manifest changed')
    r=m['resumption']
    require(r['format']==VERSION and (r['remaining_sessions'],r['maximum_new_model_requests'])==(210,3360),
            'Resumption budget changed')
    require(base.bound(r['controller'])==CONTROLLER, 'Resume controller changed')
    previous = base.bound(r['previous_manifest']).parent
    require(base.bound(r['previous_progress'])==previous/'progress.json'
            and base.bound(r['previous_launch'])==previous/'continuation-launch.json',
            'Previous campaign binding changed')
    before=read(base.bound(r['previous_inventory']))
    require(before==base.migration.inventory(previous), 'Previous evidence changed')
    proof=base.check(previous)
    require(proof==r['previous_readiness'], 'Previous readiness changed')
    old=read(previous/'manifest.json')
    expected=deepcopy(old);expected['resumption']=r
    require(m==expected, 'Resumption changed frozen assignments or settings')
    rows,diagnosis=terminal_prefix(previous,old)
    require(read(base.bound(r['diagnosis']))==diagnosis
            and r['consumed_prefix_ids']==[x['id'] for x in rows[:30]],
            'Diagnosis or consumed prefix changed')
    for row in m['rows']:
        require(base.prepared_files(output/row['path'])==base.prepared_files(previous/row['path']),
                'Prepared inputs differ from previous campaign')
    require(read(output/'launch.json')==dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')),
        'Legacy launch protection changed')
    ready=base.campaign.check(output)
    require(ready['technical_status']=='passed', 'Runtime qualification incomplete')
    require(base.migration.inventory(previous)==before, 'Previous evidence changed during review')
    return dict(status='passed',diagnosis=diagnosis,previous_evidence_unchanged=True,
                consumed=30,scored=29,protocol_success=27,evaluated_failure=2,
                unscored_incident=1,remaining=210,maximum_new_model_requests=3360)


def fresh_progress(output,m):
    require(not (output/'resumption-launch.json').exists(), 'Resumption already consumed')
    previous=base.bound(m['resumption']['previous_manifest']).parent
    expected=read(previous/'progress.json')['rows']
    p=read(output/'progress.json')
    require(p==dict(state='prepared_not_dispatched',rows=expected), 'Resume progress not fresh')
    for row in p['rows']:
        require(not (output/row['path']/'runs').exists()
                and not (output/row['path']/'summary.json').exists(),
                'Execution evidence already present')
    return p


def dispatch(output,maximum_requests):
    output=Path(output).resolve()
    require(maximum_requests==3360,'Declare the 3360-request resumption ceiling')
    m=read(output/'manifest.json')
    progress=fresh_progress(output,m)
    readiness=check(output)
    previous=Path(m['resumption']['previous_manifest']['path']).parent
    launch=dict(format=VERSION,started=now(),output=str(output),
        manifest_sha256=sha(output/'manifest.json'),maximum_new_model_requests=3360,
        controller_sha256=sha(CONTROLLER))
    # A new sibling claim preserves every byte in the stopped segment.
    with (previous.parent/(previous.name+'-resume-031-claim.json')).open('x') as stream:
        json.dump(launch,stream,indent=2)
    write_json(output/'readiness.json',readiness)
    write_json(output/'resumption-launch.json',launch)
    progress.update(state='running',started=launch['started'])
    atomic_json(output/'progress.json',progress)
    active=None
    try:
        for row in progress['rows'][30:]:
            base.bound(m['resumption']['controller'])
            base.guard(output,m,row)
            active=row
            row.update(state='started',started=now())
            atomic_json(output/'progress.json',progress)
            value=base.assess(output,m,row)
            verdict=value['verdict']
            row.update(state='finished',finished=now(),score=verdict['score'],
                strict_correct=verdict['strict_correct'],decision=value['decision'],
                verdict_path=str(output/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'))
            active=None
            atomic_json(output/'progress.json',progress)
            print(json.dumps(dict(id=row['id'],state='finished',score=row['score'],
                                  strict_correct=row['strict_correct'])),flush=True)
        progress.update(state='complete',finished=now())
    except BaseException as exc:
        if active is not None:
            active.update(state='incident',finished=now(),reason=str(exc))
        progress.update(state='stopped',finished=now(),reason=str(exc))
        print(json.dumps(dict(state='stopped',reason=str(exc),
                              active_id=active['id'] if active else None)),flush=True)
        if not isinstance(exc,Exception):raise
    finally:
        atomic_json(output/'progress.json',progress)
    return progress


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','check','run'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous',type=Path)
    p.add_argument('--maximum-model-requests',type=int)
    a=p.parse_args()
    if a.action=='prepare':
        if not a.previous:p.error('Specify --previous')
        print(prepare(a.output,a.previous)['resumption']['format'])
    elif a.action=='check':
        print(json.dumps(check(a.output.resolve()),indent=2))
    else:
        value=dispatch(a.output,a.maximum_model_requests)
        print(value['state'])
        if value['state']!='complete':raise SystemExit(1)


if __name__=='__main__':
    main()
