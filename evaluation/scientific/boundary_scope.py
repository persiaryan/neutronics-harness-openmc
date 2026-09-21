"""Explicit coverage inventory; this is neither observation nor task scoring."""
from evaluation.scientific import boundaries
from prompts.prepare import CASE_FILES

SCOPE = 'uniform-root-box-boundaries-v2'
LIMITATIONS = [
    'Only a root union established as one axis-aligned open box is supported.',
    'Face behavior must be uniform across all possible contributors for that property.',
    'Mixed face patches and conflicting coincident declarations are indeterminate; their location is not resolved.',
    'Possible contributors are a conservative superset, not proof that each cell or surface touches the face.',
    'Interior interfaces, curved exterior, filled face hierarchy, periodic coupling, edges and corners are not qualified.',
    'No global overlap, gap, material or geometry-validity claim is made.',
]


def task_matrix():
    rows=[]
    for case in CASE_FILES:
        if case == 'moderated_cylinder':
            rows.append(dict(case=case,status='unsupported',requirement_count=None,
                required_subjects=['radius-20 cylindrical wall vacuum','z=-33 end disk vacuum','z=33 end disk vacuum'],
                cause='curved_root_domain_not_supported',verdict='indeterminate',score_eligible=False,
                execution='factory-assessment-boundaries-v3 refuses this task before execution; no legacy fallback'))
        else:
            spec=boundaries.requirements(case)
            rows.append(dict(case=case,status='supported_representation_required',
                requirement_count=len(spec['requirements']),requirements=[r['id'] for r in spec['requirements']],
                source=spec['source'],verdict='requires_candidate_observation',score_eligible=None,
                execution='indeterminate required observations leave the diagnostic score unscored'))
        rows[-1]['interior_interfaces']='not qualified by this boundary capability; separate existing inventory guard only'
    return dict(format=SCOPE,observer=boundaries.VERSION,comparator=boundaries.COMPARISON,
                tasks=rows,limitations=LIMITATIONS,
                denominator=dict(all_tasks=len(rows),supported_task_families=sum(r['status']!='unsupported' for r in rows)))
