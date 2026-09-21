"""Score eligibility adapter, separate from physical extraction and comparison."""
from evaluation.scientific import boundaries


def evaluate(observation, specification, legacy_observation):
    result=boundaries.compare(observation,specification)
    states=[v['verdict'] for v in result['verdicts']]
    # Preserve the previous task's restriction on nonexternal nontransmission
    # boundaries without pretending this limited observer qualifies their role.
    covered={int(r.split(':')[1]) for face in observation['faces'] for r in face['surface_refs']}
    inactive=set(observation['coverage'].get('proven_inactive_root_surface_ids',[]))
    uncovered=[s for s in legacy_observation['nontransmission_surfaces'] if s['id'] not in covered|inactive]
    unresolved=not states or any(s not in ('conformity_established','nonconforming') for s in states) or bool(uncovered)
    result['unresolved_nonexternal_behavior']=uncovered
    result['score_check']=None if unresolved else all(s=='conformity_established' for s in states)
    result['score_eligibility']='indeterminate' if unresolved else 'eligible'
    result['status']='discrepancy' if 'nonconforming' in states else 'inconclusive' if unresolved else 'passed_checks'
    result['experimental_treatment']=('unscored capability limit; retain each demonstrated mismatch'
        if unresolved else 'apply unchanged geometry boundary check weight')
    return result
