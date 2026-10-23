"""Resume 133–240 under a versioned deferred-diagnosis operational policy."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

import confirmation_resume_121 as prior
from builder.context import write_json
from experiments.run import atomic_json

base=prior.base
read,sha,now,require=prior.read,prior.sha,prior.now,prior.require
VERSION='confirmation-resume-133-v1'
CONTROLLER=Path(__file__).resolve()
POLICY='confirmation-deferred-anomalies-v1'
POLICY_DOCUMENT=CONTROLLER.parent/'docs/experiments/confirmation-deferred-anomalies-v1.md'
OPERATIONAL_POLICY=dict(
    version=POLICY,starts_at='133',ends_at='240',
    defer='coherent_unscored_completed_assessment_with_all_hard_gates_true',
    stop='execution_exception_or_incoherent_evidence_or_uncertain_cleanup_or_failed_guard',
    null_is_model_failure=False,replay_consumed=False,automatic_retries=0,
    evaluator_changed=False,post_campaign_diagnosis=True)
HARD_GATES={'model_builds','openmc_runs','valid_geometry','required_data',
            'finite_statepoint','required_observables'}


def classify_outcome(report,value):
    """Decide dispatch only; never alter the scientific verdict."""
    v=value['verdict']
    require(report['cleanup_confirmed'] is True,'Assessment cleanup unconfirmed')
    require(v['evidence_status']=='coherent','Evidence is not coherent; stop dispatch')
    if v['score'] is not None:
        return 'scored'
    require(report['status']=='assessed' and report.get('stop') is None
            and v['strict_correct'] is False and v['diagnostic_score']['status']=='unscored'
            and set(v['gates'])==HARD_GATES
            and all(g['passed'] is True for g in v['gates'].values())
            and any(x is None for checks in v['checks'].values() for x in checks.values()),
            'Unscored result lacks completed native execution and resolved hard gates')
    return 'deferred_unscored'


def assess(output,m,row):
    """Same authoring/final-evaluation calls as the sealed predecessor.

    Only the operator response to a coherent null verdict changes.
    """
    folder=output/row['path']
    result=base.execute(folder,request_setup=m['request_setups'][row['model']])
    require(result['tasks'][0]['builder_status']=='completed','Builder incomplete; slot consumed')
    task=folder/'runs'/row['case']
    raw,provenance=base.submission(task/'builder',row['case'])
    require(raw==(task/'candidate.py').read_bytes(),'Final submission bytes changed')
    index,reference=Path(m['data_index']['path']),m['references'][row['case']]
    baseline=base.evaluate(row['case'],task/'assessment',index=index,
        candidate=task/'candidate.py',provenance=provenance,
        evaluator_protocol=base.CONFIRMATION_PROTOCOL,reference=reference)
    require(baseline['cleanup_confirmed'] is True,'Assessment cleanup unconfirmed')
    legacy=base.review_assessment(task/'assessment',index,reference=reference)
    write_json(task/'assessment/review.json',legacy)
    revised=base.verdict_migration.revise(task/'assessment',index,reference)
    write_json(task/'assessment/revised-verdict.json',revised)
    return revised,classify_outcome(baseline,revised)


def diagnose(previous,m,row):
    """Read-only reconstruction, not a new evaluation or score."""
    a=previous/row['path']/'runs'/row['case']/'assessment'
    value=base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
    require(read(a/'revised-verdict.json')==value,'132 verdict changed')
    report=read(a/'report.json')
    require(classify_outcome(report,value)=='deferred_unscored','132 is not the retained null result')
    require(value['verdict']['checks']['geometry']['boundaries'] is None,
            '132 boundary result changed')
    return dict(format='confirmation-132-retained-diagnosis-v1',assignment='132',
        classification='coherent_unscored_completed_assessment',score=None,
        assessed_model_failure=False,source_repaired=False,criterion_changed=False,
        retained_checks=value['verdict']['checks'],
        evidence_sha256={name:sha(a/name) for name in
            ('candidate.py','report.json','review.json','revised-verdict.json','export-fidelity.json')},
        limits='Retained null verdict only; no claim of full partition equivalence with 039.',
        new_model_calls=0,new_native_transports=0,new_xml_observer_executions=0)


def terminal_prefix(previous,m):
    p=read(previous/'progress.json');rows=p['rows']
    require(p['state']=='stopped' and p['reason']==
            'Unscored evaluation incident; pause before next slot','Expected stopped 132 incident')
    require(len(rows)==240 and rows[131]['state']=='incident'
            and all(r['state']=='pending' for r in rows[132:]),'Expected exactly 132 consumed assignments')
    for original,row in zip(m['rows'],rows):
        require(all(original[k]==row[k] for k in base.migration.IMMUTABLE_ROW),
                'Assignment identity or order changed')
    ancestor=base.bound(m['resumption_121']['previous_manifest']).parent
    inherited,_=prior.terminal_prefix(ancestor,read(ancestor/'manifest.json'))
    require(rows[:120]==inherited[:120],'Earlier consumed prefix changed')
    for row in rows[120:131]:
        require(row['state']=='finished','Unexpected consumed disposition before 132')
        value=base.migration.reconstruct(previous,m,row,Path(m['data_index']['path']))
        require(read(previous/row['path']/'runs'/row['case']/'assessment/revised-verdict.json')==value,
                'Consumed verdict changed')
        require(row['score']==value['verdict']['score']
                and row['strict_correct'] is value['verdict']['strict_correct'],
                'Consumed result differs from retained verdict')
    row=rows[131]
    require((row['id'],row['case'],row['model'],row['arm'],row['repeat'])==
            ('132','wrapped_eight_pin_channel','gpt-5.6-luna','D',4)
            and row['reason']=='Unscored evaluation incident; pause before next slot'
            and 'score' not in row,'132 operational result changed')
    require(sum(r.get('strict_correct') is True for r in rows[:132])==110
            and sum(r.get('strict_correct') is False for r in rows[:132])==13
            and sum(r['state']=='incident' for r in rows[:132])==9,'Consumed outcome counts changed')
    return deepcopy(rows),diagnose(previous,m,row)


def persist(output,progress):
    """Keep unresolved assignments visible, separately from model failures."""
    items=[]
    for row in progress['rows']:
        if row['state']=='incident':
            items.append(dict(id=row['id'],case=row['case'],model=row['model'],arm=row['arm'],
                disposition=row.get('disposition','retained_historical_unscored'),
                stop_required=row.get('stop_required',False),reason=row.get('reason'),
                verdict_path=row.get('verdict_path'),score=None))
    atomic_json(output/'deferred-anomalies.json',dict(format=POLICY,policy=POLICY,
        post_campaign_review_required=True,unscored_count=len(items),rows=items))
    atomic_json(output/'progress.json',progress)


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
    write_json(output/'incident-132.json',diagnosis)
    m=deepcopy(old)
    m['resumption_133']=dict(format=VERSION,created=now(),controller=base.binding(CONTROLLER),
        previous_manifest=base.binding(previous/'manifest.json'),
        previous_progress=base.binding(previous/'progress.json'),
        previous_launch=base.binding(previous/'resumption-121-launch.json'),
        previous_inventory=base.binding(output/'previous-evidence-sha256.json'),
        diagnosis=base.binding(output/'incident-132.json'),previous_readiness=proof,
        consumed_prefix_ids=[r['id'] for r in rows[:132]],remaining_sessions=108,
        maximum_new_model_requests=1728,original_maximum_model_requests=3840,
        retained_132_outcome='consumed_unscored',policy=POLICY,policy_document=base.binding(POLICY_DOCUMENT),
        operational_policy=deepcopy(OPERATIONAL_POLICY),automatic_retries=0)
    write_json(output/'manifest.json',m)
    (output/'manifest.sha256').write_text(sha(output/'manifest.json')+'\n')
    write_json(output/'launch.json',dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')))
    persist(output,dict(state='prepared_not_dispatched',rows=rows))
    require(base.migration.inventory(previous)==inventory,'Previous evidence changed')
    return m


def check(output):
    output=Path(output).resolve();m=read(output/'manifest.json');r=m['resumption_133']
    require((output/'manifest.sha256').read_text().strip()==sha(output/'manifest.json'),
            'Manifest changed')
    require(r['format']==VERSION and (r['remaining_sessions'],r['maximum_new_model_requests'],
        r['original_maximum_model_requests'],r['automatic_retries'])==(108,1728,3840,0)
        and r['retained_132_outcome']=='consumed_unscored' and r['policy']==POLICY
        and r['operational_policy']==OPERATIONAL_POLICY
        and base.bound(r['policy_document'])==POLICY_DOCUMENT,
        'Continuation policy or budgets changed')
    require(base.bound(r['controller'])==CONTROLLER,'Controller changed')
    previous=base.bound(r['previous_manifest']).parent
    require(base.bound(r['previous_progress'])==previous/'progress.json'
            and base.bound(r['previous_launch'])==previous/'resumption-121-launch.json',
            'Previous segment binding changed')
    inventory=read(base.bound(r['previous_inventory']))
    require(base.migration.inventory(previous)==inventory,'Previous evidence changed')
    proof=prior.check(previous);require(proof==r['previous_readiness'],'Previous readiness changed')
    old=read(previous/'manifest.json');expected=deepcopy(old);expected['resumption_133']=r
    require(m==expected,'Frozen experiment changed')
    rows,diagnosis=terminal_prefix(previous,old)
    require(r['consumed_prefix_ids']==[x['id'] for x in rows[:132]]
            and read(base.bound(r['diagnosis']))==diagnosis,'Prefix or diagnosis changed')
    for row in m['rows']:
        require(base.prepared_files(output/row['path'])==base.prepared_files(previous/row['path']),
                'Prepared inputs changed')
    require(read(output/'launch.json')==dict(format=VERSION,dispatched=False,
        required_entrypoint=CONTROLLER.name,manifest_sha256=sha(output/'manifest.json')),
        'Legacy launch protection changed')
    require(base.migration.inventory(previous)==inventory,'Evidence changed during check')
    return dict(status='passed',consumed=132,protocol_success=110,evaluated_failure=13,
        unscored=9,retained_039_score=None,retained_050_score=None,retained_066_score=None,retained_117_score=None,retained_118_score=None,retained_119_score=None,retained_120_score=None,retained_132_score=None,pending=108,
        maximum_new_model_requests=1728,previous_evidence_files_verified=len(inventory),
        previous_evidence_unchanged=True,live_dispatched=(output/'resumption-133-launch.json').exists(),
        new_model_calls=0,new_native_transports=0)


def fresh_progress(output,m):
    require(not (output/'resumption-133-launch.json').exists(),'Continuation already consumed')
    previous=base.bound(m['resumption_133']['previous_manifest']).parent
    expected=read(previous/'progress.json')['rows'];p=read(output/'progress.json')
    require(p==dict(state='prepared_not_dispatched',rows=expected),'Progress not fresh')
    for row in p['rows']:
        require(not (output/row['path']/'runs').exists()
                and not (output/row['path']/'summary.json').exists(),'Execution already present')
    return p


def dispatch(output,maximum_requests):
    output=Path(output).resolve()
    require(maximum_requests==1728,'Declare the 1728-request continuation ceiling')
    m=read(output/'manifest.json');progress=fresh_progress(output,m);readiness=check(output)
    previous=Path(m['resumption_133']['previous_manifest']['path']).parent
    launch=dict(format=VERSION,started=now(),output=str(output),
        manifest_sha256=sha(output/'manifest.json'),maximum_new_model_requests=1728,
        controller_sha256=sha(CONTROLLER),operational_policy=POLICY,
        policy_document_sha256=sha(POLICY_DOCUMENT))
    with (previous.parent/(previous.name+'-resume-133-claim.json')).open('x') as stream:
        json.dump(launch,stream,indent=2)
    write_json(output/'readiness.json',readiness)
    write_json(output/'resumption-133-launch.json',launch)
    progress.update(state='running',started=launch['started']);atomic_json(output/'progress.json',progress)
    active=None
    try:
        for row in progress['rows'][132:]:
            base.bound(m['resumption_133']['controller'])
            base.bound(m['resumption_133']['policy_document']);base.guard(output,m,row)
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
        print(prepare(a.output,a.previous)['resumption_133']['format'])
    elif a.action=='check':print(json.dumps(check(a.output),indent=2))
    else:
        value=dispatch(a.output,a.maximum_model_requests);print(value['state'])
        if value['state']!='complete':raise SystemExit(1)


if __name__=='__main__':main()
