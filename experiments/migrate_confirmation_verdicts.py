"""Migrate a stopped confirmation prefix from retained evidence; no live dispatch."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from builder.context import write_json
from evaluation.candidates import receipts, verdict_migration
from evaluation.confirmation import references
from evaluation.scientific.records import require
from evaluator.run import digest
from evaluator.transport_input import read_regular
from experiments import dashboard_campaign as historical
from experiments.region_confirmation import MODELS, ARMS
from prompts.confirmation import TASKS, suite

QUALIFICATION = Path('docs/experiments/lost-particle-qualification-v1.json')
QUALIFICATION_SHA256 = 'd20a8d2078471b64081686329837a4a561c42906dedc462d6d0f87a310cd83cd'
ADDITIONS = {'evaluation/candidates/lost_particles.py', 'experiments/qualify_lost_particles.py',
             'evaluation/candidates/verdict_migration.py', 'experiments/migrate_confirmation_verdicts.py'}
IMMUTABLE_ROW = ('id','model','arm','case','repeat','path','plan_sha256')


def inventory(root):
    values = {}
    require(root.is_dir() and not root.is_symlink(), 'Expected an ordinary evidence directory')
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(), 'Evidence directory contains a symlink')
        if p.is_file():
            values[str(p.relative_to(root))] = digest(read_regular(p, limit=32_000_000))
    return values


def source_revision(recorded, current, qualification):
    require(set(current) == set(recorded) | ADDITIONS, 'Unexpected source inventory change')
    allowed = {'evaluation/candidates/phase_evidence.py'}
    require(all(current[p] == sha for p,sha in recorded.items() if p not in allowed),
            'Frozen implementation changed outside qualified attribution')
    for p,sha in qualification['implementation'].items():
        require(digest(Path(p).read_bytes()) == sha, 'Qualified policy implementation changed')
        if p in current:
            require(current[p] == sha, 'Qualified source binding changed')
    require(all(current[p] == qualification['implementation'][p] for p in allowed),
            'Unqualified phase-evidence change')


def consumed_rows(manifest, progress):
    rows = manifest['rows']
    require(len(rows) == len(progress['rows']) == 240, 'Assignment count changed')
    require(len({r['id'] for r in rows}) == 240, 'Duplicate assignment identifier')
    expected = {(m,a,c,n) for m in MODELS for a in ARMS for c in TASKS for n in range(1,6)}
    require({(r['model'],r['arm'],r['case'],r['repeat']) for r in rows} == expected,
            'Assignment matrix changed')
    require(progress['state'] == 'stopped', 'Migration requires a stopped campaign')
    consumed = []
    pending_seen = False
    for original, state in zip(rows, progress['rows']):
        require(all(original[k] == state[k] for k in IMMUTABLE_ROW),
                'Assignment identity or order changed')
        path = Path(original['path'])
        require(not path.is_absolute() and '..' not in path.parts and path.parts[0] == 'runs',
                'Assignment path outside campaign')
        require(state['state'] in ('finished','incident','pending'), 'Unresolved active assignment')
        if state['state'] == 'pending':
            pending_seen = True
        else:
            require(not pending_seen, 'Consumed assignments are not a prefix')
            consumed.append(state)
    require(consumed, 'No consumed assignments to reconstruct')
    return consumed


def bindings(campaign):
    manifest = receipts.read(campaign/'manifest.json')
    require((campaign/'manifest.sha256').read_text().strip() == historical.sha(campaign/'manifest.json'),
            'Campaign manifest changed')
    require(receipts.read(campaign/'launch.json')['manifest_sha256'] == historical.sha(campaign/'manifest.json'),
            'Launch binding changed')
    require(manifest['format'] == 'region-confirmation-campaign-v1'
            and (manifest['sessions'],manifest['maximum_model_requests'],
                 manifest['authoring_seconds'],manifest['automatic_retries']) == (240,3840,600,0),
            'Campaign identity or budgets changed')
    require(manifest['evaluator_identity'] == references.identity()
            and manifest['suite_manifest_sha256'] == suite()[1]
            and manifest['protocol_sha256'] == historical.sha(references.PROTOCOL),
            'Reference evaluator, specification or criteria changed')
    require(historical.sha(QUALIFICATION) == QUALIFICATION_SHA256, 'Qualification record changed')
    qualification = receipts.read(QUALIFICATION)
    require(qualification['status'] == 'passed' and qualification['native_controls_passed'] == 2,
            'Lost-particle policy not qualified')
    source_revision(manifest['source_sha256'], historical.sources(), qualification)
    index = Path(manifest['data_index']['path'])
    require(historical.sha(index) == manifest['data_index']['sha256'], 'Data index changed')
    require(set(manifest['references']) == set(TASKS), 'Reference inventory changed')
    for case,path in manifest['references'].items():
        goal = references.target(case,path,None)
        require(goal['index']['manifest_sha256'] == manifest['reference_states'][case]['manifest_sha256'],
                'Reference package changed')
    progress = receipts.read(campaign/'progress.json')
    consumed = consumed_rows(manifest,progress)
    for row in manifest['rows']:
        require(historical.sha(campaign/row['path']/'plan.json') == row['plan_sha256'],
                'Session plan changed')
    return manifest, progress, consumed, index


def reconstruct(campaign, manifest, row, index):
    folder = campaign/row['path']/'runs'/row['case']/'assessment'
    assignment = receipts.read(folder/'assignment.json')
    require(assignment['case'] == row['case'], 'Assessment assigned to another task')
    # Bind the assessed source to the original builder, not just a copied report.
    from builder.submission import submission
    raw, provenance = submission(folder.parent/'builder', row['case'])
    builder = receipts.read(folder.parent/'builder/manifest.json')
    require(builder['model'] == row['model'] and builder['assistance'] == ARMS[row['arm']],
            'Builder model or assistance differs from assignment')
    require(raw == read_regular(folder/'candidate.py')
            and raw == read_regular(folder.parent/'candidate.py')
            and assignment['provenance'] == provenance, 'Final candidate provenance changed')
    value = verdict_migration.revise(folder,index,manifest['references'][row['case']])
    old = value['legacy_reconstruction']
    if row['state'] == 'finished':
        require(old['evidence_status'] == 'coherent' and old['score'] == row['score']
                and old['strict_correct'] is row['strict_correct'],
                'Consumed outcome contradicts reconstructed evidence')
    return value


def summary(rows, pending):
    counts = Counter('protocol_success' if r['verdict']['strict_correct'] is True
                     else 'evaluated_failure' for r in rows)
    return dict(protocol_success=counts['protocol_success'], evaluated_failure=counts['evaluated_failure'],
                unscored_incident=0, pending=pending)


def migrate(campaign, output):
    campaign, output = Path(campaign).resolve(), Path(output).resolve()
    require(not output.exists(), 'Migration output must be fresh')
    require(campaign not in output.parents, 'Write migration outside original campaign')
    manifest, progress, consumed, index = bindings(campaign)
    before = inventory(campaign)
    implementation = historical.sources()
    output.mkdir(parents=True)
    (output/'verdicts').mkdir()
    write_json(output/'original-evidence-sha256.json',before)
    for name in ('manifest.json','manifest.sha256','progress.json','launch.json'):
        (output/('original-'+name)).write_bytes(read_regular(campaign/name,limit=32_000_000))
    for name in implementation:
        p=output/'implementation'/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(Path(name).read_bytes())
    report = dict(format='confirmation-verdict-migration-v1',version=verdict_migration.VERSION,
        policy=verdict_migration.lost_particles.POLICY, created=datetime.now(timezone.utc).isoformat(),
        status='running', campaign=str(campaign), original_manifest_sha256=historical.sha(campaign/'manifest.json'),
        original_progress_sha256=historical.sha(campaign/'progress.json'),
        qualification_sha256=QUALIFICATION_SHA256, implementation=implementation,
        new_model_calls=0,new_native_transports=0,campaign_resumed=False,
        original_evidence_modified=False,rows=[])
    write_json(output/'report.json',report)
    try:
        for row in consumed:
            value=reconstruct(campaign,manifest,row,index)
            target=output/'verdicts'/(row['id']+'.json')
            write_json(target,value)
            report['rows'].append(dict(**{k:row[k] for k in IMMUTABLE_ROW},
                original_state=row['state'],decision=value['decision'],verdict=value['verdict'],
                revised_record_sha256=historical.sha(target)))
            write_json(output/'report.json',report)
            print(row['id']+': '+value['decision']+'; score='+str(value['verdict']['score']),flush=True)
        require(historical.sources()==implementation,'Implementation changed during migration')
        require(inventory(campaign)==before,'Original evidence changed during migration')
        report.update(status='passed',original_evidence_unchanged=True,
            original_evidence_files_verified=len(before),
            counts=summary(report['rows'],240-len(consumed)),
            changed_ids=[r['id'] for r in report['rows'] if r['decision']!='unchanged_after_reconstruction'])
    except Exception as exc:
        report.update(status='failed',reason=str(exc),error_type=type(exc).__name__)
        raise
    finally:
        write_json(output/'report.json',report)
    (output/'report.sha256').write_text(historical.sha(output/'report.json')+'\n')
    return report


def verify_migration(output):
    output=Path(output)
    report=receipts.read(output/'report.json')
    require(report['status']=='passed' and report['version']==verdict_migration.VERSION
            and report['policy']==verdict_migration.lost_particles.POLICY
            and report['qualification_sha256']==QUALIFICATION_SHA256,
            'Migration is not complete')
    require((output/'report.sha256').read_text().strip()==historical.sha(output/'report.json'),
            'Migration report changed')
    require(report['implementation']==historical.sources(),'Migration implementation changed')
    for name,sha in report['implementation'].items():
        require(historical.sha(output/'implementation'/name)==sha,'Implementation snapshot changed')
    require(report['new_model_calls']==0 and report['new_native_transports']==0
            and report['campaign_resumed'] is False and report['original_evidence_modified'] is False
            and report['original_evidence_unchanged'] is True, 'Migration execution boundary changed')
    campaign=Path(report['campaign'])
    before=inventory(campaign)
    require(before==receipts.read(output/'original-evidence-sha256.json'),'Original evidence changed')
    require(report['original_evidence_files_verified']==len(before), 'Evidence count changed')
    for name in ('manifest.json','manifest.sha256','progress.json','launch.json'):
        require(read_regular(output/('original-'+name),limit=32_000_000)==read_regular(campaign/name,limit=32_000_000),
                'Original control snapshot changed')
    manifest,progress,consumed,index=bindings(campaign)
    require(report['original_manifest_sha256']==historical.sha(campaign/'manifest.json')
            and report['original_progress_sha256']==historical.sha(campaign/'progress.json'),
            'Original campaign binding changed')
    require([r['id'] for r in report['rows']]==[r['id'] for r in consumed],
            'Migration omitted or duplicated consumed assignments')
    for row,saved in zip(consumed,report['rows']):
        require(all(saved[k]==row[k] for k in IMMUTABLE_ROW)
                and saved['original_state']==row['state'],'Migrated assignment identity changed')
        value=reconstruct(campaign,manifest,row,index)
        path=output/'verdicts'/(row['id']+'.json')
        require(receipts.read(path)==value and historical.sha(path)==saved['revised_record_sha256']
                and value['decision']==saved['decision'] and value['verdict']==saved['verdict'],
                'Migrated verdict contradicts reconstruction')
    require(report['counts']==summary(report['rows'],240-len(consumed)),'Migration counts changed')
    require(report['changed_ids']==[r['id'] for r in report['rows']
            if r['decision']!='unchanged_after_reconstruction'],'Changed-outcome inventory changed')
    require(inventory(campaign)==before,'Original evidence changed during review')
    return dict(status='passed',verdicts_verified=len(consumed),counts=report['counts'],
                original_evidence_unchanged=True,campaign_resumed=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('migrate','verify'))
    p.add_argument('--campaign',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.action=='migrate':
        if not a.campaign:p.error('Migration requires --campaign')
        result=migrate(a.campaign,a.output)
    else:result=verify_migration(a.output)
    print(result['status'])


if __name__=='__main__':
    main()
