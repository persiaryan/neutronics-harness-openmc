"""Explicit continuation of pending slots; consumed attempts are never retried.

The original manifest, launch seal and scientific implementation remain frozen.
This operator controller is the only additional source allowed by the amendment.
Environmental availability is checked again every 30 minutes. Unknown scientific
outcomes remain unscored, and do not prevent another independent slot running.
"""
import argparse
import copy
import fcntl
import json
from pathlib import Path
import shutil
import time

from builder.relay import load_auth
from dashboard.collection import read_studies
from evaluation.candidates.run import clean_resources, preflight, target
from experiments import dashboard_campaign as original
from experiments.run import atomic_json
from observability import now

SELF = 'experiments/continue_campaign.py'
INTERVAL = 1800


class SlotIncident(Exception):
    pass


def load_campaign(root):
    read_studies([root/'manifest.json'])  # Includes launch seal and confined paths.
    manifest = json.loads((root/'manifest.json').read_text())
    launch = json.loads((root/'launch.json').read_text())
    if launch['manifest_sha256'] != original.sha(root/'manifest.json'):
        raise ValueError('Original launch seal changed')
    progress = json.loads((root/'progress.json').read_text())
    expected = manifest['rows']
    if len(progress['rows']) != len(expected):
        raise ValueError('Progress inventory changed')
    for planned, row in zip(expected, progress['rows']):
        for key in ('id', 'run_id', 'path', 'case', 'model', 'arm', 'repeat', 'plan_sha256'):
            if row.get(key) != planned.get(key):
                raise ValueError('Progress identity changed: '+key)
        if row['state'] not in ('pending', 'started', 'finished', 'incident'):
            raise ValueError('Unknown slot state')
        if original.sha(root/row['path']/'plan.json') != planned['plan_sha256']:
            raise ValueError('Frozen execution plan changed')
        if row['state']=='pending' and (root/row['path']/'dashboard-run.json').exists():
            raise ValueError('Pending slot already has execution evidence')
    return manifest, progress


def frozen(manifest, controller_sha):
    current = original.sources()
    if current.pop(SELF, None) != controller_sha or current != manifest['source_sha256']:
        raise ValueError('Frozen scientific/authoring implementation or controller changed')
    if original.sha(manifest['data_index']) != manifest['data_index_sha256']:
        raise ValueError('Frozen data index changed')


def available(root, manifest, case):
    if shutil.disk_usage(root).free < manifest['minimum_free_bytes']:
        raise RuntimeError('Free disk below declared 10 GiB reserve')
    load_auth(Path.home()/'.codex/auth.json')  # Never retain credentials.
    clean_resources()
    if manifest['kind']=='integration_pilot':
        goal=target(case,reference=original.ROOT/'examples/reflective_pin_cell/reference',runtime=manifest['runtime'])
    else:
        goal=target(case)
    preflight(Path(manifest['data_index']), goal)


def run_slot(root, manifest, row):
    folder=root/row['path']
    if original.sha(folder/'plan.json') != row['plan_sha256']:
        raise ValueError('Frozen execution plan changed')
    if (folder/'dashboard-run.json').exists():
        raise ValueError('Authoring slot already consumed')
    row.update(state='started',started=now())
    status=dict(format='dashboard-demo-v1',state='authoring',started=now(),model=row['model'],
                reference=manifest['reference'],campaign_id=manifest['campaign_id'],
                execution_id=row['run_id'],campaign=str(root),maximum_model_requests=16,automatic_retries=0)
    atomic_json(folder/'dashboard-run.json',status)
    try:
        summary=original.execute(folder,request_setup=manifest['request_setups'][row['model']])
        taskrow=summary['tasks'][0]
        if taskrow['builder_status']!='completed':
            retained=json.loads((folder/'runs'/row['case']/'builder/result.json').read_text())
            if retained.get('cleanup_confirmed') is not True:
                raise RuntimeError('Builder cleanup is not confirmed; operator review required')
            raise SlotIncident('Builder did not complete; consumed attempt retained without retry')
        task=folder/'runs'/row['case']
        source,provenance=original.submission(task/'builder',row['case'])
        if source!=(task/'candidate.py').read_bytes():
            raise ValueError('Submission bytes changed')
        status.update(state='assessment',updated=now());atomic_json(folder/'dashboard-run.json',status)
        pilot=manifest['kind']=='integration_pilot'
        assessment=task/('assessment-public-demo' if pilot else 'assessment')
        kwargs=dict(reference=original.ROOT/'examples/reflective_pin_cell/reference',runtime=manifest['runtime']) if pilot else {}
        report=original.evaluate(row['case'],assessment,index=Path(manifest['data_index']),candidate=task/'candidate.py',provenance=provenance,**kwargs)
        if report.get('cleanup_confirmed') is not True:
            raise RuntimeError('Evaluation cleanup is not confirmed; operator review required')
        status.update(state='verification',updated=now());atomic_json(folder/'dashboard-run.json',status)
        review=original.review_assessment(assessment,Path(manifest['data_index']),**kwargs)
        atomic_json(assessment/'review.json',review)
        taskrow.update(original.assessment_summary(report,review),final_assessment=report['status'],assessment=str(assessment.relative_to(folder)))
        summary['transport']='native_final_assessment_run';atomic_json(folder/'summary.json',summary)
        row.update(score=review.get('score'),evidence_status=review['evidence_status'],overall_success=taskrow['overall_success'])
        if review['evidence_status']!='coherent' or review.get('score') is None:
            raise SlotIncident('Unscored evaluation retained; next independent slot permitted')
        row.update(state='finished',finished=now())
        status.update(state='finished',finished=now(),evidence_status=review['evidence_status'],verified_protocol_success=taskrow['overall_success'])
    except Exception as exc:
        row.update(state='incident',finished=now(),error=str(exc))
        status.update(state='stopped',finished=now(),error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        atomic_json(folder/'dashboard-run.json',status)


def resume(root):
    root=Path(root).resolve()
    with (root/'continuation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        manifest,progress=load_campaign(root)
        controller_sha=original.sha(Path(__file__))
        frozen(manifest,controller_sha)
        if progress['state']=='running':
            raise ValueError('Campaign still marked running; inspect prior process before recovery')
        if progress['state']=='complete':
            return progress
        if any(row['state']=='started' for row in progress['rows']):
            raise ValueError('Interrupted active slot requires explicit evidence reconciliation')
        receipt=dict(format='campaign-continuation-v1',time=now(),manifest_sha256=original.sha(root/'manifest.json'),
                     previous_progress=copy.deepcopy(progress),controller_sha256=controller_sha,
                     policy='Continue pending slots after retained unscored incidents; no retries or rescoring. Recheck environmental blocks every 1800 seconds.',
                     authorization='Operator requested restart or correction after campaign stops.')
        with (root/'continuations.jsonl').open('a') as stream:
            stream.write(json.dumps(receipt,sort_keys=True)+'\n')
        progress.update(state='running',continuation=receipt['policy'],updated=now())
        progress.pop('error',None)
        try:
            for row in progress['rows']:
                if row['state']!='pending':
                    continue
                while True:
                    frozen(manifest,controller_sha)
                    try:
                        available(root,manifest,row['case'])
                        break
                    except Exception as exc:
                        progress.update(state='paused_on_incident',error=str(exc),updated=now(),retry_after_seconds=INTERVAL)
                        atomic_json(root/'progress.json',progress)
                        print(json.dumps(dict(event='waiting_for_environment',error=str(exc),time=now())),flush=True)
                        time.sleep(INTERVAL)
                progress.update(state='running',updated=now())
                progress.pop('error',None);progress.pop('retry_after_seconds',None)
                atomic_json(root/'progress.json',progress)
                print(json.dumps(dict(event='started',id=row['id'],time=now())),flush=True)
                # Persist the consumed slot before authoring; status files also
                # prevent reuse if the host disappears between atomic writes.
                row.update(state='started',started=now())
                atomic_json(root/'progress.json',progress)
                try:
                    run_slot(root,manifest,row)
                except SlotIncident:
                    pass
                finally:
                    atomic_json(root/'progress.json',progress)
                print(json.dumps(dict(event=row['state'],id=row['id'],score=row.get('score'),time=now())),flush=True)
            progress.update(state='complete',finished=now())
        except Exception as exc:
            progress.update(state='paused_on_incident',error=str(exc),updated=now())
            raise
        finally:
            atomic_json(root/'progress.json',progress)
        return progress


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    resume(parser.parse_args().output)
