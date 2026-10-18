"""Explicit continuation of the migrated twelve-trial prefix; no automatic restart.

This operator entry point has its own hash binding. The frozen evaluator,
builder and migration source inventories remain unchanged.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil

from builder import region_skill
from builder.context import write_json
from builder.submission import submission
from evaluation.candidates import verdict_migration
from evaluation.candidates.run import evaluate
from evaluation.candidates.verify import review_assessment
from evaluation.scientific.records import require
from evaluator.profiles import CONFIRMATION_PROTOCOL
from experiments import region_confirmation as campaign
from experiments import migrate_confirmation_verdicts as migration
from experiments.run import execute, atomic_json

VERSION = 'confirmation-continuation-v1'
CONTROLLER = Path(__file__).resolve()
sha = campaign.historical.sha
read = campaign.references.read
now = campaign.now


def binding(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path))


def bound(value):
    path = Path(value['path'])
    require(sha(path) == value['sha256'], 'Bound evidence changed: '+str(path))
    return path


def prepared_files(folder):
    """Only original public input bundles; never copy consumed execution evidence."""
    names = ['plan.json', 'support-matrix.json']
    names += [str(Path('inputs')/p) for p in migration.inventory(folder/'inputs')]
    names += [name for name in (region_skill.SNAPSHOT, region_skill.CATALOG_SNAPSHOT)
              if (folder/name).exists()]
    return {name: sha(folder/name) for name in sorted(names)}


def prefix_rows(original, revised, output):
    require(len(revised['rows']) == 12 and
            [r['id'] for r in revised['rows']] == [f'{i:03d}' for i in range(1,13)],
            'This continuation requires exactly the twelve migrated assignments')
    require(revised['counts'] == dict(protocol_success=11, evaluated_failure=1,
                                    unscored_incident=0, pending=228),
            'Unexpected migrated prefix')
    rows = deepcopy(original['rows'])
    for row, saved in zip(rows, revised['rows']):
        require(all(row[k] == saved[k] for k in migration.IMMUTABLE_ROW),
                'Migrated prefix assignment changed')
        require(saved['verdict']['evidence_status'] == 'coherent'
                and saved['verdict']['score'] is not None, 'Unresolved prefix')
        row.update(state='finished', origin='migrated_prefix',
                   score=saved['verdict']['score'],
                   strict_correct=saved['verdict']['strict_correct'],
                   verdict_path=str(Path(output).resolve()/'verdicts'/(row['id']+'.json')))
    require(all(r['state']=='pending' for r in rows[12:]), 'Pending suffix changed')
    return rows


def prepare(output, revision, provider_controls):
    output, revision = Path(output).resolve(), Path(revision).resolve()
    require(not output.exists(), 'Continuation output must be fresh')
    proof = migration.verify_migration(revision)
    revised = read(revision/'report.json')
    original_root = Path(revised['campaign'])
    require(original_root not in output.parents and revision not in output.parents,
            'Continuation must be outside original and migrated evidence')
    original = read(original_root/'manifest.json')
    initial_rows = prefix_rows(original, revised, revision)
    output.mkdir(parents=True)
    inputs = {}
    for row in original['rows']:
        source, target = original_root/row['path'], output/row['path']
        if row['state']=='pending' and row['id'] not in {r['id'] for r in revised['rows']}:
            require(not (source/'runs').exists() and not (source/'summary.json').exists(),
                    'Pending original assignment has execution artifacts')
        inputs[row['id']] = prepared_files(source)
        for name in inputs[row['id']]:
            destination = target/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((source/name).read_bytes())
    shutil.copytree(original_root/'reference-reviews', output/'reference-reviews')
    m = deepcopy(original)
    m['source_sha256'] = campaign.historical.sources()
    m['continuation'] = dict(format=VERSION, created=now(),
        controller=binding(CONTROLLER), revision=binding(revision/'report.json'),
        original_manifest=binding(original_root/'manifest.json'),
        provider_controls=binding(Path(provider_controls)/'report.json'),
        verdict_version=verdict_migration.VERSION,
        consumed_prefix_ids=[r['id'] for r in revised['rows']],
        remaining_sessions=228, maximum_new_model_requests=3648,
        original_maximum_model_requests=3840, prepared_files=inputs,
        migration_verification=proof)
    write_json(output/'manifest.json',m)
    (output/'manifest.sha256').write_text(sha(output/'manifest.json')+'\n')
    # Prevent the historical 240-slot launcher from replaying this derived manifest.
    write_json(output/'launch.json',dict(format='reserved-continuation-entrypoint-v1',
        dispatched=False, required_entrypoint='confirmation_continuation.py',
        manifest_sha256=sha(output/'manifest.json')))
    atomic_json(output/'progress.json',dict(state='prepared_not_dispatched',rows=initial_rows))
    return m


def check(output):
    output = Path(output)
    m = read(output/'manifest.json')
    require((output/'manifest.sha256').read_text().strip() == sha(output/'manifest.json'),
            'Continuation manifest changed')
    c = m['continuation']
    require(c['format']==VERSION and c['verdict_version']==verdict_migration.VERSION
            and (c['remaining_sessions'],c['maximum_new_model_requests'],
                 c['original_maximum_model_requests'])==(228,3648,3840),
            'Continuation policy or budgets changed')
    require(bound(c['controller']) == CONTROLLER, 'Another continuation controller')
    revision = bound(c['revision']).parent
    original_path = bound(c['original_manifest'])
    proof = migration.verify_migration(revision)
    require(proof == c['migration_verification'], 'Migration proof changed')
    revised, original = read(revision/'report.json'), read(original_path)
    require(Path(revised['campaign']) == original_path.parent, 'Another original campaign')
    expected = deepcopy(original)
    expected['source_sha256'] = campaign.historical.sources()
    expected['continuation'] = c
    require(m == expected, 'Continuation changed frozen campaign parameters or assignments')
    rows = prefix_rows(original,revised,revision)
    require(c['consumed_prefix_ids']==[r['id'] for r in rows[:12]], 'Consumed prefix changed')
    require(set(c['prepared_files'])=={r['id'] for r in rows}, 'Input inventory incomplete')
    for row in rows:
        folder = output/row['path']
        require(prepared_files(folder)==c['prepared_files'][row['id']]
                ==prepared_files(original_path.parent/row['path']), 'Prepared inputs changed')
    reserved = read(output/'launch.json')
    require(reserved==dict(format='reserved-continuation-entrypoint-v1',
        dispatched=False, required_entrypoint='confirmation_continuation.py',
        manifest_sha256=sha(output/'manifest.json')), 'Legacy launch protection changed')
    controls = bound(c['provider_controls']).parent
    require(sha(controls/'report.json')==read(original_path.parent/'launch.json')['provider_controls_sha256'],
            'Provider qualification differs from original launch')
    evidence = read(controls/'report.json')
    require(evidence['status']=='passed' and len(evidence['rows'])==4
            and {(r['model'],r['arm']) for r in evidence['rows']}==
                {(model,arm) for model in campaign.MODELS for arm in campaign.ARMS},
            'Four original provider controls required')
    for row in evidence['rows']:
        require(campaign.delivery(controls/(row['model']+'-'+row['arm']),row['model'],
            row['arm'],m['request_setups'][row['model']])==row, 'Provider proof changed')
    # Reuse the original runtime, reference, 40-control and 12-E2E checks.
    ready = campaign.check(output)
    require(ready['technical_status']=='passed', 'Technical qualification incomplete')
    ready['historical_launch_marker_present'] = ready.pop('live_campaign_dispatched')
    ready['live_campaign_dispatched'] = (output/'continuation-launch.json').exists()
    return dict(status='passed', migration=proof, readiness=ready,
                remaining_sessions=228, maximum_new_model_requests=3648)


def fresh_progress(output, m):
    require(not (output/'continuation-launch.json').exists(), 'Continuation already consumed')
    c = m['continuation']
    expected = prefix_rows(read(bound(c['original_manifest'])),
                           read(bound(c['revision'])),Path(c['revision']['path']).parent)
    p = read(output/'progress.json')
    require(p==dict(state='prepared_not_dispatched',rows=expected),
            'Continuation progress is not fresh; no automatic retry')
    for row in expected:
        folder = output/row['path']
        require(not (folder/'runs').exists() and not (folder/'summary.json').exists(),
                'Prepared assignment already has execution evidence')
    return p


def assess(output, m, row):
    folder = output/row['path']
    result = execute(folder,request_setup=m['request_setups'][row['model']])
    require(result['tasks'][0]['builder_status']=='completed','Builder incomplete; slot consumed')
    task = folder/'runs'/row['case']
    raw, provenance = submission(task/'builder',row['case'])
    require(raw==(task/'candidate.py').read_bytes(), 'Final submission bytes changed')
    index, reference = Path(m['data_index']['path']), m['references'][row['case']]
    baseline = evaluate(row['case'],task/'assessment',index=index,
        candidate=task/'candidate.py',provenance=provenance,
        evaluator_protocol=CONFIRMATION_PROTOCOL,reference=reference)
    require(baseline['cleanup_confirmed'] is True, 'Assessment cleanup unconfirmed')
    legacy = review_assessment(task/'assessment',index,reference=reference)
    write_json(task/'assessment/review.json',legacy)
    revised = verdict_migration.revise(task/'assessment',index,reference)
    write_json(task/'assessment/revised-verdict.json',revised)
    verdict = revised['verdict']
    require(verdict['evidence_status']=='coherent' and verdict['score'] is not None,
            'Unscored evaluation incident; pause before next slot')
    return revised


def guard(output, m, row):
    require(sha(output/'manifest.json')==(output/'manifest.sha256').read_text().strip(),
            'Continuation manifest changed during execution')
    bound(m['continuation']['controller'])
    require(campaign.historical.sources()==m['source_sha256'], 'Frozen implementation changed')
    bound(m['data_index'])
    require(prepared_files(output/row['path'])==m['continuation']['prepared_files'][row['id']],
            'Session inputs changed')
    require(shutil.disk_usage(output).free>=10*1024**3,'Disk reserve below 10 GiB')


def dispatch(output, maximum_requests):
    output = Path(output).resolve()
    require(maximum_requests==3648, 'Declare the 3648-request continuation ceiling')
    m = read(output/'manifest.json')
    progress = fresh_progress(output,m)
    readiness = check(output)
    # Exclusive claim lives beside the sealed migration files. Even a second
    # prepared continuation directory cannot consume the suffix again.
    claim = Path(m['continuation']['revision']['path']).parent/'continuation-claim.json'
    launch = dict(format=VERSION,started=now(),output=str(output),
        maximum_new_model_requests=maximum_requests,
        manifest_sha256=sha(output/'manifest.json'),controller_sha256=sha(CONTROLLER),
        original_manifest=m['continuation']['original_manifest'],
        revision=m['continuation']['revision'])
    with claim.open('x') as stream:
        json.dump(launch,stream,indent=2)
    write_json(output/'readiness.json',readiness)
    write_json(output/'continuation-launch.json',launch)
    progress.update(state='running',started=launch['started'])
    atomic_json(output/'progress.json',progress)
    active = None
    try:
        for row in progress['rows'][12:]:
            guard(output,m,row)
            active = row
            row.update(state='started',started=now())
            atomic_json(output/'progress.json',progress)
            revised = assess(output,m,row)
            verdict = revised['verdict']
            row.update(state='finished',finished=now(),score=verdict['score'],
                strict_correct=verdict['strict_correct'],decision=revised['decision'],
                verdict_path=str(output/row['path']/'runs'/row['case']/'assessment/revised-verdict.json'))
            active = None
            atomic_json(output/'progress.json',progress)
            print(json.dumps(dict(id=row['id'],state='finished',score=row['score'],
                                  strict_correct=row['strict_correct'])),flush=True)
        progress.update(state='complete',finished=now())
    except BaseException as exc:
        if active is not None:
            active.update(state='incident',finished=now(),reason=str(exc))
        progress.update(state='stopped',reason=str(exc),finished=now())
        print(json.dumps(dict(state='stopped',reason=str(exc),
                              active_id=active['id'] if active else None)),flush=True)
        if not isinstance(exc,Exception):
            raise
    finally:
        atomic_json(output/'progress.json',progress)
    return progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','check','run'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--migration',type=Path)
    parser.add_argument('--provider-controls',type=Path)
    parser.add_argument('--maximum-model-requests',type=int)
    args = parser.parse_args()
    if args.action=='prepare':
        if not args.migration or not args.provider_controls:
            parser.error('Preparation requires migration and provider controls')
        value = prepare(args.output,args.migration,args.provider_controls)
        print(json.dumps(dict(status='prepared',remaining=value['continuation']['remaining_sessions'])))
    elif args.action=='check':
        print(json.dumps(check(args.output),indent=2))
    else:
        value = dispatch(args.output,args.maximum_model_requests)
        print(value['state'])
        if value['state']!='complete':
            raise SystemExit(1)


if __name__=='__main__':
    main()
