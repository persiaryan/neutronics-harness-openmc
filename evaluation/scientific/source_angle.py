"""Bounded angular observations from pinned OpenMC source XML; no task values.

Like source_space, this is an admitted-XML projection qualified against the
pinned API, not a replacement for fresh OpenMC loading or a general parser.
"""
import math

from evaluation.scientific.records import close
from evaluation.scientific.source_space import finite_numbers

VERSION = 'isotropic-source-comparison-v1'


def observe(angle):
    result = dict(encoding='default' if angle is None else angle.get('type'),
                  marginals={}, frame=None, limitations=[])
    limits = result['limitations']
    kind = result['encoding']
    if angle is None:
        result['law'] = 'isotropic'
        return result
    if kind == 'isotropic':
        result['law'] = 'isotropic'
        if set(angle.attrib) != {'type'} or len(angle):
            limits.append('unsupported_isotropic_structure')
        return result
    if kind == 'monodirectional':
        result['law'] = 'single_direction'
        return result
    result['law'] = None
    if kind != 'mu-phi':
        limits.append('unsupported_angular_distribution')
        return result
    result['law'] = 'independent_mu_phi'
    if set(angle.attrib) - {'type', 'reference_uvw', 'reference_vwu'}:
        limits.append('unsupported_angular_attributes')
    if any(n.tag not in ('mu', 'phi') for n in angle):
        limits.append('unsupported_angular_structure')
    vectors = [finite_numbers(angle.get(n, default), 3) for n, default in
               (('reference_uvw', '0 0 1'), ('reference_vwu', '1 0 0'))]
    if any(v is None for v in vectors):
        limits.append('unresolved_reference_frame')
    else:
        lengths = [math.hypot(*v) for v in vectors]
        valid = all(close(n, 1.) for n in lengths) and close(sum(a*b for a,b in zip(*vectors)), 0.)
        result['frame'] = dict(reference_uvw=vectors[0], reference_vwu=vectors[1],
                               supported_orthonormal=valid)
        if not valid:
            limits.append('reference_frame_outside_orthonormal_scope')
    for name in ('mu', 'phi'):
        nodes = angle.findall(name)
        if len(nodes) != 1:
            limits.append(name+':missing_or_duplicate_marginal')
            continue
        node = nodes[0]; kind = node.get('type')
        if kind == 'uniform':
            if set(node.attrib) != {'type', 'parameters'} or len(node):
                limits.append(name+':unsupported_marginal_structure')
                continue
            bounds = finite_numbers(node.get('parameters'), 2)
            if bounds is None:
                limits.append(name+':invalid_uniform_parameters')
            else:
                result['marginals'][name] = dict(law='uniform', bounds=bounds)
        elif kind == 'discrete':
            parameters = node.findall('parameters')
            if (set(node.attrib) != {'type'} or len(node) != 1 or len(parameters) != 1
                    or parameters[0].attrib or len(parameters[0])):
                limits.append(name+':unsupported_discrete_structure')
                continue
            text = (parameters[0].text or '').split()
            values = finite_numbers(' '.join(text), len(text))
            if (values and len(values) % 2 == 0 and
                    all(p >= 0 for p in values[len(values)//2:]) and sum(values[len(values)//2:]) > 0):
                result['marginals'][name] = dict(law='finite_atomic')
            else:
                limits.append(name+':invalid_discrete_parameters')
        else:
            limits.append(name+':unsupported_marginal_distribution')
    return result


def compare(observation):
    """Requirement: isotropic solid-angle density. Unknowns do not erase failures."""
    limits = observation['limitations']
    checks = []
    def check(component, actual, expected, passed, cause=None):
        checks.append(dict(field='source_angle', component=component, actual=actual,
                           expected=expected, passed=passed, cause=cause))
    law = observation.get('law')
    check('description', law, 'supported_complete_description', None if limits else True,
          list(limits) if limits else None)
    if law in ('isotropic', 'single_direction'):
        check('solid_angle', law, 'isotropic', law == 'isotropic')
    elif law == 'independent_mu_phi':
        for name in ('mu', 'phi'):
            item = observation['marginals'].get(name)
            expected = [-1., 1.] if name == 'mu' else dict(uniform_period=2*math.pi)
            verdict = None; cause = 'unresolved_marginal'
            if item is not None:
                if item['law'] == 'finite_atomic':
                    verdict = False; cause = 'finite_atomic_not_continuous_uniform'
                elif name == 'mu':
                    verdict = all(close(a,b) for a,b in zip(item['bounds'], [-1.,1.]))
                    cause = None if verdict else 'incorrect_uniform_mu_bounds'
                else:
                    span = item['bounds'][1] - item['bounds'][0]
                    if close(span, 2*math.pi):
                        verdict = True; cause = None
                    elif span < 2*math.pi:
                        verdict = False; cause = 'incomplete_or_invalid_azimuthal_coverage'
                    else:
                        cause = 'azimuthal_multiple_turns_outside_scope'
            check(name, item, expected, verdict, cause)
    return checks
