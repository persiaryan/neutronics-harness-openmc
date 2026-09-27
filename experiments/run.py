"""Prepare or execute the bounded usability pilot. Preparation never dispatches a model."""
import argparse
import json
import os
import tempfile
from pathlib import Path
from builder import run as agent
from builder.submission import submission
from builder.route import CONDITIONS, GUIDED_CONDITIONS, BOUNDARY_CONDITIONS, SMOKE_CONDITIONS, condition_prompt, request_limit, EXTENDED_REQUEST_BUDGET
from builder.trajectory import summarize as trajectory
from builder.context import sha256
from evaluator import run as exporter
from evaluator.contracts import FACTORY
from evaluator.profiles import PROFILE, FACTORY_PROFILE, BOUNDARY_PROTOCOL
from evaluation.scientific.boundary_scope import task_matrix
from prompts.prepare import prepare as prepare_prompt, CASE_FILES

BUDGETS = dict(model_requests=8, authoring_seconds=600, boundary_calls=2, boundary_seconds=120,
               export_seconds=60, automatic_retries=0)


def budgets(assistance, request_budget=None):
    declared = dict(BUDGETS, model_requests=request_limit(request_budget))
    if assistance in SMOKE_CONDITIONS:
        from evaluator.smoke import PROFILE
        return dict(declared,smoke_calls=PROFILE['max_calls'],smoke_native_seconds=PROFILE['native_seconds'])
    return declared


def atomic_json(path, value):
    """Replace one summary atomically; retained phase artifacts stay untouched."""
    path = Path(path)
    raw = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def prepare(output, *, assistance, model='gpt-5.6-luna', cases=('reflective_pin_cell','moderated_cylinder'),smoke_data_index=None,
            request_budget=None):
    declared = budgets(assistance, request_budget)
    if assistance not in CONDITIONS or not cases or len(set(cases)) != len(cases) or set(cases)-set(CASE_FILES):
        raise ValueError('Invalid condition or task inventory')
    if (assistance in SMOKE_CONDITIONS)!=(smoke_data_index is not None):
        raise ValueError('Declare smoke data only with the explicit smoke condition')
    smoke_config=None
    if smoke_data_index is not None:
        from builder.smoke_tool import identity
        index,_=exporter.data_directory(Path(smoke_data_index))
        smoke_config=dict(adapter=identity(),data_index=str(index),data_index_sha256=sha256(index.read_bytes()))
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    prompts = {case: prepare_prompt(case, output/'inputs'/case) for case in cases}
    plan = dict(format='research-usability-pilot-v2', status='prepared_not_dispatched', model=model,
        adapter='codex_subscription', assistance=assistance, cases=list(cases), prompts=prompts,
        delivery_contract=FACTORY, execution_profile=PROFILE, evaluator_protocol=BOUNDARY_PROTOCOL,
        budgets=declared, maximum_model_requests=len(cases)*declared['model_requests'],
        strict_tool_free_baseline=False, formal_efficacy_study=False, transport=False,
        resource_policy='Same authoring wall/request budgets. Inspection uses this wall budget plus its own call cap. No retries.',
        tool_use_policy='Optional and recorded, never rewarded. Unsupported cylinder tests interpretation of limits.')
    if assistance in GUIDED_CONDITIONS:
        plan['tool_use_policy'] = ('Guided working export; boundary inspection additionally instructed only in '
                                   'guided_boundaries. Workflow is not guaranteed or scientifically scored.')
    if smoke_config:
        plan.update(smoke=smoke_config,authoring_native_transport=True,
            resource_policy='Same 8-request/600-second session, including boundary and smoke calls. Separate declared per-tool caps. No automatic retries.',
            tool_use_policy='Guided export, boundary inspection and smoke execution; one smoke correction opportunity. Observed use is not scientific credit.')
    plan['condition'] = CONDITIONS[assistance]
    if request_budget is not None:
        plan['request_budget_profile'] = request_budget
        plan['resource_policy'] = plan['resource_policy'].replace('8-request', str(declared['model_requests'])+'-request')
    plan['authoring_prompt_sha256'] = {case: sha256(condition_prompt((output/'inputs'/case/'prompt.txt').read_text(), assistance,
        request_budget=request_budget).encode()) for case in cases}
    exporter.write_json(output/'plan.json', plan)
    exporter.write_json(output/'support-matrix.json', task_matrix())
    return plan


def execute(output, *, responder=None, request_setup=None):
    output = Path(output)
    plan = json.loads((output/'plan.json').read_bytes())
    if plan.get('authoring_allowed') is False:
        raise ValueError('Authoring slot already consumed; retained submissions may only be reassessed')
    if plan.get('format') != 'research-usability-pilot-v2':
        raise ValueError('Prepare a new v2 plan; historical plans are not relabelled')
    request_budget = plan.get('request_budget_profile')
    declared = budgets(plan['assistance'], request_budget)
    total_requests = plan['maximum_model_requests']
    if type(total_requests) is not int or total_requests != len(plan['cases'])*declared['model_requests']:
        raise ValueError('Prepared total request budget changed')
    if plan['status'] != 'prepared_not_dispatched' or plan['budgets'] != declared or plan['execution_profile'] != PROFILE:
        raise ValueError('Pilot plan/budgets changed')
    if plan['delivery_contract'] != FACTORY or plan['evaluator_protocol'] != BOUNDARY_PROTOCOL or plan['transport'] is not False:
        raise ValueError('Unexpected pilot contract/protocol')
    if plan['assistance'] not in CONDITIONS:
        raise ValueError('Unknown assistance condition')
    smoke_kwargs={}
    if plan['assistance'] in SMOKE_CONDITIONS:
        from builder.smoke_tool import identity
        config=plan['smoke'];index=Path(config['data_index'])
        if config['adapter']!=identity() or sha256(index.read_bytes())!=config['data_index_sha256']:
            raise ValueError('Prepared smoke environment changed')
        smoke_kwargs['smoke_data_index']=index
    elif 'smoke' in plan:
        raise ValueError('Undeclared smoke availability')
    if request_setup is not None:
        smoke_kwargs['request_setup'] = request_setup
    if request_budget is not None:
        smoke_kwargs['request_budget'] = request_budget
    expected = {case: sha256(condition_prompt((output/'inputs'/case/'prompt.txt').read_text(),
                plan['assistance'], request_budget=request_budget).encode()) for case in plan['cases']}
    if plan.get('condition') != CONDITIONS[plan['assistance']] or plan.get('authoring_prompt_sha256') != expected:
        raise ValueError('Prepared guided policy/prompt changed; prepare a new run')
    runs = output/'runs'; runs.mkdir(exist_ok=False)
    summary = dict(format='research-usability-result-v2', model=plan['model'], assistance=plan['assistance'],
                   plan='plan.json', transport='not_run', live_inference=responder is None, tasks=[])
    if plan['assistance'] in SMOKE_CONDITIONS:
        summary['authoring_smoke_enabled']=True
        summary['transport_scope']='Independent final transport; authoring smoke outcomes are recorded per task'
    for case in plan['cases']:
        folder = runs/case; folder.mkdir()
        result = agent.run(folder/'builder', case=case, prepared_input=output/'inputs'/case,
            model=plan['model'], assistance=plan['assistance'], contract=plan['delivery_contract'],
            execution_profile=plan['execution_profile']['id'], evaluator_protocol=plan['evaluator_protocol'], max_requests=declared['model_requests'],
            wall_seconds=declared['authoring_seconds'], mode='mock' if responder else 'subscription', responder=responder,**smoke_kwargs)
        row = dict(case=case, builder_status=result['status'], builder=f'runs/{case}/builder',
                   requests=result.get('request_count',0), attempted_boundary_calls=0,
                   export_status='not_run', diagnostic_score=None, final_assessment='not_run')
        usage = folder/'builder/boundary-tool/usage.json'
        if usage.exists():
            row['boundary_usage'] = json.loads(usage.read_bytes())
            row['attempted_boundary_calls'] = row['boundary_usage']['attempted_calls']
        usage=folder/'builder/smoke-tool/usage.json'
        if usage.exists():row['smoke_usage']=json.loads(usage.read_bytes())
        if result['status'] == 'completed':
            source, provenance = submission(folder/'builder', case)
            (folder/'candidate.py').write_bytes(source)
            exporter.write_json(folder/'provenance.json', provenance)
            row['candidate_sha256'] = sha256(source)
        row['authoring'] = trajectory(folder/'builder', result)
        row['authoring']['condition'] = CONDITIONS[plan['assistance']]
        row['authoring']['boundary_tool_available'] = plan['assistance'] in BOUNDARY_CONDITIONS
        row['authoring']['guided_workflow_required'] = plan['assistance'] in GUIDED_CONDITIONS
        if plan['assistance'] in SMOKE_CONDITIONS:row['authoring']['smoke_tool_available']=True
        row['delivery'] = dict(status='not_run', reason='Final validation belongs to independent assessment')
        row['overall_success'] = False
        row['overall_success_label'] = 'all implemented required checks passed within declared coverage'
        summary['tasks'].append(row)
        atomic_json(output/'summary.json', summary)
        if not result['cleanup_confirmed']:
            raise RuntimeError('Builder cleanup uncertain; later sessions not launched')
    return summary



def assess(output, *, index):
    """Explicit later operation: never called by the usability pilot's execute step."""
    from evaluation.candidates.run import evaluate
    from evaluation.candidates.verify import review_assessment
    output = Path(output)
    summary = json.loads((output/'summary.json').read_bytes())
    plan = json.loads((output/'plan.json').read_bytes())
    if (plan.get('format') != 'research-usability-pilot-v2' or plan['evaluator_protocol'] != BOUNDARY_PROTOCOL
            or plan['execution_profile'] != PROFILE or plan['delivery_contract'] != FACTORY
            or summary['assistance'] != plan['assistance']):
        raise ValueError('Assessment requires the prepared current contract/profile/protocol')
    if summary.get('assessment_requested'):
        raise ValueError('Assessment already requested; preserve its existing attempt')
    summary['assessment_requested'] = True
    atomic_json(output/'summary.json', summary)
    for row in summary['tasks']:
        if row['builder_status'] != 'completed':
            row['final_assessment'] = 'unavailable_submission'
            continue
        case = row['case']; folder = output/'runs'/case
        source, provenance = submission(folder/'builder', case)
        if source != (folder/'candidate.py').read_bytes():
            raise ValueError('Frozen submission differs from the retained builder answer')
        result = evaluate(case, folder/'assessment', index=Path(index), candidate=folder/'candidate.py', provenance=provenance,
            contract=plan['delivery_contract'], execution_profile=plan['execution_profile']['id'],
            evaluator_protocol=plan['evaluator_protocol'])
        review = review_assessment(folder/'assessment', Path(index))
        exporter.write_json(folder/'assessment/review.json', review)
        row.update(final_assessment=result['status'], assessment=f'runs/{case}/assessment',
                   evidence_status=review['evidence_status'], reported_score=result['diagnostic_score']['score'],
                   failure=result.get('stop'))
        row.update(assessment_summary(result, review))
        atomic_json(output/'summary.json', summary)
        if not result['cleanup_confirmed']:
            raise RuntimeError('Assessment cleanup uncertain; later tasks not started')
    atomic_json(output/'summary.json', summary)
    return summary


def assessment_summary(report, review):
    """Project existing verdicts; never grade authoring behavior or invent checks."""
    coherent = review['evidence_status'] == 'coherent'
    checks = report.get('checks', {}) if coherent else {}
    unresolved = [dict(check=category+'.'+name, cause='unassessed; see retained phase/requirement evidence')
                  for category, group in checks.items() for name, value in group.items() if value is None]
    violations = [dict(check=category+'.'+name, evidence='report.json#/checks/'+category+'/'+name)
                  for category in ('geometry','materials','physics_settings','engineering_consistency')
                  for name, value in checks.get(category, {}).items() if value is False]
    boundary = report.get('fidelity', {}).get('boundaries', {}) if coherent else {}
    for value in boundary.get('verdicts', []):
        if value['verdict'] == 'nonconforming':
            violations.append(value)
        elif value['verdict'] != 'conformity_established':
            unresolved.append(value)
    if boundary.get('unresolved_nonexternal_behavior'):
        unresolved.append(dict(check='nonexternal_boundary_behavior',
                               observations=boundary['unresolved_nonexternal_behavior']))
    if not coherent:
        unresolved.append(dict(check='evidence', cause=review.get('reason', review['evidence_status'])))
    stop = report.get('stop')
    if stop and stop.get('cause') != 'model':
        unresolved.append(dict(check=stop['stage'], cause=stop['cause'], detail=stop['detail']))
    assignment = report.get('assignment', {})
    export = report.get('phases', {}).get('export', {})
    return dict(evidence_status=review['evidence_status'],
        delivery=dict(status=export.get('status', 'not_run') if coherent else 'unverified',
                      reason=stop if stop and stop['stage'] in ('admission','export','eligibility','preflight') else None,
                      evidence='report.json#/phases/export'),
        export_status=export.get('status','not_run') if coherent else 'unverified',
        final_model=report.get('final_model') if coherent else None,
        hard_gates=report.get('gates') if coherent else None,
        material_input_findings=report.get('material_input_findings', []) if coherent else [],
        demonstrated_physical_violations=violations, unresolved_requirements=unresolved,
        coverage=dict(boundary=assignment.get('scientific_boundary'),
                      support_limit=stop if stop and stop.get('cause') == 'capability' else None,
                      geometry='Finite task probes and qualified boundary scope; no universal geometry claim',
                      details='export-fidelity.json and export-boundaries/stdout.json'),
        numerical=dict(comparison=report.get('comparison'), candidate_keff=report.get('candidate_keff'),
                       reference_keff=assignment.get('reference', {}).get('primary_mean')) if coherent else None,
        overall_success=bool(coherent and report['status']=='assessed' and review.get('strict_correct') is True),
        overall_success_label='all implemented required checks passed within declared coverage',
        diagnostic_score=review.get('score') if coherent else None,
        grading_enabled=False,
        identities=dict(protocol=assignment.get('assessment_route'), rubric=assignment.get('rubric'),
                        reference=assignment.get('reference'), frozen_index_sha256=assignment.get('frozen_index_sha256')),
        assessment_effort=dict(elapsed_seconds=report.get('elapsed_seconds'),
                               phases={n:dict(status=v.get('status'),elapsed_seconds=v.get('elapsed_seconds'))
                                       for n,v in report.get('phases', {}).items()}))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--assistance', choices=tuple(CONDITIONS), required=True)
    p.add_argument('--model', default='gpt-5.6-luna')
    p.add_argument('--cases', nargs='+', choices=sorted(CASE_FILES), default=['reflective_pin_cell','moderated_cylinder'])
    p.add_argument('--smoke-data-index',type=Path)
    p.add_argument('--request-budget',choices=(EXTENDED_REQUEST_BUDGET,))
    p = sub.add_parser('execute')
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('assess', help='Separate independent evaluation; may run native transport')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--data-index', dest='index', type=Path, required=True)
    args = vars(parser.parse_args()); action = args.pop('action')
    if action == 'prepare':
        result = prepare(**args)
    elif action == 'execute':
        result = execute(**args)
    else:
        result = assess(**args)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
