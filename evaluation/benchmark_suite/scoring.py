"""Calculate the frozen diagnostic score from private, independently checked evidence.

This is not a candidate-evaluation pipeline. Never accept builder self-ratings.
"""
import json
import hashlib
from copy import deepcopy
from pathlib import Path
from evaluation.scientific.records import require

RUBRIC_PATH = Path(__file__).with_name('scoring.json')
RUBRIC = json.loads(RUBRIC_PATH.read_bytes())


def identity():
    return dict(format=RUBRIC['format'], sha256=hashlib.sha256(RUBRIC_PATH.read_bytes()).hexdigest(),
                applicable_points=70)


def verify_reference_criteria(frozen):
    """The sole authorized migration: remove traceability points, preserve physics."""
    expected = deepcopy(frozen)
    require(expected['format'] == 'private-weighted-keff-rubric-v1', 'Unexpected frozen rubric')
    require(expected['categories'].pop('reproducibility_traceability') ==
            dict(weight=5, checks=['complete_verified_chain', 'repeat_export_consistent']),
            'Unexpected historical category')
    expected.update(format='private-weighted-keff-rubric-v2', applicable_points=70,
                    normalization='100 * earned_points / 70; no points for N/A categories')
    require(expected == RUBRIC, 'V2 rubric changes criteria outside the authorized migration')



def score(gates, checks):
    """Gate records use passed=True/False/None and cause=model/infrastructure/evaluator.

    Check values are True/False/None, with exact category and check inventories.
    Missing evidence is unscored; model-caused hard failures are always zero.
    """
    require(set(gates)==set(RUBRIC['hard_gates']), 'Incomplete hard-gate inventory')
    for gate in gates.values():
        require(type(gate.get('passed')) is bool or gate.get('passed') is None, 'Invalid gate status')
        require(gate.get('cause') in ('model','infrastructure','evaluator',None), 'Invalid gate cause')
        require(gate['passed'] is True or gate.get('cause') is not None, 'Unresolved failure attribution')
    base={'format':'weighted-keff-score-v2','applicable_points':70,'not_applicable':RUBRIC['not_applicable'],
          'grading_enabled':False,'strict_correct':False}
    if any(g['passed'] is False and g['cause']=='model' for g in gates.values()):
        return dict(base,status='model_gate_failure',score=0.,earned_points=0.)
    if any(g['passed'] is not True for g in gates.values()):
        return dict(base,status='unscored',score=None,reason='Incomplete or failed infrastructure/evaluator gate')
    require(set(checks)==set(RUBRIC['categories']), 'Incomplete category inventory')
    categories={}
    for name,definition in RUBRIC['categories'].items():
        values=checks[name]
        require(set(values)==set(definition['checks']), 'Incomplete checks: '+name)
        require(all(type(v) is bool or v is None for v in values.values()), 'Checks must be boolean or unassessed')
        if any(v is None for v in values.values()):
            return dict(base,status='unscored',score=None,reason='Unassessed evidence: '+name)
        fraction=sum(values.values())/len(values)
        categories[name]={'fraction':fraction,'earned_points':fraction*definition['weight'],'checks':values}
    earned=sum(v['earned_points'] for v in categories.values())
    return dict(base,status='scored',score=100*earned/70,earned_points=earned,categories=categories,
                strict_correct=all(v['fraction']==1 for v in categories.values()))
