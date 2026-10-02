"""Copy the sealed Request-16 archive for local viewing; never run its code."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil

from dashboard.campaign import read_records, campaign
from dashboard.contracts import normalize_evaluation


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def import_study(locations, output):
    locations = json.loads(Path(locations).read_text())
    root = Path(locations['source_root']).resolve()
    base = root/'evidence/abc-temperature-amendment-v1'
    closeout = json.loads((base/'closeout-02/verification.json').read_text())
    seal_path = base/'closeout-02/seal.json'
    if sha(seal_path) != closeout['seal_sha256']:
        raise ValueError('Archive seal changed')
    inventory = json.loads(seal_path.read_text())['inventory']
    for path, expected in closeout['analysis_files'].items():
        if sha(root/path) != expected:
            raise ValueError('Archived analysis changed: '+path)
    analysis = json.loads((base/'analysis-02/analysis.json').read_text())
    if not analysis['complete'] or len(analysis['trials']) != 150:
        raise ValueError('Expected the complete sealed Request-16 study')
    indexed = {r['id']:r for r in locations['records']}
    if set(indexed) != {r['id'] for r in analysis['trials']}:
        raise ValueError('Recovered locations differ from sealed study')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    roots = []
    copied = {}

    def copy(source, destination):
        source = Path(source)
        relative = source.relative_to(root)
        if source.is_symlink() or any(p.is_symlink() for p in source.parents if p != root.parent):
            raise ValueError('Linked archive evidence is not imported')
        if not source.is_file() or sha(source) != inventory.get(str(relative)):
            raise ValueError('Unsealed or changed source: '+str(relative))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied[str(destination.relative_to(output))] = dict(source=str(source), sha256=sha(destination))

    def tree(source, destination):
        # Native binaries are not served by the dashboard. All copied content is
        # sealed text evidence; no candidate or archived helper is imported.
        for path in sorted(source.rglob('*')):
            if path.is_file() and path.suffix in ('.json','.jsonl','.sse','.txt','.xml','.csv','.py','.md'):
                if str(path.relative_to(root)) in inventory:
                    copy(path, destination/path.relative_to(source))

    for row in analysis['trials']:
        ident, case = row['id'], row['case']
        if Path(ident).name != ident or Path(case).name != case:
            raise ValueError('Invalid archived assignment identity')
        inherited = row['order'] <= 38
        original = (root/'evidence/abc-request16-development-v1/study-01' if inherited else base/'study-01')/'trials'/ident
        target = output/ident
        target.mkdir()
        roots.append(target)
        for name in ('plan.json','summary.json','result.json'):
            if (original/name).exists(): copy(original/name, target/name)
        tree(original/'inputs', target/'inputs')
        task = original/'runs'/case
        tree(task/'builder', target/'runs'/case/'builder')
        for name in ('candidate.py','provenance.json'):
            if (task/name).exists(): copy(task/name, target/'runs'/case/name)
        if row.get('assessment_evidence'):
            relative = Path(row['assessment_evidence'])
            selected = (root if relative.parts[0]=='evidence' else base/'study-01')/relative
            folder = target/'runs'/case/'assessment'
            tree(selected.parent, folder)
            review = selected.with_name('verification.json' if inherited else 'review.json')
            if inherited: copy(review, folder/'review.json')
            report = json.loads((folder/'report.json').read_text())
            reviewed = json.loads((folder/'review.json').read_text())
            view = normalize_evaluation(report, reviewed)
            if not view['trusted'] or report['diagnostic_score']['score'] != row['diagnostic_score']:
                raise ValueError('Archived score/review differs from sealed analysis: '+ident)

    records, warnings = read_records(roots)
    if warnings: raise ValueError('Imported records contain read warnings')
    contexts, signatures = defaultdict(dict), defaultdict(set)
    for record in records:
        if record['definition']:
            contexts[record['context']['model']][record['cohort']] = record
            signatures[(record['context']['model'],record['case'])].add(record['task_signature'])
    if any(len(v)!=1 for v in contexts.values()) or any(len(v)!=1 for v in signatures.values()):
        raise ValueError('Archived comparisons have conflicting identities')
    for target, record, row in zip(roots, records, analysis['trials']):
        template = next(iter(contexts[record['context']['model']].values()))
        bindings = {}
        for name in ['plan.json','result.json',f'runs/{row["case"]}/builder/manifest.json',
                     f'runs/{row["case"]}/assessment/report.json',f'runs/{row["case"]}/assessment/review.json']:
            path = target/name
            bindings[name] = sha(path) if path.exists() else None
        write(target/'dashboard-study-context.json', dict(format='dashboard-study-context-v1',
            study_id='request16-historical-v7', origin=str(base), assessment_protocol='factory-assessment-boundaries-v7',
            inherited_authoring=row['order']<=38, terminal_category=row['category'],
            context=template['context'], definition=template['definition'],
            task_signature=next(iter(signatures[(record['context']['model'],record['case'])])),bindings=bindings,
            interpretation='Imported sealed historical evidence; intended study identities do not supply missing verdicts.'))
    result = campaign(roots)
    expected={'gpt-5.6-luna':{'A':18,'B':17,'C':14},'gpt-5.6-sol':{'A':23,'B':25,'C':21}}
    if len(result['cohorts']) != 2: raise ValueError('Expected two historical model cohorts')
    for cohort in result['cohorts']:
        for arm, passed in expected[cohort['context']['model']].items():
            stats=cohort['groups'][arm]['domains']['overall']
            if stats['n']!=25 or stats['passed']!=passed:
                raise ValueError('Imported campaign disagrees with frozen study counts')
    write(output/'campaign.json',dict(runs=[str(p) for p in roots]))
    write(output/'import-receipt.json',dict(format='dashboard-archive-import-v1',source=str(base),files=copied,
        assessment_selection='Original authoring; selected v7 assessments; verification.json copied byte-for-byte as review.json for inherited sessions.',
        source_seal_sha256=sha(seal_path),new_model_calls=0,new_native_runs=0))
    write(output/'campaign-state.json',result)
    return output/'campaign.json'


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--locations',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(import_study(args.locations,args.output))
