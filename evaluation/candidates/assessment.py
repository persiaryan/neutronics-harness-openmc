"""Map independently checked evidence onto the frozen named scoring checks."""
import math

from evaluation.benchmark_suite import scoring
from evaluation.benchmark_suite.numerics import compare
from evaluation.benchmark_suite.suite_cases import SPECS, probes, expected, check_materials


def blank_gates():
    return {name: dict(passed=None, cause='evaluator', detail='not reached')
            for name in scoring.RUBRIC['hard_gates']}


def blank_checks():
    return {name: {key: None for key in category['checks']}
            for name, category in scoring.RUBRIC['categories'].items()}


def inspection_failure(observation):
    """Attribute only verified observations, without treating exceptions as defects.

    openmc_runs includes native input eligibility: a demonstrated fatal input
    precondition prevents a run, even though factory export succeeded. No native
    execution is claimed and the existing hard-failure score policy is unchanged.
    """
    if observation['status'] == 'inspected':
        return None
    if observation['status'] == 'invalid_model':
        return dict(cause='model', hard_gate='openmc_runs',
                    detail='Native input precondition failed: material requires nuclides or macroscopic data; transport not attempted')
    return dict(cause='evaluator', hard_gate=None,
                detail='Inspection incomplete or unsupported; no established candidate-failure attribution')


def all_known(values):
    values = list(values)
    if not values or any(value is None for value in values):
        return None
    return all(values)


def field_checks(items, names):
    """Absent assertions are unassessed, never vacuous passes."""
    return all_known(all_known(c['passed'] for c in items if c['field'] == name) for name in names)


def fidelity_checks(case, fidelity, observation=None):
    result = blank_checks()
    s = fidelity['settings']
    if not s['unassessed_options']:
        result['physics_settings'] = dict(
            physics=field_checks(s['checks'], ['run_mode', 'energy_mode', 'temperature_method',
                                              'temperature_tolerance', 'temperature_multipole']),
            sampling=field_checks(s['checks'], ['particles', 'batches', 'inactive', 'generations_per_batch', 'seed']),
            source=field_checks(s['checks'], ['source_count', 'source_type', 'source_particle', 'source_space',
                                            'source_parameters', 'source_fissionable', 'source_rejection',
                                            'source_angle', 'source_energy', 'source_watt']),
            entropy_mesh_and_output=field_checks(s['checks'], ['entropy_mesh_count', 'entropy_mesh_type',
                                                             'entropy_dimensions', 'entropy_lower_left',
                                                             'entropy_upper_right', 'final_statepoint']))
        # A missing/multiple source or mesh is a demonstrated defect, not missing evidence.
        for count, name in [('source_count', 'source'), ('entropy_mesh_count', 'entropy_mesh_and_output')]:
            if field_checks(s['checks'], [count]) is False:
                result['physics_settings'][name] = False
    if 'geometry' not in fidelity:
        return result
    groups = fidelity['geometry']['groups']
    group_ok = lambda names: all_known(groups[n]['failures'] == 0 if n in groups else None for n in names)
    result['geometry'] = dict(interfaces=group_ok(['interfaces']),
                             extent_and_map=group_ok(['axial_ends', 'material_map']),
                             domain=group_ok(['domain_samples'] + ([] if SPECS[case]['shape'] == 'cylinder' else ['outer_faces'])),
                             boundaries=None if fidelity['boundaries']['status'] == 'inconclusive'
                             else fidelity['boundaries']['status'] == 'passed_checks')
    if 'active_samples' in groups:
        result['geometry']['domain'] = all_known([result['geometry']['domain'], group_ok(['active_samples'])])
    if 'score_check' in fidelity['boundaries']:
        result['geometry']['boundaries'] = fidelity['boundaries']['score_check']
    # Cylinder radial/axial assertions share the registered interface probe set.
    if SPECS[case]['shape'] == 'cylinder':
        result['geometry']['interfaces'] = None
        result['geometry']['extent_and_map'] = None
        if observation is not None:
            roles, _ = check_materials(case, observation['materials'])
            radial, axial = [], []
            points, labels = probes(case)
            for p, label, (state, leaves) in zip(points, labels, observation['observations']):
                if label != 'interfaces':
                    continue
                actual = ('outside' if state == 'outside' else
                          ('void' if leaves[0][0] is None else roles.get(str(leaves[0][0]), 'unknown'))
                          if state == 'ok' and len(leaves) == 1 else state)
                match = actual == expected(case, p)
                if abs(p[2]) < 25:
                    radial.append(match)
                if math.hypot(p[0], p[1]) < 12:
                    axial.append(match)
            result['geometry']['interfaces'] = all_known(radial)
            result['geometry']['extent_and_map'] = all_known(axial)
    m = fidelity['materials']
    result['materials'] = dict(composition=field_checks(m['checks'], ['composition', 'required_material_roles', 'forced_isotropic']),
                              density=field_checks(m['checks'], ['density']),
                              thermal_scattering=field_checks(m['checks'], ['thermal_scattering']),
                              temperature=m['temperature_failures'] == 0)
    if field_checks(m['checks'], ['composition', 'required_material_roles']) is False:
        result['materials']['composition'] = False
        # Unknown roles have no trusted target density or S(a,b) assignment.
        result['materials']['density'] = None
        result['materials']['thermal_scattering'] = None
    return result


def complete_checks(checks, record, reference, leakage):
    numerical = compare(record['keff'], reference, scoring.RUBRIC['equivalence_margin_pcm'],
                        scoring.RUBRIC['interval_multiplier'])
    checks['keff']['equivalence_demonstrated'] = numerical['status'] == 'agreement'
    drift = record['convergence']['statistics'].get('entropy_bits', {}).get('second_minus_first')
    checks['statistical_quality'] = dict(precision=record['keff']['std_dev'] * 1e5 <= scoring.RUBRIC['maximum_candidate_std_dev_pcm'],
                                        entropy_screen=abs(drift) <= scoring.RUBRIC['entropy_active_half_drift_screen_bits']
                                        if drift is not None and math.isfinite(drift) else False)
    checks['engineering_consistency'] = leakage
    return numerical
