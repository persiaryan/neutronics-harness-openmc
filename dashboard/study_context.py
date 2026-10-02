"""Operator-imported study identities. These never supply observed verdicts."""
import hashlib

from observation_contracts import validate_evaluation_definition


def read_context(evidence):
    value = evidence.json('dashboard-study-context.json', register=True)
    if value is None:
        return None
    try:
        if value['format'] != 'dashboard-study-context-v1':
            raise ValueError('Unsupported imported study context')
        validate_evaluation_definition(value['definition'])
        if value['context']['definition'] != value['definition']['sha256']:
            raise ValueError('Imported study definition mismatch')
        bindings = value['bindings']
        if not isinstance(bindings, dict) or 'plan.json' not in bindings:
            raise ValueError('Imported context has no plan binding')
        for path, digest in bindings.items():
            raw = evidence.raw(path)
            if (hashlib.sha256(raw).hexdigest() if raw is not None else None) != digest:
                raise ValueError('Imported context evidence changed: '+path)
        return value
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        evidence.warnings.append(dict(path='dashboard-study-context.json', reason=str(exc)))
        return None
