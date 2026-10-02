"""Descriptive aggregates of retained reviews. No execution or scientific grading."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from dashboard.projection import Evidence, confined

from dashboard.contracts import configuration_view, normalize_evaluation
from observation_contracts import catalog, fingerprint

CONFIGURATIONS = {c['id']: c for c in catalog()['configurations']}


def obj(value):
    return value if isinstance(value, dict) else {}


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def configuration(plan):
    value = configuration_view(plan)['definition']
    return value['configuration']['id'] if value else '?'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def outcome(values):
    if any(v == 'fail' for v in values):
        return 'fail'
    return 'pass' if values and all(v == 'pass' for v in values) else 'unknown'


def read_records(roots):
    records, warnings = [], []
    for run_id, root in enumerate(roots):
        e = Evidence(root)
        plan = e.json('plan.json') or {}
        summary = e.json('summary.json') or {}
        cases = plan.get('cases') or []
        if not isinstance(cases, list):
            warnings.append(dict(run=run_id, reason='invalid_task_inventory'))
            continue
        if not cases:
            folder = confined(e.root, 'runs')
            cases = sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.is_symlink()) if folder.is_dir() else []
        if not cases:
            warnings.append(dict(run=run_id, reason='missing_task_inventory'))
        seen = set()
        for task_index, case in enumerate(cases):
            if not isinstance(case, str) or Path(case).name != case or case in ('.', '..') or case in seen:
                warnings.append(dict(run=run_id, reason='invalid_or_duplicate_task'))
                continue
            seen.add(case)
            base = Path('runs')/case
            assessment = base/'assessment'
            if confined(e.root, base/'assessment-public-demo').exists():
                assessment = base/'assessment-public-demo'
            report = e.json(assessment/'report.json') or {}
            review = e.json(assessment/'review.json') or {}
            builder = e.json(base/'builder/result.json') or {}
            manifest = e.json(base/'builder/manifest.json') or {}
            summary_tasks = summary.get('tasks')
            row = next((v for v in (summary_tasks if isinstance(summary_tasks, list) else []) if isinstance(v, dict) and v.get('case') == case), {})
            effort = obj(obj(row.get('authoring')).get('effort'))
            assignment = obj(report.get('assignment'))
            evaluation = normalize_evaluation(report or None, review)
            definition = evaluation['definition']
            presented = evaluation['report'] or {}
            score = obj(presented.get('diagnostic_score'))
            rubric = obj(assignment.get('rubric'))
            supported = evaluation['status'] == 'supported'
            trusted = evaluation['trusted']
            inventory = {**definition['checks'], 'hard_gates': definition['gates']} if definition else {}
            config_view = configuration_view(plan)
            config_definition = config_view['definition']
            checks, domains = {}, {}
            for domain, names in inventory.items():
                raw = obj(presented.get('gates' if domain == 'hard_gates' else 'checks'))
                if domain != 'hard_gates':
                    raw = obj(raw.get(domain))
                checks[domain] = {}
                for name in names:
                    value = raw.get(name)
                    if domain == 'hard_gates':
                        gate = obj(value)
                        value = gate.get('passed')
                        if value is False and gate.get('cause') != 'model':
                            value = None
                    checks[domain][name] = ('pass' if value is True else 'fail' if value is False else 'unknown') if trusted else 'unknown'
                domains[domain] = outcome(list(checks[domain].values()))
            domains['overall'] = outcome(list(domains.values()))
            if domains['overall'] == 'pass' and (review.get('strict_correct') is not True or report.get('status') != 'assessed'):
                domains['overall'] = 'unknown'
            budgets = obj(plan.get('budgets'))
            route = obj(assignment.get('assessment_route'))
            profile = obj(route.get('execution_profile')) or obj(plan.get('execution_profile'))
            cohort = dict(model=plan.get('model'), protocol=route.get('evaluator_protocol') or plan.get('evaluator_protocol'),
                          budgets={k: budgets.get(k) for k in ('model_requests', 'authoring_seconds', 'automatic_retries')},
                          profile=profile, rubric=definition['rubric_sha256'] if definition else rubric.get('sha256'), definition=definition['sha256'] if definition else None, adapter=plan.get('adapter'),
                          builder_image=manifest.get('image_id'), request_setup_sha256=digest(manifest['required_request_setup']) if manifest.get('required_request_setup') else None,
                          reference_scope='public_demo' if assessment.name == 'assessment-public-demo' else 'private')
            prompts = obj(obj(plan.get('prompts')).get(case))
            signature = dict(prompt=prompts.get('prompt_sha256'), reference=assignment.get('reference'), sampling=assignment.get('sampling'))
            elapsed = number(builder.get('elapsed_seconds'))
            tokens = number(obj(effort.get('token_usage')).get('total_tokens')) if effort.get('token_usage_complete') is True else None
            records.append(dict(id=f'{run_id}:{case}', run=run_id, run_name=e.root.name, task_index=task_index,
                case=case, configuration=configuration(plan), configuration_description=config_definition, configuration_status=config_view['status'], evaluation_status=evaluation['status'], evaluation_reason=evaluation['reason'], definition=definition, cohort=digest(cohort), context=cohort,
                task_signature=digest(signature), task_identity_known=bool(signature['prompt'] and signature['reference'] and signature['sampling']),
                report_path=str(assessment/'report.json'), review_path=str(assessment/'review.json'),
                review_status=review.get('evidence_status', 'absent'), report_status=report.get('status', 'pending'),
                builder_status=builder.get('status', 'pending'), domains=domains, checks=checks,
                score=number(score.get('score')) if trusted else None,
                elapsed_seconds=elapsed, tokens=tokens, requests=number(builder.get('request_count')),
                assistance_budgets={k:v for k,v in budgets.items() if k not in ('model_requests','authoring_seconds','automatic_retries')},
                supported_rubric=supported, trusted=trusted))
        warnings.extend(dict(run=run_id, **w) for w in e.warnings)
    return records, warnings


def summarize(rows, tasks, getter):
    """Equal task weights; absent tasks suppress rates. Unknowns stay in denominators."""
    counts = Counter(getter(r) for r in rows)
    by_task = []
    for task in tasks:
        values = [getter(r) for r in rows if r['case'] == task]
        n = len(values)
        c = Counter(values)
        by_task.append(dict(case=task, n=n, passed=c['pass'], failed=c['fail'], unknown=c['unknown']))
    complete = bool(by_task) and all(t['n'] for t in by_task)
    lower = sum(t['passed']/t['n'] for t in by_task)/len(by_task) if complete else None
    upper = sum((t['passed']+t['unknown'])/t['n'] for t in by_task)/len(by_task) if complete else None
    return dict(n=len(rows), passed=counts['pass'], failed=counts['fail'], unknown=counts['unknown'],
                rate=lower, possible_rate=upper, task_counts=by_task, coverage_complete=complete)


def mean(values):
    values = [v for v in values if v is not None]
    return dict(mean=sum(values)/len(values) if values else None, n=len(values))


def group(rows, tasks, inventory, blocked_tasks=()):
    domains = {d: summarize(rows, tasks, lambda r: r['domains'].get(d, 'unknown')) for d in ['overall', *inventory]}
    checks = {d: {c: summarize(rows, tasks, lambda r: r['checks'].get(d, {}).get(c, 'unknown')) for c in names} for d, names in inventory.items()}
    if set(tasks).intersection(blocked_tasks):
        for value in [*domains.values(), *(v for domain in checks.values() for v in domain.values())]:
            value.update(rate=None, possible_rate=None)
    return dict(domains=domains, checks=checks, n=len(rows),
                efforts={k: mean([r[k] for r in rows]) for k in ('elapsed_seconds', 'tokens', 'requests', 'score')})


def aggregate(records, warnings=()):
    # Same human label can denote different retained configuration versions.
    descriptors = {fingerprint(c): c for c in CONFIGURATIONS.values()}
    for record in records:
        snapshot = record.get('configuration_description')
        if snapshot:
            descriptor = {**snapshot['configuration'], 'tool_definitions': snapshot['tools']}
            descriptors[fingerprint(descriptor)] = descriptor
    # Remove default placeholders where recorded definitions supply that ID/version.
    recorded_ids = {r['configuration'] for r in records if r.get('configuration_description')}
    descriptors = {h:c for h,c in descriptors.items() if 'tool_definitions' in c or c['id'] not in recorded_ids}
    counts = Counter(c['id'] for c in descriptors.values())
    keys = {h: c['id'] if counts[c['id']] == 1 else c['id']+'@'+c['version']+'-'+h[:6] for h,c in descriptors.items()}
    configurations = {keys[h]:c for h,c in descriptors.items()}
    records = [dict(r) for r in records]
    for record in records:
        snapshot = record.get('configuration_description')
        if snapshot:
            record['configuration'] = keys[fingerprint({**snapshot['configuration'], 'tool_definitions': snapshot['tools']})]
    buckets = defaultdict(list)
    for record in records:
        buckets[record['cohort']].append(record)
    cohorts = []
    for identity, rows in buckets.items():
        tasks = sorted({r['case'] for r in rows})
        definition = rows[0].get('definition')
        inventory = {'hard_gates': definition['gates'], **definition['checks']} if definition else {}
        valid = [r for r in rows if r['configuration'] in configurations]
        conflicts = [t for t in tasks if len({r['task_signature'] for r in valid if r['case'] == t}) > 1]
        budget_conflicts = [c for c in configurations if len({digest(r['assistance_budgets']) for r in valid if r['configuration'] == c}) > 1]
        blocked_tasks = tasks if budget_conflicts else conflicts
        groups = {c: group([r for r in valid if r['configuration'] == c], tasks, inventory, blocked_tasks) for c in configurations}
        by_task = {t: {c: group([r for r in valid if r['case'] == t and r['configuration'] == c], [t], inventory, blocked_tasks) for c in configurations} for t in tasks}
        context = rows[0]['context']
        comparable = (bool(valid) and definition is not None and not conflicts and not budget_conflicts and all(r['task_identity_known'] for r in valid)
                      and bool(context['model'] and context['protocol'] and context['rubric'] and context['builder_image'])
                      and all(v is not None for v in context['budgets'].values()))
        cohorts.append(dict(id=identity, context=context, definition=definition, configurations=configurations, domains=['overall', *inventory], tasks=tasks, groups=groups, by_task=by_task,
                            conflicting_tasks=conflicts, conflicting_tool_budgets=budget_conflicts,
                            assistance_budgets={c: next((r['assistance_budgets'] for r in valid if r['configuration'] == c), None) for c in configurations},
                            comparable=comparable, excluded=sum(r['configuration']=='?' for r in rows)))
    return dict(format='dashboard-campaign-v2', configurations=configurations, cohorts=cohorts,
                records=records, warnings=list(warnings), assignments=len(records))


def campaign(roots):
    return aggregate(*read_records(roots))


def selected_roots(runs, manifest=None):
    roots = list(runs or [])
    if manifest:
        path = Path(manifest).resolve()
        if path.stat().st_size > 1_000_000:
            raise ValueError('Campaign manifest too large')
        value = json.loads(path.read_text())
        entries = value.get('runs') if isinstance(value, dict) else None
        if not isinstance(entries, list) or not entries or any(not isinstance(p, str) or not p for p in entries):
            raise ValueError('Campaign manifest requires a nonempty runs array of directory paths')
        roots.extend(path.parent/entry for entry in entries)
    roots = [Path(p).resolve() for p in roots]
    if not roots or len(roots) > 1000 or len(set(roots)) != len(roots):
        raise ValueError('Select 1–1000 distinct run directories; duplicate roots would count sessions twice')
    return roots
