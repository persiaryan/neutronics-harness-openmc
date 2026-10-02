"""Explicit serial pilot/study execution with frozen inputs and consumed slots."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import uuid

from builder.submission import submission
from evaluation.candidates.run import evaluate
from evaluation.candidates.verify import review_assessment
from evaluator.public_runtime import load
from experiments.run import prepare, execute, atomic_json, assessment_summary
from observability import now

ROOT = Path(__file__).resolve().parents[1]
ARMS = {'A':'guided_construction','B':'guided_boundaries','C':'guided_boundaries_smoke'}
MODELS = ('gpt-5.6-luna','gpt-5.6-sol')
TASKS = ('reflective_pin_cell','reflected_7x7','two_composition_5x5','axially_zoned_5x5','asymmetric_5x5')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    paths=[]
    for folder in ('builder','evaluation','evaluator','experiments','prompts'):
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and 'frozen' not in p.parts
                     and '__pycache__' not in p.parts and p.suffix in ('.py','.md','.json','.txt'))
    paths.extend(ROOT/p for p in ('observability.py','observation_contracts.py','observation_catalog.json'))
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}


def prepare_campaign(output, *, pilot, data_index, setup_file, runtime_path=None):
    output=Path(output).resolve()
    if output.exists(): raise ValueError('Use a fresh campaign directory')
    if pilot and runtime_path is None: raise ValueError('Pilot requires public runtime binding')
    runtime=load(runtime_path) if pilot else None
    setups=json.loads(Path(setup_file).read_text())
    if set(setups)!=set(MODELS): raise ValueError('Declare both reviewed model request setups')
    output.mkdir(parents=True)
    rows=[]
    order=[(r,t,m,a) for r in range(1,2 if pilot else 6) for t in (TASKS[:1] if pilot else TASKS) for m in MODELS for a in ARMS]
    if not pilot: random.Random(20261002).shuffle(order)
    for number,(repeat,case,model,arm) in enumerate(order,1):
        ident=f'{number:03d}-r{repeat}-{case}-{model}-{arm}'
        folder=output/'runs'/ident
        prepare(folder,assistance=ARMS[arm],model=model,cases=(case,),
                smoke_data_index=data_index if arm=='C' else None,request_budget='authoring-requests-16-v1')
        plan=json.loads((folder/'plan.json').read_text())
        rows.append(dict(id=ident,run_id=plan['execution_ids'][case],plan_sha256=sha(folder/'plan.json'),case=case,model=model,arm=arm,repeat=repeat,path=str(folder.relative_to(output)),state='pending'))
    manifest=dict(format='dashboard-live-campaign-v2',campaign_id=str(uuid.uuid4()),name=output.name,created=now(),kind='integration_pilot' if pilot else 'prospective_development_study',
        sessions=len(rows),rows=rows,models=list(MODELS),arms=ARMS,cases=list(TASKS[:1] if pilot else TASKS),
        repeats=1 if pilot else 5,request_limit=16,authoring_seconds=600,automatic_retries=0,
        maximum_model_requests=len(rows)*16,source_sha256=sources(),data_index=str(Path(data_index).resolve()),data_index_sha256=sha(data_index),
        request_setups=setups,runtime=runtime,reference='public_demo_only' if pilot else 'private_frozen_suite',
        failure_policy='Pause after infrastructure, provider or evaluator incidents; consumed slots are never retried.',
        minimum_free_bytes=10*1024**3,study_type='Repeated development tasks; descriptive comparison, not holdout confirmation.')
    atomic_json(output/'manifest.json',manifest)
    atomic_json(output/'progress.json',dict(state='prepared',rows=rows))
    atomic_json(output/'dashboard-campaign.json',dict(campaigns=['manifest.json']))
    return manifest


def run_campaign(output):
    output=Path(output).resolve()
    manifest=json.loads((output/'manifest.json').read_text())
    if (output/'launch.json').exists(): raise ValueError('Campaign launch already consumed; no automatic resume')
    if manifest['source_sha256']!=sources() or sha(manifest['data_index'])!=manifest['data_index_sha256']:
        raise ValueError('Frozen implementation or data index changed')
    atomic_json(output/'launch.json',dict(started=now(),manifest_sha256=sha(output/'manifest.json')))
    progress=dict(state='running',started=now(),rows=manifest['rows'])
    try:
        for row in progress['rows']:
            if manifest['source_sha256']!=sources(): raise ValueError('Frozen implementation changed during campaign')
            if shutil.disk_usage(output).free<manifest['minimum_free_bytes']:
                raise RuntimeError('Free disk below declared 10 GiB reserve; no next session dispatched')
            folder=output/row['path']
            if row.get('plan_sha256') and sha(folder/'plan.json') != row['plan_sha256']:
                raise ValueError('Frozen execution plan changed')
            if (folder/'dashboard-run.json').exists(): raise ValueError('Authoring slot already consumed')
            row.update(state='started',started=now())
            status=dict(format='dashboard-demo-v1',state='authoring',started=now(),model=row['model'],reference=manifest['reference'],
                        campaign_id=manifest.get('campaign_id'),execution_id=row.get('run_id'),
                        campaign=str(output),maximum_model_requests=16,automatic_retries=0)
            atomic_json(folder/'dashboard-run.json',status)
            atomic_json(output/'progress.json',progress)
            print(json.dumps(dict(event='started',id=row['id'],time=now())),flush=True)
            try:
                summary=execute(folder,request_setup=manifest['request_setups'][row['model']])
                taskrow=summary['tasks'][0]
                if taskrow['builder_status']!='completed':
                    raise RuntimeError('Builder did not complete; slot consumed without retry')
                task=folder/'runs'/row['case']
                source,provenance=submission(task/'builder',row['case'])
                if source!=(task/'candidate.py').read_bytes(): raise ValueError('Submission bytes changed')
                status.update(state='assessment',updated=now());atomic_json(folder/'dashboard-run.json',status)
                pilot=manifest['kind']=='integration_pilot'
                assessment=task/('assessment-public-demo' if pilot else 'assessment')
                kwargs=dict(reference=ROOT/'examples/reflective_pin_cell/reference',runtime=manifest['runtime']) if pilot else {}
                report=evaluate(row['case'],assessment,index=Path(manifest['data_index']),candidate=task/'candidate.py',provenance=provenance,**kwargs)
                status.update(state='verification',updated=now());atomic_json(folder/'dashboard-run.json',status)
                review=review_assessment(assessment,Path(manifest['data_index']),**kwargs)
                atomic_json(assessment/'review.json',review)
                taskrow.update(assessment_summary(report,review),final_assessment=report['status'],assessment=str(assessment.relative_to(folder)))
                summary['transport']='native_final_assessment_run';atomic_json(folder/'summary.json',summary)
                row.update(state='finished',finished=now(),score=review.get('score'),evidence_status=review['evidence_status'],overall_success=taskrow['overall_success'])
                status.update(state='finished',finished=now(),evidence_status=review['evidence_status'],verified_protocol_success=taskrow['overall_success'])
                if review['evidence_status']!='coherent' or review.get('score') is None:
                    raise RuntimeError('Final evaluation incident; pause before dispatching another session')
                print(json.dumps(dict(event='finished',id=row['id'],score=review['score'],success=taskrow['overall_success'],time=now())),flush=True)
            except Exception as exc:
                row.update(state='incident',finished=now(),error=str(exc))
                status.update(state='stopped',finished=now(),error_type=type(exc).__name__,error=str(exc))
                raise
            finally:
                atomic_json(folder/'dashboard-run.json',status)
                atomic_json(output/'progress.json',progress)
        progress.update(state='complete',finished=now())
    except Exception as exc:
        progress.update(state='paused_on_incident',updated=now(),error=str(exc))
        print(json.dumps(dict(event='paused',error=str(exc),time=now())),flush=True)
        raise
    finally:
        atomic_json(output/'progress.json',progress)
    return progress


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--pilot',action='store_true')
    parser.add_argument('--data-index',type=Path)
    parser.add_argument('--setups',type=Path)
    parser.add_argument('--runtime',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':
        if not args.data_index or not args.setups: parser.error('Preparation needs --data-index and --setups')
        result=prepare_campaign(args.output,pilot=args.pilot,data_index=args.data_index,setup_file=args.setups,runtime_path=args.runtime)
        print(json.dumps(dict(prepared=result['sessions'],kind=result['kind'])))
    else: run_campaign(args.output)
