"""Prospective fidelity and conformance; the weighted rubric stays unchanged."""
from evaluation.benchmark_suite import suite_checks
from evaluation.benchmark_suite.suite_cases import SPECS, check_materials
from evaluation.candidates import assessment
from evaluation.scientific import source_domains

VERSION='representation-fidelity-v1'


def identity():
    """Bind prospective semantics separately from the unchanged weighted rubric."""
    from pathlib import Path
    from evaluator.run import digest
    root=Path(__file__).resolve().parents[2]
    paths=('evaluation/candidates/representation.py','evaluation/scientific/source_domains.py',
           'evaluation/scientific/source_domains_worker_v1.py','evaluation/scientific/boundary_worker_v3.py')
    return dict(format=VERSION, files={p:digest((root/p).read_bytes()) for p in paths})


def assess(case, root, observation, sampling, *, boundary_result, source_observation):
    result=suite_checks.assess(case,root,observation,sampling,boundary_result=boundary_result)
    roles,_=check_materials(case,observation['materials'])
    # These roles match explicit benchmark recipes. Unknown compositions never
    # inherit fissionability from a material name or a submitted numeric ID.
    classified={int(mid):True if role in {'fuel','fuel_A','fuel_B','mixture','uranium_metal'} else
                False if role in {'water','zirconium'} else None for mid,role in roles.items()}
    support=source_domains.compare(root,source_observation,classified)
    settings=result['settings']
    settings['checks']=[c for c in settings['checks'] if c['field']!='source_fissionable']+[support]
    settings['unassessed_options']=[n for n in settings['unassessed_options'] if n not in
                                   ('constraints/domain_type','constraints/domain_ids')]
    settings['status']=('discrepancy' if any(c['passed'] is False for c in settings['checks']) else
        'inconclusive' if settings['unassessed_options'] or any(c['passed'] is None for c in settings['checks']) else 'passed_checks')
    settings['source_support']=support
    states={result[k]['status'] for k in ('materials','geometry','boundaries','settings')}
    result['status']='discrepancy' if 'discrepancy' in states else 'inconclusive' if 'inconclusive' in states else 'passed_checks'
    result['fidelity_version']=VERSION
    return result


def fidelity_checks(case, fidelity, observation=None):
    result=assessment.fidelity_checks(case,fidelity,observation)
    fields=assessment.field_checks; s=fidelity['settings']
    names=dict(
        physics=['run_mode','energy_mode','temperature_method','temperature_tolerance','temperature_multipole']+
                (['temperature_default'] if SPECS[case]['shape']=='confirmation' else []),
        sampling=['particles','batches','inactive','generations_per_batch','seed'],
        source=['source_count','source_type','source_particle','source_space','source_parameters',
                'source_accepted_support','source_rejection','source_angle','source_energy','source_watt'],
        entropy_mesh_and_output=['entropy_mesh_count','entropy_mesh_type','entropy_dimensions',
                                 'entropy_lower_left','entropy_upper_right','final_statepoint'])
    result['physics_settings']={group:fields(s['checks'],required) for group,required in names.items()}
    for option in s['unassessed_options']:
        affected=['source'] if option.startswith(('source/','constraints/')) else list(names)
        for group in affected: result['physics_settings'][group]=None
    for count,group in [('source_count','source'),('entropy_mesh_count','entropy_mesh_and_output')]:
        if fields(s['checks'],[count]) is False: result['physics_settings'][group]=False
    return result


def conclusion(gates, checks, fidelity, score, *, evidence_available=True):
    """A refuted requirement survives incomplete scoring, not invalid evidence.

    'conforming_within_protocol' is explicitly limited to the measured protocol,
    including its finite geometry coverage; it is not global physical validity.
    """
    mismatch=[]; unknown=[]
    for name,gate in gates.items():
        if gate['passed'] is False and gate['cause']=='model': mismatch.append('gates.'+name)
        elif gate['passed'] is not True: unknown.append('gates.'+name)
    for category,values in checks.items():
        for name,value in values.items():
            if value is False: mismatch.append(category+'.'+name)
            elif value is None: unknown.append(category+'.'+name)
    for category in ('settings','materials'):
        for check in fidelity.get(category,{}).get('checks',[]):
            if check['passed'] is False: mismatch.append(category+'.'+check['field'])
    for row in fidelity.get('boundaries',{}).get('verdicts',[]):
        if row['verdict']=='nonconforming': mismatch.append('boundaries.'+row['requirement_id'])
    status=('indeterminate' if not evidence_available else 'nonconforming' if mismatch else
            'indeterminate' if unknown else 'conforming_within_protocol')
    return dict(format='conformance-and-coverage-v1', conformance=status,
                evidence_available=evidence_available, evaluation_complete=evidence_available and not unknown,
                score_complete=evidence_available and score.get('score') is not None,
                known_mismatches=sorted(set(mismatch)) if evidence_available else [],
                unassessed_checks=sorted(set(unknown)), global_geometry_validity='not_established')
