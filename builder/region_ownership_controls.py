"""Small OpenMC 0.15.3 region controls; no candidate, reference, data, or transport."""
import json


def qualify(openmc):
    if openmc.__version__ != '0.15.3':
        raise ValueError('Region controls require OpenMC 0.15.3')
    observations = {}

    def check(name, value):
        observations[name] = bool(value)
        if not value:
            raise AssertionError('Region control failed: ' + name)

    left = openmc.XPlane(x0=-1.)
    right = openmc.XPlane(x0=1.)
    middle = openmc.XPlane(x0=0.)
    lower = openmc.XPlane(x0=-2.)
    upper = openmc.XPlane(x0=2.)
    domain = +lower & -upper
    negative = (-0.5, 0., 0.)
    positive = (0.5, 0., 0.)
    outside = (-1.5, 0., 0.)

    # The literal slab -1 < x < 1 must contain both interior points initially.
    base = +left & -right
    cell = openmc.Cell(region=base)
    check('initial_slab_membership', negative in base and positive in base and outside not in base)
    derived = base
    derived &= +middle
    check('intersection_alias_mutates_base', derived is base and negative not in base)
    check('assigned_cell_observes_mutation', cell.region is base and negative not in cell.region)
    check('mutated_complement_includes_original_interior', negative in (domain & ~base))

    base = +left & -right
    derived = base
    derived = derived & +middle
    check('new_intersection_preserves_base', derived is not base and negative in base and positive in base)
    check('derived_intersection_has_requested_membership', negative not in derived and positive in derived)
    check('preserved_complement_excludes_interior', negative not in (domain & ~base) and outside in (domain & ~base))

    # Intentional in-place construction of an unshared accumulator is valid.
    owned = +left & -right
    owned &= +middle
    check('unshared_inplace_can_be_intentional', negative not in owned and positive in owned)

    base = -left | +right
    derived = base
    derived |= +middle
    check('union_alias_mutates_base', derived is base and positive in base)
    base = -left | +right
    derived = base | +middle
    check('new_union_preserves_base', positive not in base and positive in derived)

    # A new outer expression does not detach a nested mutable child.
    child = +left & -right
    outer = child | +upper
    check('nested_child_initial_membership', negative in outer)
    child &= +middle
    check('new_expression_still_shares_children', negative not in outer)

    return dict(format='openmc-region-ownership-controls-v1',
                openmc=openmc.__version__, checks=observations,
                neutron_transport='not_run', nuclear_data='not_used',
                skill_efficacy='not_tested')


if __name__ == '__main__':
    import openmc
    print(json.dumps(qualify(openmc), sort_keys=True))
