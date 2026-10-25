"""Compare accepted source support using pinned resampling semantics.

An exhaustive flat-cell identity is a sufficient positive proof. Interior
witnesses only refute equivalence; their absence never establishes it.
Material fissionability is supplied by the comparator's qualified material
catalog, not inferred here from names or numerical IDs.
"""
from evaluation.scientific import inspection, source_space
from evaluation.scientific.records import require

VERSION='accepted-source-support-comparison-v1'


def observe(xml, points, output, *, image=inspection.IMAGE, wall_seconds=120):
    return inspection.inspect_xml(xml, points, output, image=image, wall_seconds=wall_seconds,
                                  capability='source-domains-v1')


def record(directory, xml, points, *, image=inspection.IMAGE):
    return inspection.completed_record(directory, xml, points, image=image, capability='source-domains-v1')


def compare(root, observation, material_fissionability):
    result=dict(field='source_accepted_support', comparison_version=VERSION, expected='uniform_proposal_conditioned_on_fissionable_material',
                passed=None, cause=None, proof=None, witnesses=[], limitations=[])
    def unknown(cause):
        result['cause']=cause
        return result
    sources=root.findall('settings/source')
    if len(sources)!=1:
        return unknown('requires_one_source')
    source=sources[0]
    constraints=source.findall('constraints')
    if len(constraints)>1:
        return unknown('duplicate_constraints')
    node=constraints[0] if constraints else None
    fields={} if node is None else {c.tag:c for c in node}
    if node is not None and (node.attrib or len(fields)!=len(node) or
                             any(c.attrib or len(c) or not (c.text or '').strip() for c in node)):
        return unknown('unsupported_constraint_structure')
    text=lambda name,default: fields[name].text.strip() if name in fields and fields[name].text else default
    unsupported=sorted(set(fields)-{'fissionable','rejection_strategy','domain_type','domain_ids'})
    result['limitations']=['unsupported_constraint:'+name for name in unsupported]
    value=text('fissionable','false')
    if value not in ('true','false','1','0'):
        return unknown('unsupported_fissionable_value')
    spaces=source.findall('space')
    if len(spaces)!=1:
        return unknown('requires_one_spatial_description')
    spatial=source_space.observe(spaces[0])
    if spatial['limitations']:
        return unknown('unsupported_proposal_distribution')
    flag=value in ('true','1') or spaces[0].get('type')=='fission'
    if text('rejection_strategy','resample')!='resample':
        # The separate literal rejection-strategy check records the mismatch.
        return unknown('unsupported_rejection_strategy')
    has_domain=bool({'domain_type','domain_ids'} & fields.keys())
    if not has_domain and flag:
        if unsupported:
            return unknown('additional_constraints_may_change_support')
        result.update(passed=True, proof='native_fissionable_resampling_without_domain_restriction')
        return result
    if observation.get('limitations'):
        return unknown(observation['limitations'][0])
    require(observation.get('observer_version')=='source-domain-observation-v1', 'Unknown source-domain observations')
    cells=observation['cells']
    if not cells or len({c['id'] for c in cells})!=len(cells):
        return unknown('missing_or_duplicate_flat_cells')
    labels={c['id']:False if c['material_id'] is None else material_fissionability.get(c['material_id']) for c in cells}
    if any(v is None for v in labels.values()):
        return unknown('material_fissionability_not_qualified')
    fissile={cid for cid,value in labels.items() if value}
    if not fissile:
        return unknown('no_qualified_fissionable_cell')
    selected=set(labels)
    if has_domain:
        kind=text('domain_type',None)
        if kind not in ('cell','material') or 'domain_ids' not in fields:
            return unknown('unsupported_or_incomplete_domain_constraint')
        try:
            ids=[int(v) for v in text('domain_ids','').split()]
        except ValueError:
            return unknown('malformed_domain_ids')
        if not ids or len(set(ids))!=len(ids) or any(i<=0 for i in ids):
            return unknown('empty_duplicate_or_invalid_domain_ids')
        known={c['id'] if kind=='cell' else c['material_id'] for c in cells}
        if not set(ids)<=known:
            return unknown('domain_id_not_in_flat_inventory')
        selected={c['id'] for c in cells if (c['id'] if kind=='cell' else c['material_id']) in ids}
    accepted=selected & fissile if flag else selected
    result['actual']=dict(fissionable_filter=flag, selected_cells=sorted(selected),
                          accepted_cells=sorted(accepted), fissionable_cells=sorted(fissile))
    if accepted==fissile and not unsupported:
        result.update(passed=True, proof='identical_accepted_and_fissionable_flat_cell_sets')
        return result
    for witness in observation['witnesses']:
        p=witness['point']; cid=witness['cell_id']
        if cid not in labels or not all(spatial['axes'][a]['bounds'][0]<p[i]<spatial['axes'][a]['bounds'][1] for i,a in enumerate('xyz')):
            continue
        # An unknown extra restriction can remove accepted sites. It cannot
        # rescue a site already rejected by the known domain restriction.
        omitted=cid in fissile and cid not in accepted
        extra=cid in accepted and cid not in fissile and not unsupported
        if omitted or extra:
            result['witnesses'].append(dict(witness, expected_acceptance=cid in fissile, known_acceptance=cid in accepted))
    if result['witnesses']:
        result.update(passed=False, cause='accepted_support_mismatch', proof='strict_interior_counterexample')
        result['witnesses']=result['witnesses'][:20]
        return result
    return unknown('additional_constraints_may_change_support' if unsupported else 'cell_set_difference_not_resolved_inside_proposal')
