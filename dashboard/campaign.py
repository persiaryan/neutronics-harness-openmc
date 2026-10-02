"""Descriptive aggregates of retained reviews. No execution or scientific grading."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from dashboard.projection import Evidence, confined

RUBRIC_BYTES = (Path(__file__).resolve().parents[1]/'evaluation/benchmark_suite/scoring.json').read_bytes()
RUBRIC = json.loads(RUBRIC_BYTES)
RUBRIC_HASH = hashlib.sha256(RUBRIC_BYTES).hexdigest()
CHECKS = {k: v['checks'] for k, v in RUBRIC['categories'].items()}
CHECKS['hard_gates'] = RUBRIC['hard_gates']
DOMAINS = ['overall', 'hard_gates', *RUBRIC['categories']]
CONFIGURATIONS = {
    'A': ('guided_construction', 'generic_coding_guided_construction_v1'),
    'B': ('guided_boundaries', 'generic_coding_guided_boundaries_v3'),
    'C': ('guided_boundaries_smoke', 'generic_coding_guided_boundaries_smoke_v1'),
}


def obj(value):
    return value if isinstance(value, dict) else {}


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def configuration(plan):
    for letter, (assistance, condition) in CONFIGURATIONS.items():
        if (plan.get('assistance') == assistance or plan.get('condition') == condition) and all(
                plan.get(k) in (None, '', v) for k, v in [('assistance', assistance), ('condition', condition)]):
            return letter
    return '?'


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
            score = obj(report.get('diagnostic_score'))
            rubric = obj(assignment.get('rubric'))
            supported = rubric.get('sha256') == RUBRIC_HASH
            valid_score = score.get('score') is None or (number(score.get('score')) is not None and score['score'] <= 100)
            trusted = (review.get('evidence_status') == 'coherent' and supported
                       and valid_score and score.get('status') in ('scored', 'model_gate_failure', 'unscored')
                       and (review.get('strict_correct') is not True or (score.get('status') == 'scored' and score.get('score') == 100))
                       and review.get('score') == score.get('score')
                       and type(review.get('strict_correct')) is bool
                       and review.get('strict_correct') == score.get('strict_correct'))
            checks, domains = {}, {}
            for domain, names in CHECKS.items():
                raw = obj(report.get('gates' if domain == 'hard_gates' else 'checks'))
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
                          profile=profile, rubric=rubric.get('sha256'), adapter=plan.get('adapter'),
                          builder_image=manifest.get('image_id'), request_setup_sha256=digest(manifest['required_request_setup']) if manifest.get('required_request_setup') else None,
                          reference_scope='public_demo' if assessment.name == 'assessment-public-demo' else 'private')
            prompts = obj(obj(plan.get('prompts')).get(case))
            signature = dict(prompt=prompts.get('prompt_sha256'), reference=assignment.get('reference'), sampling=assignment.get('sampling'))
            elapsed = number(builder.get('elapsed_seconds'))
            tokens = number(obj(effort.get('token_usage')).get('total_tokens')) if effort.get('token_usage_complete') is True else None
            records.append(dict(id=f'{run_id}:{case}', run=run_id, run_name=e.root.name, task_index=task_index,
                case=case, configuration=configuration(plan), cohort=digest(cohort), context=cohort,
                task_signature=digest(signature), task_identity_known=bool(signature['prompt'] and signature['reference'] and signature['sampling']),
                report_path=str(assessment/'report.json'), review_path=str(assessment/'review.json'),
                review_status=review.get('evidence_status', 'absent'), report_status=report.get('status', 'pending'),
                builder_status=builder.get('status', 'pending'), domains=domains, checks=checks,
                score=number(score.get('score')) if trusted else None,
                elapsed_seconds=elapsed, tokens=tokens, requests=number(builder.get('request_count')),
                assistance_budgets={k:budgets.get(k) for k in ('boundary_calls','boundary_seconds','smoke_calls','smoke_native_seconds')},
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


def group(rows, tasks, blocked_tasks=()):
    domains = {d: summarize(rows, tasks, lambda r: r['domains'][d]) for d in DOMAINS}
    checks = {d: {c: summarize(rows, tasks, lambda r: r['checks'][d][c]) for c in names} for d, names in CHECKS.items()}
    if set(tasks).intersection(blocked_tasks):
        for value in [*domains.values(), *(v for domain in checks.values() for v in domain.values())]:
            value.update(rate=None, possible_rate=None)
    return dict(domains=domains, checks=checks, n=len(rows),
                efforts={k: mean([r[k] for r in rows]) for k in ('elapsed_seconds', 'tokens', 'requests', 'score')})


def aggregate(records, warnings=()):
    buckets = defaultdict(list)
    for record in records:
        buckets[record['cohort']].append(record)
    cohorts = []
    for identity, rows in buckets.items():
        tasks = sorted({r['case'] for r in rows})
        valid = [r for r in rows if r['configuration'] in CONFIGURATIONS]
        conflicts = [t for t in tasks if len({r['task_signature'] for r in valid if r['case'] == t}) > 1]
        budget_conflicts = [c for c in CONFIGURATIONS if len({digest(r['assistance_budgets']) for r in valid if r['configuration'] == c}) > 1]
        blocked_tasks = tasks if budget_conflicts else conflicts
        groups = {c: group([r for r in valid if r['configuration'] == c], tasks, blocked_tasks) for c in CONFIGURATIONS}
        by_task = {t: {c: group([r for r in valid if r['case'] == t and r['configuration'] == c], [t], blocked_tasks) for c in CONFIGURATIONS} for t in tasks}
        context = rows[0]['context']
        comparable = (bool(valid) and not conflicts and not budget_conflicts and all(r['task_identity_known'] for r in valid)
                      and bool(context['model'] and context['protocol'] and context['rubric'] and context['builder_image'])
                      and all(v is not None for v in context['budgets'].values()))
        cohorts.append(dict(id=identity, context=context, tasks=tasks, groups=groups, by_task=by_task,
                            conflicting_tasks=conflicts, conflicting_tool_budgets=budget_conflicts,
                            assistance_budgets={c: next((r['assistance_budgets'] for r in valid if r['configuration'] == c), None) for c in CONFIGURATIONS},
                            comparable=comparable, excluded=sum(r['configuration']=='?' for r in rows)))
    return dict(format='dashboard-campaign-v1', domains=DOMAINS, cohorts=cohorts,
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
