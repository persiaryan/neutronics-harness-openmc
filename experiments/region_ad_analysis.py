"""Read-only A/D outcome analysis and hash-bound manual mechanism annotations."""
import argparse
from collections import Counter
import json
from pathlib import Path

from builder.context import sha256
from evaluator.transport_input import read_regular
from evaluation.candidates.verify import review_assessment
from experiments.region_ad import verify_plan, read, require
from experiments.run import atomic_json


def annotation(output, row, value):
    """Validate traceability of a human judgment; never infer semantics from syntax."""
    source = output/row['path']/'runs'/row['case']/'candidate.py'
    status = value['status']
    require(status in ('pending','demonstrated','not_observed_within_reviewed_scope','unassessable'),
            'Unknown mechanism annotation')
    if status == 'pending':
        return status
    require(isinstance(value.get('reviewer'),str) and value['reviewer'].strip(), 'Annotation reviewer missing')
    actual = sha256(read_regular(source)) if source.exists() or source.is_symlink() else None
    require(value.get('source_sha256') == actual, 'Annotation source identity changed')
    require(isinstance(value.get('limitations'),str) and value['limitations'].strip(),
            'Document annotation coverage and limitations')
    if status == 'unassessable':
        return status
    require(actual is not None, 'A missing submission cannot establish presence or absence of the defect')
    for key in ('sharing','mutation','downstream_use','damaging_consequence'):
        require(isinstance(value.get(key),str) and value[key].strip(), 'Mechanism review incomplete: '+key)
    evidence = value.get('evidence',[])
    require(evidence, 'Annotation evidence missing')
    source_cited = False
    for item in evidence:
        path = Path(item['path'])
        require(not path.is_absolute() and '..' not in path.parts, 'Annotation path must be campaign-relative')
        target = output/path
        require(target.resolve().is_relative_to(output.resolve()) and not target.is_symlink(),
                'Annotation evidence outside campaign')
        require(sha256(read_regular(target)) == item['sha256'], 'Annotation evidence changed')
        lines = item['lines']
        require(len(lines)==2 and all(type(n) is int for n in lines)
                and 1 <= lines[0] <= lines[1] <= len(target.read_text().splitlines()),
                'Annotation line references invalid')
        source_cited |= target.resolve() == source.resolve()
    require(source_cited, 'Annotation must cite the frozen submitted source')
    return status


def summarize(output, annotations=None):
    output = Path(output)
    manifest = verify_plan(output)
    progress = read(output/'progress.json')
    states = {r['id']:r for r in progress['rows']}
    require(len(states)==36 and set(states)=={r['id'] for r in manifest['rows']},
            'Progress assignment inventory changed')
    judgments = {}
    if annotations is not None:
        value = read(annotations)
        require(value['format']=='region-ad-annotations-v1'
                and value['protocol_sha256']==manifest['region_ad_protocol']['sha256']
                and value['campaign_manifest_sha256']==sha256((output/'manifest.json').read_bytes()),
                'Annotation study/protocol binding changed')
        judgments = {r['id']:r for r in value['records']}
        require(len(judgments)==len(value['records']) and set(judgments)<=set(states),
                'Annotation IDs duplicate or unknown')
    rows = []
    for row in manifest['rows']:
        root = output/row['path']
        folder = root/'runs'/row['case']
        state = states[row['id']]['state']
        consumed = (root/'dashboard-run.json').exists() or state != 'pending'
        review = review_assessment(folder/'assessment',Path(manifest['data_index'])) if (folder/'assessment/report.json').exists() else {}
        scored = review.get('evidence_status')=='coherent' and review.get('score') is not None
        terminal = state in ('finished','incident')
        outcome = ('protocol_success' if scored and review.get('strict_correct') is True else
                   'evaluated_failure' if scored else 'unscored_incident' if consumed and terminal else 'pending')
        mechanism = annotation(output,row,judgments[row['id']]) if row['id'] in judgments else (
            'unassessable' if terminal and not (folder/'candidate.py').is_file() else 'pending')
        authoring = read(folder/'builder/result.json') if (folder/'builder/result.json').exists() else {}
        assessment_report = read(folder/'assessment/report.json') if (folder/'assessment/report.json').exists() else {}
        rows.append(dict(id=row['id'],model=row['model'],case=row['case'],arm=row['arm'],
            consumed=consumed,outcome=outcome,mechanism=mechanism,
            evidence_status=review.get('evidence_status'), requests_received=authoring.get('request_count'),
            completed_provider_responses=sum(1 for p in (folder/'builder').glob('upstream-*.json')
                                            if read(p).get('completion_observed') is True) if authoring else None,
            authoring_seconds=authoring.get('elapsed_seconds'),
            assessment_seconds=assessment_report.get('elapsed_seconds'),
            checks=assessment_report.get('checks') if scored else None,
            operational_state=state))
    groups=[]
    for model in manifest['models']:
        for case in manifest['cases']:
            for arm in ('A','D'):
                cell=[r for r in rows if (r['model'],r['case'],r['arm'])==(model,case,arm)]
                outcomes=Counter(r['outcome'] for r in cell)
                successes=outcomes['protocol_success'];scored=successes+outcomes['evaluated_failure']
                efforts={}
                for name in ('requests_received','completed_provider_responses','authoring_seconds','assessment_seconds'):
                    eligible=[r for r in cell if r['consumed']]
                    values=[r[name] for r in eligible if type(r[name]) in (int,float)]
                    efforts[name]=dict(total=sum(values) if values else None, available=len(values),
                                       missing=len(eligible)-len(values))
                groups.append(dict(model=model,case=case,arm=arm,planned=len(cell),
                    consumed=sum(r['consumed'] for r in cell),
                    outcomes={k:outcomes[k] for k in ('protocol_success','evaluated_failure','unscored_incident','pending')},
                    protocol_success_fraction=successes/len(cell) if not outcomes['pending'] else None,
                    conditional_success_fraction_scored=successes/scored if scored else None,
                    mechanism_counts={k:sum(r['mechanism']==k for r in cell) for k in
                                      ('demonstrated','not_observed_within_reviewed_scope','unassessable','pending')},
                    effort=efforts))
    comparisons=[]
    for model in manifest['models']:
        selected=[g for g in groups if g['model']==model]
        complete=all(g['protocol_success_fraction'] is not None for g in selected)
        rates={a:sum(g['protocol_success_fraction'] for g in selected if g['arm']==a)/3
               for a in ('A','D')} if complete else {}
        comparisons.append(dict(model=model,complete=complete,task_weighted_rates=rates,
                                D_minus_A=rates['D']-rates['A'] if complete else None))
    return dict(format='region-ad-analysis-v1',protocol_sha256=manifest['region_ad_protocol']['sha256'],
        manifest_sha256=sha256((output/'manifest.json').read_bytes()),rows=rows,groups=groups,
        comparisons=comparisons,grading_enabled=False,
        interpretation='Descriptive reused-task pilot. Manual annotations explain mechanisms; no causal claim from loaders or syntactic counts.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--annotations',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(not args.output.exists(),'Use a fresh analysis output')
    result=summarize(args.campaign,args.annotations)
    atomic_json(args.output,result)
    print(json.dumps(dict(groups=len(result['groups']),status='written',comparisons=result['comparisons'])))
