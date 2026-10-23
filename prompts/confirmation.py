"""Prepare the separate twelve-task candidate suite; no execution or assessment."""
import argparse
import hashlib
import json
from pathlib import Path

from prompts import prepare as public

MANIFEST = 'confirmation_v2/manifest.json'
TASKS = (
    'offset_plate_bank', 'staggered_seven_pin_cluster',
    'three_annular_fuel_channels', 'separated_twin_bundles',
    'cross_shaped_mixture', 'indc107_reflective_pin',
    'stepped_axial_mixture', 'wrapped_eight_pin_channel',
    'mixed_boundary_fuel_slab', 'cylindrical_void_sleeve',
    'dual_temperature_pin_pair', 'restricted_source_nine_pin',
)


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def suite():
    """Verify the public inventory; do not resolve or load private references."""
    text = public.read_public_text(MANIFEST)
    value = json.loads(text)
    records = value.get('tasks', [])
    if (value.get('format') != 'region-confirmation-task-suite-v1'
            or value.get('task_count') != 12
            or [r.get('id') for r in records] != list(TASKS)
            or value.get('assessment_ready') is not False
            or value.get('grading_enabled') is not False):
        raise ValueError('Unexpected candidate task inventory or qualification')
    if value.get('template_path') != 'template_factory_v1.md':
        raise ValueError('Unexpected task template')
    template = public.read_public_text('template_factory_v1.md')
    if digest(template) != value['template_sha256']:
        raise ValueError('Candidate task template changed')
    if template.count('{{TASK_SPECIFICATION}}') != 1:
        raise ValueError('Template must contain exactly one task marker')
    for index, record in enumerate(records):
        expected = ('confirmation_v2/cases/' if index == 5 else 'confirmation_v1/cases/') + TASKS[index] + '.md'
        if (record.get('path') != expected
                or record.get('family') != ('external_control' if index == 5 else 'reuse' if index < 4 else 'transfer' if index < 8 else 'control')
                or record.get('assessment_ready') is not False
                or record.get('reference_status') != 'not_created'):
            raise ValueError('Unexpected candidate task path or qualification')
        task = public.read_public_text(expected)
        if digest(task) != record['sha256'] or len(task.encode()) != record['bytes']:
            raise ValueError('Candidate task specification changed: ' + record['id'])
    return value, digest(text)


def build_prompt(case):
    if case not in TASKS:
        raise ValueError('Unknown confirmation candidate task')
    inventory, _ = suite()
    record = next(r for r in inventory['tasks'] if r['id'] == case)
    template = public.read_public_text('template_factory_v1.md')
    task = public.read_public_text(record['path'])
    return template.replace('{{TASK_SPECIFICATION}}', task.rstrip()).rstrip() + '\n'


def prepare(case, output):
    """Write a fresh public-only prompt bundle, explicitly unqualified."""
    if case not in TASKS:
        raise ValueError('Unknown confirmation candidate task')
    inventory, inventory_sha256 = suite()
    record = next(r for r in inventory['tasks'] if r['id'] == case)
    task = public.read_public_text(record['path'])
    template = public.read_public_text('template_factory_v1.md')
    prompt = template.replace('{{TASK_SPECIFICATION}}', task.rstrip()).rstrip() + '\n'
    messages = json.dumps([dict(role='user', content=prompt)], indent=2, ensure_ascii=False) + '\n'
    manifest = dict(format='builder-input-v2', case=case,
        delivery_contract='openmc-model-factory-v1', prompt_sha256=digest(prompt),
        messages_sha256=digest(messages), message_count=1,
        required_session='fresh; no inherited conversation or memory',
        required_capabilities='contained generic coding; assistance declared separately',
        dispatch_implemented=False, candidate_execution_implemented=False,
        candidate_suite=inventory['id'], suite_manifest_sha256=inventory_sha256,
        task_sha256=record['sha256'], assessment_ready=False,
        scientific_review='pending_owner_review', reference_status='not_created',
        held_out_status=inventory['held_out_status'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output/'prompt.txt').write_text(prompt, encoding='utf-8')
    (output/'messages.json').write_text(messages, encoding='utf-8')
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--case', choices=TASKS)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.check and args.output:
        parser.error('--check does not create an output')
    if args.case and args.output is None:
        parser.error('--case requires a fresh --output directory')
    try:
        if args.check:
            inventory, sha256 = suite()
            result = dict(status='specification_inventory_verified', tasks=len(inventory['tasks']),
                          suite_manifest_sha256=sha256, assessment_ready=False)
        else:
            result = prepare(args.case, args.output)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
