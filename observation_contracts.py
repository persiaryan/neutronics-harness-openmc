"""Host-owned descriptions for observation. No candidate import or scientific grading."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value):
        raise ValueError('Invalid observation identifier')
    return value


def label(value):
    if not isinstance(value, dict) or not value or any(k not in ('en','fr') or not isinstance(v,str) or not v.strip() for k,v in value.items()):
        raise ValueError('Expected localized label')


def validate_tool(tool):
    identifier(tool['id']); identifier(tool['version']); label(tool['label'])
    if tool.get('directory') is not None:
        identifier(tool['directory'])
    if tool.get('budget_key') is not None:
        identifier(tool['budget_key'])
    if tool.get('working_xml') not in (None,'model.xml','execution/working.xml'):
        raise ValueError('Unsupported legacy working XML mapping')
    return tool


def validate_configuration(value):
    if value.get('format') != 'observation-configuration-v1':
        raise ValueError('Unsupported configuration description')
    descriptor=value['configuration']
    for name in ('id','version','assistance','condition'):
        identifier(descriptor[name])
    label(descriptor['label']); label(descriptor['description'])
    tools=value['tools']
    if not isinstance(tools,list): raise ValueError('Invalid tool inventory')
    ids=[validate_tool(t)['id'] for t in tools]
    if len(set(ids)) != len(ids) or descriptor['tools'] != ids:
        raise ValueError('Inconsistent tool inventory')
    body={k:v for k,v in value.items() if k!='sha256'}
    if value.get('sha256') != fingerprint(body):
        raise ValueError('Configuration description digest mismatch')
    return value


def catalog():
    value=json.loads((ROOT/'observation_catalog.json').read_text())
    if value['format']!='observation-catalog-v1': raise ValueError('Unknown observation catalog')
    return value


def describe_configuration(plan, *, historical=False):
    """Prefer the session snapshot; exact catalog identities support legacy sessions."""
    if 'observation_configuration' in plan:
        value=deepcopy(validate_configuration(plan['observation_configuration']))
        config=value['configuration']
        if any(plan.get(k)!=config[k] for k in ('assistance','condition')):
            raise ValueError('Plan differs from configuration description')
        return value
    definitions=json.loads((ROOT/'dashboard/legacy/configurations-v1.json').read_text()) if historical else catalog()
    for config in definitions['configurations']:
        if any(plan.get(k)==config[k] for k in ('assistance','condition')) and all(plan.get(k) in (None,'',config[k]) for k in ('assistance','condition')):
            tools=[next(t for t in definitions['tools'] if t['id']==name) for name in config['tools']]
            value=dict(format='observation-configuration-v1',configuration=config,tools=tools)
            value['sha256']=fingerprint(value)
            return deepcopy(validate_configuration(value))
    return None


def evaluation_definition(rubric, rubric_hash, protocol):
    """Snapshot the evaluator's actual rubric; never consult this for historical runs."""
    def item(name):
        return dict(label={'en':name.replace('_',' ').capitalize()},description={'en':'All declared required observations must satisfy this check.'},unit=None,rule=None)
    checks={domain:{name:item(name) for name in group['checks']} for domain,group in rubric['categories'].items()}
    rules={k:rubric[k] for k in ('equivalence_margin_pcm','interval_multiplier','maximum_candidate_std_dev_pcm','entropy_active_half_drift_screen_bits') if k in rubric}
    value=dict(format='evaluation-definition-v1',protocol=protocol,report_format='private-candidate-diagnostic-v5',
               rubric_sha256=rubric_hash,score=dict(maximum=100,applicable_points=rubric['applicable_points']),
               checks=checks,gates={name:item(name) for name in rubric['hard_gates']},
               domain_labels={domain:{'en':domain.replace('_',' ').capitalize()} for domain in checks},
               weights={domain:group['weight'] for domain,group in rubric['categories'].items()},rules=rules,
               aggregation='all-required-checks-v1')
    value['sha256']=fingerprint(value)
    return validate_evaluation_definition(value)


def validate_evaluation_definition(value):
    if not isinstance(value,dict) or value.get('format')!='evaluation-definition-v1' or value.get('aggregation')!='all-required-checks-v1':
        raise ValueError('Unsupported evaluation definition')
    identifier(value['protocol'])
    if value.get('report_format') not in ('private-candidate-diagnostic-v5','evaluation-report-v1'):
        raise ValueError('Unsupported report format')
    for field in ('maximum','applicable_points'):
        n=value['score'][field]
        if type(n) not in (int,float) or not math.isfinite(n) or n<=0:
            raise ValueError('Invalid score scale')
    if not isinstance(value.get('rules'),dict): raise ValueError('Invalid rule inventory')
    for n in value['rules'].values():
        if type(n) not in (int,float) or not math.isfinite(n) or n<0: raise ValueError('Invalid numeric rule')
    if not isinstance(value.get('checks'),dict) or not value['checks'] or not isinstance(value.get('gates'),dict) or not value['gates']:
        raise ValueError('Empty required-check inventory')
    for domain,checks in value['checks'].items():
        identifier(domain)
        if domain in ('overall','hard_gates'): raise ValueError('Reserved domain')
        if not isinstance(checks,dict) or not checks: raise ValueError('Empty required domain')
    for group in [value['gates'],*value['checks'].values()]:
        for name,description in group.items():
            identifier(name); label(description['label'])
            if description.get('unit') is not None and not isinstance(description['unit'],str): raise ValueError('Invalid unit')
    body={k:v for k,v in value.items() if k!='sha256'}
    if value.get('sha256')!=fingerprint(body): raise ValueError('Evaluation definition digest mismatch')
    return value
