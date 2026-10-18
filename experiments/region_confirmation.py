"""Prepare/check/analyze the new A/D suite. Live dispatch is separately budgeted."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import shutil

from builder import region_skill
from builder.context import write_json
from builder.submission import submission
from evaluation.confirmation import cases, references
from evaluation.candidates.run import evaluate
from evaluation.candidates.verify import review_assessment
from evaluation.scientific.records import require
from evaluator.profiles import CONFIRMATION_PROTOCOL
from experiments import dashboard_campaign as historical
from experiments.run import prepare as prepare_session, execute, atomic_json
from prompts.confirmation import TASKS, suite

MODELS=historical.MODELS
ARMS=historical.REGION_ARMS


def now():
    return datetime.now(timezone.utc).isoformat()


def reference_index(path):
    value=references.read(path)
    require(isinstance(value,dict) and set(value)<=set(TASKS),'Unknown reference index')
    return value


def end_to_end(index_file, output, data_index, selected):
    mapping=reference_index(index_file)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for case in selected:
        require(case in mapping,'Reference missing from index')
        package=Path(mapping[case])
        from experiments.confirmation_reference_review import review as review_reference
        proof=review_reference(case,package,data_index)
        write_json(output/(case+'-reference-review.json'),proof)
        folder=output/case
        result=evaluate(case,folder,index=data_index,candidate=package/'reference.py',
                        evaluator_protocol=CONFIRMATION_PROTOCOL,reference=package)
        review=review_assessment(folder,data_index,reference=package)
        write_json(folder/'review.json',review)
        rows.append(dict(case=case,assessment_path=str(folder.resolve()),status=result['status'],evidence_status=review['evidence_status'],
            score=review.get('score'),strict_correct=review.get('strict_correct'),
            report_sha256=historical.sha(folder/'report.json'),reference_manifest_sha256=historical.sha(package/'manifest.json')))
        write_json(output/'report.json',dict(format='confirmation-end-to-end-v1',provider_calls=0,
            evaluator_identity=references.identity(),rows=rows,
            status='passed' if all(r['evidence_status']=='coherent' and r['strict_correct'] is True for r in rows) else 'failed'))
        print(json.dumps(rows[-1]),flush=True)
    return rows


def prepare(output, index_file, data_index, setups_file, controls_file, end_to_end_file):
    output=Path(output)
    require(not output.exists(),'Use a fresh confirmation directory')
    mapping=reference_index(index_file)
    require(set(mapping)==set(TASKS),'Twelve references must be assigned, including unavailable ones explicitly')
    setups=references.read(setups_file)
    require(set(setups)==set(MODELS),'Declare both matched model configurations')
    for model,setup in setups.items():
        require(setup.get('request_configuration',{}).get('reasoning',{}).get('effort')==
                ('medium' if 'luna' in model else 'low'),'Unexpected model reasoning configuration')
    output.mkdir(parents=True)
    states={}
    for case in TASKS:
        try:
            goal=references.target(case,mapping[case],None)
            from experiments.confirmation_reference_review import review as review_reference
            proof=review_reference(case,mapping[case],Path(data_index))
            audit=output/'reference-reviews'/(case+'.json');audit.parent.mkdir(exist_ok=True)
            write_json(audit,proof)
            states[case]=dict(status='qualified',manifest_sha256=goal['index']['manifest_sha256'],
                             review_sha256=historical.sha(audit))
        except (ValueError,OSError,KeyError,RuntimeError) as exc:
            states[case]=dict(status='blocked',reason=str(exc))
    assignments=[(m,a,c,r) for c in TASKS for m in MODELS for a in ARMS for r in range(1,6)]
    random.Random(20261018).shuffle(assignments)
    rows=[]
    for number,(model,arm,case,repeat) in enumerate(assignments,1):
        path=f'runs/{number:03d}-{case}-{model}-{arm}-r{repeat}'
        folder=output/path
        prepare_session(folder,assistance=ARMS[arm],model=model,cases=[case],
                        request_budget='authoring-requests-16-v1')
        rows.append(dict(id=f'{number:03d}',model=model,arm=arm,case=case,repeat=repeat,path=path,
            state='pending',plan_sha256=historical.sha(folder/'plan.json')))
    binding=lambda p:dict(path=str(Path(p).resolve()),sha256=historical.sha(p))
    manifest=dict(format='region-confirmation-campaign-v1',created=now(),comparison='region-ownership-confirmation-ad-v1',
        suite_manifest_sha256=suite()[1],skill=region_skill.material()[1],source_sha256=historical.sources(),
        evaluator_identity=references.identity(),protocol_sha256=historical.sha(references.PROTOCOL),
        data_index=binding(data_index),request_setups=setups,references={c:str(Path(p).resolve()) for c,p in mapping.items()},
        reference_states=states,controls=binding(controls_file),end_to_end=binding(end_to_end_file),
        sessions=240,maximum_model_requests=3840,authoring_seconds=600,automatic_retries=0,
        shuffle_seed=20261018,rows=rows,grading_enabled=False,scientific_review='pending_owner_review',
        sample_size_justification='pending: 12 tasks x 2 setups x A/D x 5 repeats is a proposed inventory, not a power guarantee',
        primary='Complete independently verified protocol success; all assigned denominator',
        secondary='Source-adjudicated damaging shared-region mutation; pending labels are not negatives',
        mechanism_definition=references.read(Path('experiments/region_ad_protocol.json'))['secondary'],
        analysis='Report per-task/model and equal-task-weight differences; repeated generations are nested within task.',
        provider_qualification='pending_separate_budgeted_controls')
    write_json(output/'manifest.json',manifest)
    (output/'manifest.sha256').write_text(historical.sha(output/'manifest.json')+'\n')
    write_json(output/'progress.json',dict(state='prepared_not_dispatched',rows=rows))
    annotations=dict(format='confirmation-mechanism-annotations-v1',campaign_manifest_sha256=historical.sha(output/'manifest.json'),
        records=[dict(id=r['id'],status='pending',reviewer=None,reviewer_type=None,source_sha256=None,evidence=[],limitations=None) for r in rows])
    write_json(output/'annotations-template.json',annotations)
    return manifest


def check(output):
    output=Path(output);m=references.read(output/'manifest.json')
    require((output/'manifest.sha256').read_text().strip()==historical.sha(output/'manifest.json'),'Manifest changed')
    require(m['format']=='region-confirmation-campaign-v1' and m['source_sha256']==historical.sources()
        and m['evaluator_identity']==references.identity() and m['suite_manifest_sha256']==suite()[1]
        and m['skill']==region_skill.material()[1] and m['protocol_sha256']==historical.sha(references.PROTOCOL),
        'Frozen confirmation code/specification/skill changed')
    require(historical.sha(m['data_index']['path'])==m['data_index']['sha256'],'Data index changed')
    expected={(model,arm,case,r) for model in MODELS for arm in ARMS for case in TASKS for r in range(1,6)}
    require(len(m['rows'])==240 and {(r['model'],r['arm'],r['case'],r['repeat']) for r in m['rows']}==expected,
            'Assignment inventory changed')
    require((m['sessions'],m['maximum_model_requests'],m['authoring_seconds'],m['automatic_retries'])==(240,3840,600,0),
            'Confirmation budgets changed')
    require(len({r['id'] for r in m['rows']})==240,'Duplicate assignment identifiers')
    requirements={}
    checked_dependencies=set()
    for case in TASKS:
        try:
            goal=references.target(case,m['references'][case],None)
            require(m['reference_states'][case].get('manifest_sha256')==goal['index']['manifest_sha256'],'Reference changed')
            proof=output/'reference-reviews'/(case+'.json')
            require(historical.sha(proof)==m['reference_states'][case]['review_sha256'],'Reference review changed')
            audit=references.read(proof)
            require(audit['evidence_status']=='coherent' and audit['reference_manifest_sha256']==goal['index']['manifest_sha256'],
                    'Reference review binding changed')
            dependency_key=json.dumps(dict(data=goal['data'],images=goal['protocol']),sort_keys=True)
            if dependency_key not in checked_dependencies:
                from evaluation.candidates.run import preflight
                preflight(Path(m['data_index']['path']),goal)
                checked_dependencies.add(dependency_key)
            requirements[case]='passed'
        except (ValueError,OSError,KeyError,RuntimeError):
            requirements[case]='blocked'
    for row in m['rows']:
        relative=Path(row['path'])
        require(not relative.is_absolute() and '..' not in relative.parts and relative.parts[0]=='runs',
                'Session path outside campaign')
        folder=output/relative
        require(historical.sha(folder/'plan.json')==row['plan_sha256'],'Session plan changed')
        plan=references.read(folder/'plan.json')
        require(plan['model']==row['model'] and plan['cases']==[row['case']]
                and plan['assistance']==ARMS[row['arm']] and plan['evaluator_protocol']==CONFIRMATION_PROTOCOL
                and plan['budgets']['model_requests']==16 and plan['budgets']['authoring_seconds']==600,
                'Session assignment or matched budget changed')
        region_skill.verify(folder,plan,plan['assistance'])
    for kind in ('controls','end_to_end'):
        b=m[kind];require(historical.sha(b['path'])==b['sha256'],'Qualification evidence changed')
        evidence=references.read(b['path'])
        requirements[kind]='passed' if evidence.get('status')=='passed' and evidence.get('evaluator_identity')==references.identity() else 'blocked'
        if kind=='controls':
            complete={r['case'] for r in evidence.get('rows',[]) if r.get('control')=='correct' and r.get('status')=='passed'}==set(TASKS)
        else:
            complete={r['case'] for r in evidence.get('rows',[]) if r.get('strict_correct') is True}==set(TASKS)
        if kind=='controls':
            expected={(case,name) for case in TASKS for name in ('correct','equivalent_order','shared_mutation')}
            expected|={('staggered_seven_pin_cluster','annulus_instead_of_envelope'),
                       ('dual_temperature_pin_pair','wrong_temperature'),
                       ('dual_temperature_pin_pair','wrong_boundary'),
                       ('restricted_source_nine_pin','wrong_source')}
            complete &= {(r['case'],r['control']) for r in evidence.get('rows',[]) if r['status']=='passed'}==expected
        if not complete:requirements[kind]='blocked'
        if complete and evidence.get('status')=='passed':
            for row in evidence['rows']:
                if kind=='controls':
                    folder=Path(row['evidence'])
                    require(historical.sha(folder/'fidelity.json')==row['fidelity_sha256']
                            and historical.sha(folder/'reference.py')==row['source_sha256'],
                            'Native control evidence changed')
                else:
                    folder=Path(row['assessment_path'])
                    require(historical.sha(folder/'report.json')==row['report_sha256'],'End-to-end report changed')
                    raw=references.read(folder/'report.json')
                    require(raw['case']==row['case'],'End-to-end case changed')
                    actual=review_assessment(folder,Path(m['data_index']['path']),reference=m['references'][row['case']])
                    require(actual['evidence_status']=='coherent' and actual.get('strict_correct') is True,
                            'End-to-end success contradicts retained execution')
    return dict(format='confirmation-readiness-v1',technical_status='passed' if all(v=='passed' for v in requirements.values()) else 'blocked',
        checks=requirements,live_campaign_dispatched=(output/'launch.json').exists(),
        provider_qualification_at_preparation=m['provider_qualification'],
        scientific_review=m['scientific_review'],sample_size_justification=m['sample_size_justification'])


def analyze(output, annotations=None):
    output=Path(output);m=references.read(output/'manifest.json');progress=references.read(output/'progress.json')
    require(set(r['id'] for r in progress['rows'])==set(r['id'] for r in m['rows']),'Progress assignment inventory changed')
    states={r['id']:r for r in progress['rows']}
    labels={}
    if annotations:
        value=references.read(annotations)
        require(value['format']=='confirmation-mechanism-annotations-v1'
                and value['campaign_manifest_sha256']==historical.sha(output/'manifest.json'),
                'Annotation campaign binding changed')
        labels={r['id']:r for r in value['records']}
        require(len(labels)==len(value['records']) and set(labels)<=set(states),'Unknown/duplicate mechanism labels')
    rows=[]
    for row in m['rows']:
        s=states[row['id']];assessment=output/row['path']/'runs'/row['case']/'assessment'
        review=review_assessment(assessment,Path(m['data_index']['path']),reference=m['references'][row['case']]) if (assessment/'report.json').exists() else {}
        scored=review.get('evidence_status')=='coherent' and review.get('score') is not None
        outcome=('protocol_success' if scored and review.get('strict_correct') is True else
                 'evaluated_failure' if scored else 'unscored_incident' if s['state'] in ('finished','incident') else 'pending')
        from experiments.region_ad_analysis import annotation
        mechanism=annotation(output,row,labels[row['id']]) if row['id'] in labels else 'pending'
        builder=output/row['path']/'runs'/row['case']/'builder'
        result=references.read(builder/'result.json') if (builder/'result.json').exists() else {}
        usage=None;usage_complete=False
        if result:
            from builder.trajectory import summarize
            effort=summarize(builder,result)['effort']
            usage=effort['token_usage'];usage_complete=effort['token_usage_complete']
        assessment_report=references.read(assessment/'report.json') if (assessment/'report.json').exists() else {}
        rows.append(dict(row,state=s['state'],operational_state=s['state'],outcome=outcome,mechanism=mechanism,
            mechanism_reviewer=labels.get(row['id'],{}).get('reviewer'),
            mechanism_reviewer_type=labels.get(row['id'],{}).get('reviewer_type','unspecified'),
            assessment_seconds=assessment_report.get('elapsed_seconds'),
            retained_evidence_status=review.get('evidence_status'),
            verified_checks=assessment_report.get('checks') if review.get('evidence_status')=='coherent' else None,
            reported_stop=assessment_report.get('stop'),
            numerical_comparison=assessment_report.get('comparison') if review.get('evidence_status')=='coherent' else None,
            geometry_status=assessment_report.get('fidelity',{}).get('geometry',{}).get('status') if review.get('evidence_status')=='coherent' else None,
            settings_status=assessment_report.get('fidelity',{}).get('settings',{}).get('status') if review.get('evidence_status')=='coherent' else None,
            requests_received=result.get('request_count'),authoring_seconds=result.get('elapsed_seconds'),
            token_usage=usage,token_usage_complete=usage_complete))
    groups=[]
    for model in MODELS:
        for case in TASKS:
            for arm in ARMS:
                counts=Counter(r['outcome'] for r in rows if (r['model'],r['case'],r['arm'])==(model,case,arm))
                cell=[r for r in rows if (r['model'],r['case'],r['arm'])==(model,case,arm)]
                consumed=[r for r in cell if r['operational_state']!='pending']
                effort={}
                for name in ('requests_received','authoring_seconds','assessment_seconds'):
                    values=[r[name] for r in consumed if type(r[name]) in (int,float)]
                    effort[name]=dict(total=sum(values) if values else None,available=len(values),missing=len(consumed)-len(values))
                usage=[r['token_usage'] for r in consumed if r['token_usage'] is not None]
                effort['reported_tokens']=dict(sums={k:sum(u[k] for u in usage) for k in ('input_tokens','output_tokens','total_tokens')} if usage else None,
                    available_records=len(usage),complete_records=sum(r['token_usage_complete'] for r in consumed),
                    missing_records=len(consumed)-len(usage))
                scored=counts['protocol_success']+counts['evaluated_failure']
                groups.append(dict(model=model,case=case,arm=arm,planned=5,consumed=len(consumed),
                    mechanism_counts={status:sum(r['mechanism']==status for r in cell) for status in
                        ('pending','demonstrated','not_observed_within_reviewed_scope','unassessable')},
                    outcomes={k:counts[k] for k in
                    ('protocol_success','evaluated_failure','unscored_incident','pending')},effort=effort,
                    success_fraction=counts['protocol_success']/5 if not counts['pending'] else None,
                    conditional_success_fraction_scored=counts['protocol_success']/scored if scored else None))
    comparisons=[]
    for model in MODELS:
        selected=[g for g in groups if g['model']==model]
        complete=all(g['success_fraction'] is not None for g in selected)
        rates={a:sum(g['success_fraction'] for g in selected if g['arm']==a)/12 for a in ARMS} if complete else {}
        comparisons.append(dict(model=model,complete=complete,equal_task_weight_rates=rates,
                                 D_minus_A=rates['D']-rates['A'] if complete else None))
    return dict(format='confirmation-analysis-v1',rows=rows,groups=groups,comparisons=comparisons,
                mechanism_status='pending separate source review; no inference from syntax or skill exposure')


def delivery(folder, model, arm, setup):
    """Reconstruct one-request real-provider transmission; not task performance."""
    from builder.context import request_setup
    from builder.relay import validate_event_stream, event_frame
    from builder.openmc_python import IMAGE_ID
    from builder.route import condition_prompt, EXTENDED_REQUEST_BUDGET
    from prompts.prepare import build_prompt
    folder=Path(folder)
    m=references.read(folder/'manifest.json')
    require(m['mode']=='subscription' and m['model']==model and m['assistance']==ARMS[arm]
            and m['case']=='cross_shaped_mixture' and m['max_requests']==1 and m['wall_seconds']==120
            and m['image_id']==IMAGE_ID and m['assessment_route']['evaluator_protocol']==CONFIRMATION_PROTOCOL,
            'Provider control assignment changed')
    region_skill.verify(folder,m,ARMS[arm])
    prompt=condition_prompt(build_prompt('cross_shaped_mixture'),ARMS[arm],request_budget=EXTENDED_REQUEST_BUDGET)
    body=references.read(folder/'request-01.json')
    require(body.get('model')==model and region_skill.initial_context(body,prompt,ARMS[arm])
            and request_setup(body)==setup,'Provider task/setup/procedure delivery changed')
    require(references.read(folder/'setup-01.json').get('matched') is True,'Provider setup unchecked')
    upstream=references.read(folder/'upstream-01.json')
    raw=(folder/'response-01.sse').read_bytes();validate_event_stream(raw)
    require(upstream.get('completion_observed') is True and upstream.get('http_status')==200
            and upstream.get('stream_validation')=='passed'
            and upstream.get('response_bytes_forwarded')==len(raw)
            and upstream.get('stop_reason')=='response_completed','Complete provider delivery unavailable')
    require({p.name for p in folder.glob('request-*.json')}=={'request-01.json'}
            and {p.name for p in folder.glob('response-*.sse')}=={'response-01.sse'}
            and {p.name for p in folder.glob('upstream-*.json')}=={'upstream-01.json'},'Control request cap changed')
    require(references.read(folder/'result.json')['cleanup_confirmed'] is True,'Control cleanup unconfirmed')
    require(m['controller_sha256']==historical.sha('builder/run.py')
            and historical.sha(folder/'controller-source.py')==m['controller_sha256'],
            'Provider control implementation changed')
    events=[event_frame(block) for block in raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').split('\n\n') if block.strip()]
    terminal=[e['response'] for e in events if isinstance(e,dict) and e.get('type')=='response.completed']
    require(len(terminal)==1,'Ambiguous provider completion')

    return dict(model=model,arm=arm,status='passed',response_model=terminal[0].get('model'),
                request_sha256=historical.sha(folder/'request-01.json'),
                response_sha256=historical.sha(folder/'response-01.sse'))


def provider_controls(output, setups_file, maximum_requests):
    from builder import run as builder
    from prompts.confirmation import prepare as prepare_prompt
    require(maximum_requests==4,'Declare the four-request provider qualification budget')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    setups=references.read(setups_file)
    require(set(setups)==set(MODELS),'Declare both provider setups')
    prepare_prompt('cross_shaped_mixture',output/'input')
    report=dict(format='confirmation-provider-controls-v1',status='running',maximum_requests=4,
                excluded_from_campaign=True,rows=[])
    write_json(output/'report.json',report)
    for model in MODELS:
        for arm in ARMS:
            folder=output/(model+'-'+arm)
            try:
                builder.run(folder,case='cross_shaped_mixture',prepared_input=output/'input',
                    model=model,assistance=ARMS[arm],evaluator_protocol=CONFIRMATION_PROTOCOL,
                    mode='subscription',max_requests=1,wall_seconds=120,
                    request_budget='authoring-requests-16-v1',request_setup=setups[model],
                    expected_region_skill=region_skill.material()[1] if arm=='D' else None)
                proof=delivery(folder,model,arm,setups[model])
                report['rows'].append(proof);write_json(output/'report.json',report)
            except Exception as exc:
                report.update(status='blocked',reason=str(exc),stopped_at=folder.name)
                write_json(output/'report.json',report)
                return report
    report['status']='passed';write_json(output/'report.json',report)
    return report


def dispatch(output, controls, maximum_requests):
    """Explicit, budgeted live action. Never called by prepare/check/qualification."""
    output=Path(output)
    ready=check(output);require(ready['technical_status']=='passed','Technical qualification incomplete')
    require(maximum_requests==3840,'Declare the 3840-request campaign ceiling')
    m=references.read(output/'manifest.json')
    controls=Path(controls)
    evidence=references.read(controls/'report.json')
    require(evidence['status']=='passed' and len(evidence['rows'])==4
            and {(r['model'],r['arm']) for r in evidence['rows']}==
                {(model,arm) for model in MODELS for arm in ARMS},'Four provider controls required')
    for row in evidence['rows']:
        require(delivery(controls/(row['model']+'-'+row['arm']),row['model'],row['arm'],
                         m['request_setups'][row['model']])==row,'Provider-control evidence changed')
    require(not (output/'launch.json').exists(),'Campaign already consumed; no automatic restart')
    write_json(output/'launch.json',dict(started=now(),maximum_model_requests=maximum_requests,
        manifest_sha256=historical.sha(output/'manifest.json'),
        provider_controls_sha256=historical.sha(controls/'report.json')))
    progress=dict(state='running',rows=m['rows'])
    try:
        for row in progress['rows']:
            # A failure/incident is never replaced. Check frozen code and inputs before every assignment.
            require(m['source_sha256']==historical.sources()
                    and historical.sha(m['data_index']['path'])==m['data_index']['sha256'],
                    'Frozen implementation/data changed during campaign')
            require(historical.sha(output/row['path']/'plan.json')==row['plan_sha256'],'Session plan changed')
            require(shutil.disk_usage(output).free>=10*1024**3,'Disk reserve below 10 GiB')
            row.update(state='started',started=now());atomic_json(output/'progress.json',progress)
            folder=output/row['path']
            summary=execute(folder,request_setup=m['request_setups'][row['model']])
            require(summary['tasks'][0]['builder_status']=='completed','Builder incomplete; slot consumed')
            task=folder/'runs'/row['case']
            raw,provenance=submission(task/'builder',row['case'])
            require(raw==(task/'candidate.py').read_bytes(),'Final submission bytes changed')
            result=evaluate(row['case'],task/'assessment',index=Path(m['data_index']['path']),
                candidate=task/'candidate.py',provenance=provenance,evaluator_protocol=CONFIRMATION_PROTOCOL,
                reference=m['references'][row['case']])
            review=review_assessment(task/'assessment',Path(m['data_index']['path']),reference=m['references'][row['case']])
            write_json(task/'assessment/review.json',review)
            require(review['evidence_status']=='coherent' and review.get('score') is not None,
                    'Unscored evaluation incident; pause before next slot')
            row.update(state='finished',finished=now(),score=review['score'],strict_correct=review['strict_correct'])
            atomic_json(output/'progress.json',progress)
            print(json.dumps(dict(id=row['id'],state='finished',strict_correct=review['strict_correct'])),flush=True)
        progress.update(state='complete',finished=now())
    except Exception as exc:
        row.update(state='incident',finished=now(),reason=str(exc))
        progress.update(state='stopped',reason=str(exc))
    finally:
        atomic_json(output/'progress.json',progress)
    return progress


def review_controls(sources, roots, output, data_index, selected=TASKS):
    """Reconstruct native control verdicts; keep original reports unchanged."""
    from evaluation.confirmation.controls import inputs
    from evaluation.confirmation.qualify import inspect
    from evaluator.transport_input import accepted_export
    from evaluator.profiles import PROFILE
    from evaluator.run import digest
    from evaluation.candidates.phase_evidence import export_outcome
    from evaluation.scientific.records import inspection_record
    from evaluation.scientific.inspection import WORKER, admit
    from evaluation.scientific import boundaries
    from evaluation.candidates import assessment, boundary_assessment
    from evaluation.benchmark_suite.suite_checks import assess
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    sampling=dict(references.read(references.PROTOCOL)['sampling'],seed=1)
    report=dict(format='confirmation-native-controls-v1',provider_calls=0,neutron_transport=False,
                evaluator_identity=references.identity(),rows=[])
    for case in selected:
        for name,text,expected in inputs(case,Path(sources,case+'.py').read_text()):
            matches=[Path(root)/case/name for root in roots if (Path(root)/case/name).is_dir()]
            require(len(matches)==1,'Missing/ambiguous control evidence: '+case+'/'+name)
            folder=matches[0]
            require((folder/'reference.py').read_text()==text,'Control source changed')
            require(export_outcome(folder/'export',PROFILE['export_image'],data_index,digest(text.encode()))==
                    dict(cause=None,reason=None),'Control export evidence incomplete')
            xml,_=accepted_export(folder/'export')
            obs=inspection_record(case,folder/'inspection',xml,WORKER.read_bytes(),image=PROFILE['export_image'])
            require(obs['status']=='inspected','Control inspection unavailable')
            br=boundary_assessment.evaluate(boundaries.record(folder/'boundaries',xml,image=PROFILE['export_image']),
                                             boundaries.requirements(case),obs)
            fidelity=assess(case,admit(xml),obs,sampling,boundary_result=br)
            require(fidelity==references.read(folder/'fidelity.json'),'Control fidelity changed')
            checks=assessment.fidelity_checks(case,fidelity,obs)
            if expected is None:
                passed=all(v is True for group in ('geometry','materials','physics_settings') for v in checks[group].values())
            else:
                group,field=expected
                if field in ('invalid_geometry','temperature_failures'):passed=fidelity[group][field]>0
                elif field=='score_check':passed=any(v['verdict']=='nonconforming' for v in fidelity[group]['verdicts'])
                else:passed=any(c['passed'] is False for c in fidelity['settings']['checks']
                               if c['field'] in ('source_space','source_parameters'))
            report['rows'].append(dict(case=case,control=name,status='passed' if passed else 'failed',
                expected='accept' if expected is None else 'detect',evidence=str(folder.resolve()),
                source_sha256=digest(text.encode()),xml_sha256=digest(xml),
                fidelity_sha256=historical.sha(folder/'fidelity.json')))
    report['status']='passed' if all(r['status']=='passed' for r in report['rows']) else 'failed'
    write_json(output/'report.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','check','analyze','end-to-end','qualify-provider','run','review-controls'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--references',type=Path)
    p.add_argument('--data-index',type=Path)
    p.add_argument('--setups',type=Path)
    p.add_argument('--controls',type=Path)
    p.add_argument('--end-to-end',type=Path)
    p.add_argument('--cases',nargs='+',choices=TASKS,default=list(TASKS))
    p.add_argument('--sources',type=Path)
    p.add_argument('--control-roots',nargs='+',type=Path)
    p.add_argument('--annotations',type=Path)
    p.add_argument('--maximum-model-requests',type=int)
    a=p.parse_args()
    if a.action=='review-controls':
        if not all((a.sources,a.control_roots,a.data_index)):p.error('Control review requires sources, control roots and data')
        result=review_controls(a.sources,a.control_roots,a.output,a.data_index.resolve(strict=True),a.cases)
        print(json.dumps(dict(status=result['status'],controls=len(result['rows'])),indent=2));return
    if a.action in ('qualify-provider','run') and a.maximum_model_requests is None:
        p.error('Live operations require an explicit maximum-model-requests budget')
    if a.action=='qualify-provider':
        if not a.setups:p.error('Provider controls require reviewed setups')
        print(json.dumps(provider_controls(a.output,a.setups,a.maximum_model_requests),indent=2));return
    if a.action=='run':
        if not a.controls:p.error('Run requires the provider-control directory')
        dispatch(a.output,a.controls,a.maximum_model_requests);return
    if a.action=='prepare':
        if not all((a.references,a.data_index,a.setups,a.controls,a.end_to_end)):
            p.error('Preparation requires references, data, setups, controls and end-to-end receipts')
        result=prepare(a.output,a.references,a.data_index,a.setups,a.controls,a.end_to_end)
        result=dict(sessions=result['sessions'],maximum_model_requests=result['maximum_model_requests'],dispatched=False)
    elif a.action=='end-to-end':
        if not a.references or not a.data_index:p.error('End-to-end requires reference index and data')
        result=end_to_end(a.references,a.output,a.data_index.resolve(strict=True),a.cases)
    elif a.action=='check':result=check(a.output)
    else:result=analyze(a.output,a.annotations)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
