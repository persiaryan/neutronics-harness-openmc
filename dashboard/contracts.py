"""Explicit report readers. Raw reports remain available, unsupported formats never pass."""
from copy import deepcopy
import json
import math
from pathlib import Path

from observation_contracts import fingerprint, validate_evaluation_definition, describe_configuration

LEGACY = Path(__file__).parent/'legacy/evaluation-v5.json'


def obj(value):
    return value if isinstance(value,dict) else {}


def configuration_view(plan):
    try:
        value=describe_configuration(obj(plan), historical=True)
        return dict(status='supported' if value else 'unsupported',definition=value,reason=None if value else 'Unknown configuration identity')
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        return dict(status='invalid',definition=None,reason=str(exc))


def legacy_definition():
    # This immutable migration definition deliberately does not read the live rubric.
    return validate_evaluation_definition(json.loads(LEGACY.read_text()))


def assessment_state(report):
    """Read execution status without interpreting scores or inventing a rubric."""
    if report is None:
        return dict(state='pending')
    if not isinstance(report,dict) or report.get('format') not in (
            'private-candidate-diagnostic-v5','evaluation-report-v1'):
        return dict(state='unavailable')
    status=report.get('status')
    state='interrupted' if status in ('incomplete','stopped') else 'completed' if status=='assessed' else 'unavailable'
    stop=obj(report.get('stop'))
    result=dict(state=state, reported_status=status)
    for name in ('stage','cause','detail'):
        if isinstance(stop.get(name),str): result[name]=stop[name]
    if isinstance(report.get('error'),str): result['error']=report['error']
    # This v5 admission error precedes assignment and any scientific execution.
    if (report.get('format')=='private-candidate-diagnostic-v5' and state=='interrupted'
            and stop.get('stage')=='admission' and stop.get('cause')=='evaluator'
            and not report.get('assignment') and report.get('phases')=={}
            and report.get('error')=='Package root must be a real directory'):
        result['reason']='reference_unavailable'
    return result


def normalize_evaluation(report, review):
    result=dict(format='dashboard-evaluation-v1',status='missing',reason=None,definition=None,
                report=None,trusted=False,criteria=[],operational=assessment_state(report))
    if report is None: return result
    try:
        if not isinstance(report,dict): raise ValueError('Report must be an object')
        version=report.get('format')
        if version not in ('private-candidate-diagnostic-v5','evaluation-report-v1'):
            result.update(status='unsupported',reason='Unsupported report format: '+str(version)); return result
        if 'observation_definition' in report:
            definition=deepcopy(validate_evaluation_definition(report['observation_definition']))
            if definition['report_format']!=version: raise ValueError('Report and definition formats differ')
        elif version=='private-candidate-diagnostic-v5':
            definition=deepcopy(legacy_definition())
            actual=obj(obj(report.get('assignment')).get('rubric')).get('sha256')
            if not actual:
                result.update(status='unsupported',reason='Historical report has no recorded rubric identity'); return result
            if actual!=definition['rubric_sha256']:
                result.update(status='unsupported',reason='No retained definition for this historical rubric'); return result
            definition['protocol']=obj(obj(report.get('assignment')).get('assessment_route')).get('evaluator_protocol') or 'legacy-recorded-protocol'
            definition['sha256']=fingerprint({k:v for k,v in definition.items() if k!='sha256'})
        else: raise ValueError('A versioned report requires its evaluation definition')
        assignment=obj(report.get('assignment'))
        rubric=obj(assignment.get('rubric')).get('sha256')
        protocol=obj(assignment.get('assessment_route')).get('evaluator_protocol')
        if rubric and rubric!=definition['rubric_sha256']: raise ValueError('Report rubric differs from definition')
        if protocol and protocol!=definition['protocol']: raise ValueError('Report protocol differs from definition')
        maximum=definition['score']['maximum']
        if version=='evaluation-report-v1':
            raw_results=report.get('criteria')
            if not isinstance(raw_results,list): raise ValueError('Criteria must be a list')
            gates,checks={}, {d:{} for d in definition['checks']}
            seen=set()
            for criterion in raw_results:
                domain,name=criterion['domain'],criterion['id']
                if (domain,name) in seen: raise ValueError('Duplicate criterion')
                seen.add((domain,name))
                inventory=definition['gates'] if domain=='hard_gates' else definition['checks'].get(domain,{})
                if name not in inventory: raise ValueError('Undeclared criterion')
                if criterion['verdict'] not in ('pass','fail','unknown'): raise ValueError('Unknown criterion verdict')
                passed={'pass':True,'fail':False,'unknown':None}[criterion['verdict']]
                if domain=='hard_gates': gates[name]=dict(passed=passed,cause=criterion.get('cause'),detail=criterion.get('reason',''))
                else: checks[domain][name]=passed
            score=obj(report.get('score'))
            normalized=dict(status=report.get('status'),assignment=assignment,gates=gates,checks=checks,
                diagnostic_score=dict(score=score.get('value'),strict_correct=score.get('strict_correct'),status=score.get('status')),
                grading_enabled=report.get('grading_enabled',False),comparison=report.get('comparison'),candidate_keff=report.get('candidate_keff'))
            result['criteria']=deepcopy(raw_results)
        else:
            normalized=deepcopy(report)
        if not isinstance(normalized.get('gates'),dict) or not isinstance(normalized.get('checks'),dict):
            raise ValueError('Missing or malformed gate/check inventory')
        unknown_domains=set(normalized['checks'])-set(definition['checks'])
        if unknown_domains or set(normalized['gates'])-set(definition['gates']): raise ValueError('Undeclared check inventory')
        for domain,names in definition['checks'].items():
            supplied=normalized['checks'].get(domain,{})
            if not isinstance(supplied,dict) or set(supplied)-set(names): raise ValueError('Invalid domain inventory')
            if any(v is not None and type(v) is not bool for v in supplied.values()): raise ValueError('Checks require boolean or null verdicts')
        for gate in normalized['gates'].values():
            if not isinstance(gate,dict) or (gate.get('passed') is not None and type(gate.get('passed')) is not bool): raise ValueError('Invalid gate verdict')
        score=normalized.get('diagnostic_score')
        if not isinstance(score,dict): raise ValueError('Missing score record')
        categories=score.get('categories',{})
        if not isinstance(categories,dict) or any(not isinstance(v,dict) for v in categories.values()):
            raise ValueError('Malformed category score record')
        value=score.get('score')
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=maximum):
            raise ValueError('Score outside declared scale')
        if score.get('strict_correct') is not None and type(score['strict_correct']) is not bool: raise ValueError('Invalid strict-success flag')
        comparison=obj(normalized.get('comparison'))
        if comparison:
            margin=comparison.get('margin_pcm')
            if margin!=definition['rules'].get('equivalence_margin_pcm'): raise ValueError('Comparison rule differs from recorded definition')
            interval=comparison.get('interval_pcm')
            if interval is not None and (not isinstance(interval,list) or len(interval)!=2 or
                    any(type(v) not in (int,float) or not math.isfinite(v) for v in interval) or interval[0]>interval[1]):
                raise ValueError('Malformed comparison interval')
        review=obj(review)
        hash_required=version=='evaluation-report-v1' or 'observation_definition' in report
        binding=review.get('report_sha256')==fingerprint(report) if hash_required or 'report_sha256' in review else True
        all_passed = all(normalized['checks'].get(d, {}).get(n) is True for d, names in definition['checks'].items() for n in names) and all(obj(normalized['gates'].get(n)).get('passed') is True for n in definition['gates'])
        trusted=(score.get('status') in ('scored','model_gate_failure','unscored') and review.get('evidence_status')=='coherent' and binding and review.get('score')==value
                 and type(review.get('strict_correct')) is bool and review.get('strict_correct')==score.get('strict_correct')
                 and (review.get('strict_correct') is not True or (all_passed and value==maximum and score.get('status')=='scored')))
        for domain,names in definition['checks'].items():
            for name in names: normalized['checks'].setdefault(domain,{}).setdefault(name,None)
        for name in definition['gates']:
            normalized['gates'].setdefault(name,dict(passed=None,cause=None,detail='No retained verdict'))
        normalized['diagnostic_score'].setdefault('categories',{})
        normalized.setdefault('status','incomplete')
        result.update(status='supported',definition=definition,report=normalized,trusted=trusted)
        if review.get('evidence_status')=='coherent' and not trusted: result['reason']='Review does not bind consistently to this report'
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        result.update(status='invalid',reason=str(exc),report=None,trusted=False)
    return result
