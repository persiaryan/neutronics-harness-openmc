"""Bounded semantic projection of two pinned OpenMC spatial-source encodings.

This reads admitted XML, not Python or a private reference. It is not a general
distribution parser: unrecognized structure remains explicitly unassessed.
Qualification binds these encodings to OpenMC 0.15.3 construction/loading.
"""
import math

from evaluation.scientific.records import close

VERSION = 'uniform-box-source-comparison-v1'


def finite_numbers(text, count):
    try:
        values = [float(v) for v in text.split()]
    except (AttributeError, ValueError):
        return None
    return values if len(values) == count and all(math.isfinite(v) for v in values) else None


def observe(space):
    """Extract independent Uniform intervals only; no expected values or verdicts."""
    result = dict(encoding=None if space is None else space.get('type'),
                  independent=None, axes={}, limitations=[])
    def limited(cause):
        result['limitations'].append(cause)
    if space is None:
        limited('missing_spatial_description')
        return result
    kind = space.get('type')
    if kind not in ('box', 'fission', 'cartesian'):
        limited('unsupported_spatial_distribution')
        return result
    if set(space.attrib) != {'type'}:
        limited('unsupported_spatial_attributes')
    if kind in ('box', 'fission'):
        nodes = space.findall('parameters')
        if len(space) != 1 or len(nodes) != 1 or nodes[0].attrib or len(nodes[0]):
            limited('incomplete_or_unsupported_box_description')
            return result
        values = finite_numbers(nodes[0].text, 6)
        if values is None:
            limited('invalid_box_parameters')
            return result
        result['independent'] = True
        result['axes'] = {axis: dict(distribution='uniform', bounds=[values[i], values[i+3]])
                          for i, axis in enumerate('xyz')}
    else:
        result['independent'] = True  # Pinned cartesian means independent marginals.
        if any(n.tag not in ('x', 'y', 'z') for n in space):
            limited('unsupported_cartesian_structure')
        for axis in 'xyz':
            nodes = space.findall(axis)
            if len(nodes) != 1:
                limited(axis+':missing_or_duplicate_axis')
                continue
            node = nodes[0]
            if node.get('type') != 'uniform':
                limited(axis+':unsupported_axis_distribution')
                continue
            if set(node.attrib) != {'type', 'parameters'} or len(node):
                limited(axis+':unsupported_uniform_structure')
                continue
            values = finite_numbers(node.get('parameters'), 2)
            if values is None:
                limited(axis+':invalid_uniform_parameters')
                continue
            result['axes'][axis] = dict(distribution='uniform', bounds=values)
    for axis, item in result['axes'].items():
        if item['bounds'][0] >= item['bounds'][1]:
            limited(axis+':nonpositive_interval')
    return result


def compare(observation, bounds):
    """Compare to public bounds; retain a mismatch beside an unresolved axis.

    Repeated source_parameters records are per-axis assertions in the existing
    source check. Unknowns remain None and never earn score credit.
    """
    limitations = observation['limitations']
    checks = [dict(field='source_space', actual='uniform_cartesian_box' if not limitations else None,
                   expected='uniform_cartesian_box', passed=True if not limitations else None,
                   cause=None if not limitations else limitations)]
    for i, axis in enumerate('xyz'):
        item = observation['axes'].get(axis)
        actual = None if item is None else item['bounds']
        target = [bounds[i], bounds[i+3]]
        checks.append(dict(field='source_parameters', axis=axis, actual=actual, expected=target,
                           passed=None if actual is None else all(close(a,b) for a,b in zip(actual,target)),
                           cause='unresolved_axis_bounds' if actual is None else None))
    return checks
