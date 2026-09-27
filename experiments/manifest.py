"""Prepare/verify a prospective manifest. No authoring or native dispatch."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess

from builder import boundary_tool, openmc_python, smoke_tool
from builder.context import sha256
from builder.route import CONDITIONS, BOUNDARY_CONDITIONS, SMOKE_CONDITIONS, condition_prompt, request_limit
from evaluator.contracts import FACTORY
from evaluator.profiles import PROFILE, BOUNDARY_PROTOCOL
from evaluator import run as exporter
from evaluation.benchmark_suite import references, scoring
from experiments.run import budgets
from prompts.prepare import CASE_FILES, build_prompt

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'prospective-study-manifest-v1'
SOURCE_DIRECTORIES = ('builder', 'evaluator', 'evaluation', 'experiments', 'prompts')
FILES = ('spec.json', 'assignments.json', 'analysis.json', 'manifest.json', 'seal.sha256')
ANALYSIS_RULES = dict(format='descriptive-balanced-policy-v1',
    task_weights='equal', setup_pooling=False, success_denominator='all_started_assignments',
    score_denominator='available_scores_only', null_scores='preserve_null',
    intervals='wilson_95_descriptive_per_cell', unresolved='identification_bounds',
    incomplete_inventory='withhold_balanced_contrasts', historical_pooling=False,
    family_counts='may_overlap', numerical_physical_incident_outcomes='separate',
    effort='observed_delivery_and_explicit_coverage', causal_interpretation=False)
MAX_JSON_BYTES = 4_000_000


def require(value, message):
    if not value:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def regular(path):
    info = Path(path).lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            'Expected an ordinary file without links')
    return info


def read_json(path):
    info = regular(path)
    require(info.st_size <= MAX_JSON_BYTES, 'JSON exceeds preparation limit')
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    def constant(_):
        raise ValueError('Non-finite JSON value')
    value = json.loads(Path(path).read_bytes(), object_pairs_hook=pairs, parse_constant=constant)
    encode(value)  # Also reject finite-looking literals that overflow to infinity.
    return value


def keys(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected), 'Unexpected fields')


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value)
            and value not in ('.', '..'), 'Expected a short public identifier')


def sha(value):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'Invalid SHA-256')
    return value


def validate_spec(spec):
    keys(spec, ('study_id', 'tasks', 'excluded_tasks', 'setups', 'arms', 'repetitions',
                'data_id', 'reference_ids', 'assignments', 'analysis'))
    identifier(spec['study_id']); identifier(spec['data_id'])
    tasks = spec['tasks']
    require(isinstance(tasks, list) and tasks and all(isinstance(t, str) for t in tasks)
            and len(set(tasks)) == len(tasks) and set(tasks) <= set(CASE_FILES), 'Invalid task inventory')
    keys(spec['excluded_tasks'], set(CASE_FILES)-set(tasks))
    for reason in spec['excluded_tasks'].values():
        identifier(reason)
    keys(spec['reference_ids'], tasks)
    for resource in spec['reference_ids'].values():
        identifier(resource)
    setups, arms = {}, {}
    for rows, target in ((spec['setups'], setups), (spec['arms'], arms)):
        require(isinstance(rows, list) and rows, 'Declare setups and arms explicitly')
        for row in rows:
            keys(row, ('id', 'model', 'request_setup_id', 'request_budget') if target is setups
                 else ('id', 'assistance'))
            identifier(row['id']); require(row['id'] not in target, 'Duplicate setup/arm identifier')
            target[row['id']] = row
            if target is setups:
                identifier(row['model']); identifier(row['request_setup_id']); request_limit(row['request_budget'])
            else:
                require(row['assistance'] in CONDITIONS, 'Unknown assistance condition')
    require(len(arms) >= 2, 'A comparison needs at least two explicitly named arms')
    repeats = spec['repetitions']
    require(type(repeats) is int and repeats > 0, 'Repetitions must be a positive integer')
    total = len(tasks)*len(setups)*len(arms)*repeats
    require(total <= 10000, 'Manifest exceeds the 10000-assignment metadata limit')
    rows = spec['assignments']
    require(isinstance(rows, list) and len(rows) == total, 'Incomplete assignment inventory')
    actual = []
    for row in rows:
        keys(row, ('case', 'setup', 'arm', 'repeat'))
        require(row['case'] in tasks and row['setup'] in setups and row['arm'] in arms
                and type(row['repeat']) is int and 1 <= row['repeat'] <= repeats, 'Invalid assignment')
        actual.append((row['case'], row['setup'], row['arm'], row['repeat']))
    expected = [(t, s, a, r) for t in tasks for s in setups for a in arms for r in range(1, repeats+1)]
    require(Counter(actual) == Counter(expected), 'Duplicate or missing assignment')
    analysis = spec['analysis']
    keys(analysis, ('primary_contrast', 'secondary_contrasts', 'trajectory_examples'))
    pairs = [analysis['primary_contrast']]
    require(isinstance(analysis['secondary_contrasts'], list), 'Invalid secondary contrasts')
    pairs += analysis['secondary_contrasts']
    for pair in pairs:
        require(isinstance(pair, list) and len(pair) == 2 and all(isinstance(a, str) and a in arms for a in pair)
                and pair[0] != pair[1], 'Contrast must name two different declared arms')
    require(len({tuple(p) for p in pairs}) == len(pairs), 'Duplicate contrast')
    require(analysis['trajectory_examples'] in ('none', 'first_verified_success_and_non_success_per_setup_arm'),
            'Unknown trajectory example policy')
    return setups, arms


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.DEVNULL)


def source_inventory():
    records = {}
    for directory in SOURCE_DIRECTORIES:
        for path in sorted((ROOT/directory).rglob('*')):
            if 'frozen' in path.relative_to(ROOT).parts or '__pycache__' in path.parts:
                continue
            if path.suffix not in ('.py', '.md', '.json') and not path.name.startswith('Dockerfile'):
                continue
            if path.is_dir():
                continue
            regular(path)
            records[path.relative_to(ROOT).as_posix()] = sha256(path.read_bytes())
    require(records, 'No implementation inventory')
    return records


def file_identity(path):
    before = regular(path)
    with Path(path).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = regular(path)
    require((before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_ino, after.st_size, after.st_mtime_ns), 'Resource changed while hashing')
    return dict(bytes=after.st_size, sha256=digest)


def setup_identity(path):
    value = read_json(path)
    keys(value, ('request_configuration', 'generic_tools_sha256', 'instruction_messages',
                 'top_level_instructions_sha256'))
    keys(value['request_configuration'], ('tool_choice', 'parallel_tool_calls', 'reasoning',
        'store', 'stream', 'include', 'text'))
    sha(value['generic_tools_sha256']); sha(value['top_level_instructions_sha256'])
    require(isinstance(value['instruction_messages'], list), 'Invalid instruction inventory')
    for item in value['instruction_messages']:
        keys(item, ('role', 'bytes', 'sha256', 'first_line'))
        require(item['role'] in ('system', 'developer') and type(item['bytes']) is int and item['bytes'] >= 0
                and isinstance(item['first_line'], str), 'Invalid instruction identity')
        sha(item['sha256'])
    # Only the file hash enters the public manifest, not its private instructions.
    return file_identity(path)


def resource_identities(spec, bindings):
    keys(bindings, ('data', 'references', 'request_setups'))
    keys(bindings['data'], (spec['data_id'],))
    keys(bindings['references'], set(spec['reference_ids'].values()))
    setup_ids = {s['request_setup_id'] for s in spec['setups']}
    keys(bindings['request_setups'], setup_ids)
    index, _ = exporter.data_directory(Path(bindings['data'][spec['data_id']]))
    data = {p.name: file_identity(p) for p in sorted(index.parent.iterdir())}
    # Publish an aggregate inventory binding; keep individual library paths local.
    result = dict(data={spec['data_id']: dict(index_sha256=data[index.name]['sha256'],
        inventory_sha256=sha256(encode(data)), files=len(data),
        bytes=sum(v['bytes'] for v in data.values()), qualification='not_run')},
        references={}, request_setups={})
    for resource, location in bindings['references'].items():
        path = Path(location)
        checked = references.verify_package(path)
        package = read_json(path/'manifest.json')
        cases = [case for case, name in spec['reference_ids'].items() if name == resource]
        require(cases == [package.get('case')], 'Reference must be sealed for its declared task')
        result['references'][resource] = dict(manifest_sha256=checked['manifest_sha256'],
            files=checked['files'], qualification='sealed_bytes_only_not_scientific_approval')
    for resource, location in bindings['request_setups'].items():
        result['request_setups'][resource] = setup_identity(Path(location))
    return result


def compile_manifest(spec, bindings, checkpoint):
    setups, arms = validate_spec(spec)
    require(isinstance(checkpoint, str) and re.fullmatch(r'[0-9a-f]{40}', checkpoint), 'Invalid implementation commit')
    require(subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', checkpoint, 'HEAD'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0, 'Implementation commit is not an ancestor')
    resources = resource_identities(spec, bindings)
    slots, declarations = [], {}
    prompts = {}
    for setup_id, setup in setups.items():
        declarations[setup_id] = {a: budgets(arm['assistance'], setup['request_budget']) for a, arm in arms.items()}
        prompts[setup_id] = {a: {t: sha256(condition_prompt(build_prompt(t), arm['assistance'],
            request_budget=setup['request_budget']).encode()) for t in spec['tasks']} for a, arm in arms.items()}
    for number, row in enumerate(spec['assignments'], 1):
        setup, arm = setups[row['setup']], arms[row['arm']]
        slots.append(dict(row, id=f'slot-{number:04d}', order=number, model=setup['model'],
            assistance=arm['assistance'], condition=CONDITIONS[arm['assistance']],
            request_budget=setup['request_budget'], request_setup_id=setup['request_setup_id'],
            reference_id=spec['reference_ids'][row['case']], data_id=spec['data_id']))
    n_boundary = sum(s['assistance'] in BOUNDARY_CONDITIONS for s in slots)
    n_smoke = sum(s['assistance'] in SMOKE_CONDITIONS for s in slots)
    ceilings = dict(sessions=len(slots), model_requests=sum(request_limit(s['request_budget']) for s in slots),
        authoring_seconds=sum(declarations[s['setup']][s['arm']]['authoring_seconds'] for s in slots),
        boundary_calls=n_boundary*boundary_tool.PROFILE['max_calls'],
        boundary_recorded_requests=n_boundary*boundary_tool.PROFILE['max_recorded_requests'],
        smoke_calls=n_smoke*smoke_tool.PROFILE['max_calls'],
        smoke_recorded_requests=n_smoke*(smoke_tool.PROFILE['max_calls']+1),
        smoke_native_seconds=n_smoke*smoke_tool.PROFILE['max_calls']*smoke_tool.PROFILE['native_seconds'],
        independent_final_exports=len(slots), final_native_attempts=len(slots),
        final_native_seconds=len(slots)*PROFILE['budgets']['transport'], automatic_retries=0)
    analysis = dict(ANALYSIS_RULES, **spec['analysis'])
    manifest = dict(format=FORMAT, study_id=spec['study_id'], status='prepared_not_dispatched',
        execution_authorized=False, dispatch_implemented=False, from_scratch=True,
        spec_sha256=sha256(encode(spec)), assignments_sha256=sha256(encode(slots)),
        analysis_sha256=sha256(encode(analysis)), assignment_count=len(slots),
        delivery_contract=FACTORY, evaluator_protocol=BOUNDARY_PROTOCOL, execution_profile=PROFILE,
        authoring_image=openmc_python.IMAGE_ID, authoring_environment=openmc_python.ENVIRONMENT,
        boundary_tool=boundary_tool.identity() if n_boundary else None,
        smoke_tool=smoke_tool.identity() if n_smoke else None, rubric=scoring.identity(),
        budgets=declarations, ceilings=ceilings, authoring_prompt_sha256=prompts,
        resources=resources, implementation_checkpoint=checkpoint, implementation_files=source_inventory())
    return {'spec.json': spec, 'assignments.json': slots, 'analysis.json': analysis, 'manifest.json': manifest}


def prepare(output, *, spec, bindings):
    """Freeze a fresh, non-executable package; never generate candidates."""
    output = Path(output)
    require(not output.exists() and not output.is_symlink(), 'Refusing to overwrite a preparation')
    target = output.resolve()
    require(not any(target.is_relative_to((ROOT/d).resolve()) for d in SOURCE_DIRECTORIES),
            'Preparation must stay outside implementation directories')
    for location in [*bindings.get('data', {}).values(), *bindings.get('references', {}).values()]:
        path = Path(location).resolve()
        protected = path if path.is_dir() else path.parent
        require(not target.is_relative_to(protected), 'Preparation must not modify external resources')
    checkpoint = git('rev-parse', 'HEAD').decode().strip()
    documents = compile_manifest(spec, bindings, checkpoint)
    require(all(len(encode(value)) <= MAX_JSON_BYTES for value in documents.values()),
            'Prepared JSON exceeds metadata byte limit')
    output.mkdir(parents=True, exist_ok=False)
    for name, value in documents.items():
        with (output/name).open('xb') as stream:
            stream.write(encode(value))
    seal = sha256(encode(documents['manifest.json']))
    with (output/'seal.sha256').open('x') as stream:
        stream.write(seal+'\n')
    return dict(status='prepared_not_dispatched', manifest_sha256=seal,
        assignments=documents['manifest.json']['assignment_count'], model_calls=0, native_runs=0,
        execution_authorized=False)


def verify(output, *, bindings, expected_sha256=None, require_committed=False):
    """Reconstruct all declarations and compare current bytes; no writes."""
    output = Path(output)
    require(output.is_dir() and not output.is_symlink(), 'Preparation must be a real directory')
    require({p.name for p in output.iterdir()} == set(FILES), 'Prepared artifact inventory changed')
    for name in FILES:
        regular(output/name)
    spec = read_json(output/'spec.json'); manifest = read_json(output/'manifest.json')
    regular(output/'seal.sha256')
    require((output/'seal.sha256').stat().st_size == 65, 'Invalid seal length')
    seal = (output/'seal.sha256').read_text().strip(); sha(seal)
    require(sha256((output/'manifest.json').read_bytes()) == seal, 'Manifest seal changed')
    if expected_sha256 is not None:
        require(seal == sha(expected_sha256), 'Manifest differs from trusted expected hash')
    require(manifest.get('format') == FORMAT, 'Unknown manifest format')
    documents = compile_manifest(spec, bindings, manifest['implementation_checkpoint'])
    for name, expected in documents.items():
        require((output/name).read_bytes() == encode(expected), 'Prepared declaration or dependency changed: '+name)
    if require_committed:
        paths = [output/n for n in FILES]+[ROOT/n for n in manifest['implementation_files']]
        for path in paths:
            relative = path.resolve().relative_to(ROOT.resolve())
            require(git('show', f'HEAD:{relative.as_posix()}') == path.read_bytes(),
                    'Preparation or implementation differs from committed HEAD')
    return dict(status='verified_manifest', manifest_sha256=seal, assignments=manifest['assignment_count'],
        ceilings=manifest['ceilings'], committed=require_committed,
        execution_authorized=False, dispatch_implemented=False, model_calls=0, native_runs=0,
        runtime_qualification='not_run', reference_qualification='sealed_bytes_only')


def local_bindings(path):
    value = read_json(path)
    keys(value, ('data', 'references', 'request_setups'))
    return {kind: {name: str((Path(path).parent/Path(location)).absolute()) for name, location in rows.items()}
            for kind, rows in value.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prepare_cli = sub.add_parser('prepare')
    prepare_cli.add_argument('--spec', type=Path, required=True)
    verify_cli = sub.add_parser('verify')
    verify_cli.add_argument('--expected-sha256')
    verify_cli.add_argument('--require-committed', action='store_true')
    for command in (prepare_cli, verify_cli):
        command.add_argument('--output', type=Path, required=True)
        command.add_argument('--bindings', type=Path, required=True)
    args = parser.parse_args()
    try:
        bindings = local_bindings(args.bindings)
        result = (prepare(args.output, spec=read_json(args.spec), bindings=bindings) if args.action == 'prepare'
                  else verify(args.output, bindings=bindings, expected_sha256=args.expected_sha256,
                              require_committed=args.require_committed))
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        parser.error('Manifest or local dependencies are unavailable, inconsistent, or invalid')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
