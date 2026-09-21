"""Verify this adapter's retained submission; scientific assessment is provider-neutral."""
import json
from pathlib import Path
from builder import openmc_python, boundary_tool
from builder.context import sha256, request_inventory
from builder.route import condition_prompt, CONDITIONS, BOUNDARY_CONDITIONS
from builder.run import verify_container
from evaluator.contracts import FACTORY
from evaluator.profiles import assessment_route, FACTORY_PROFILE, BOUNDARY_PROTOCOL
from evaluator.transport_input import read_regular
from prompts.prepare import build_prompt


def submission(directory, case, *, recorded_protocol=None):
    directory = Path(directory)
    def read(name):
        return json.loads(read_regular(directory / name))
    def require(value, message):
        if not value:
            raise ValueError(message)
    manifest, result, life = [read(n) for n in ('manifest.json','result.json','lifecycle.json')]
    base = build_prompt(case)
    route = assessment_route(FACTORY, FACTORY_PROFILE, BOUNDARY_PROTOCOL)
    if recorded_protocol is not None:
        # Explicit read-only migration binding. Dispatch still accepts only the
        # current protocol; retained authoring is never relabelled as a new run.
        require(recorded_protocol == 'factory-assessment-boundaries-v3',
                'Unsupported retained authoring protocol')
        route['evaluator_protocol'] = recorded_protocol
    route['prompt_sha256'] = sha256(base.encode())
    assistance = manifest['assistance']
    expected = condition_prompt(base, assistance).encode()
    require(manifest['delivery_contract'] == FACTORY and manifest['assessment_route'] == route,
            'Builder delivery contract/profile/protocol changed')
    require(manifest['case'] == case and manifest['mode'] in ('mock','subscription'), 'Builder assignment changed')
    require(manifest['condition'] == CONDITIONS[assistance],
            'Builder condition changed')
    require(manifest['image_id'] == openmc_python.IMAGE_ID and manifest['authoring_environment'] == openmc_python.ENVIRONMENT,
            'Authoring environment changed')
    info = read('container.json')
    verify_container(info, openmc_python.IMAGE_ID)
    openmc_python.verify_image(info, True)
    openmc_python.verify_probe(read('environment-probe.json'), True)
    require(result['status'] == 'completed' and result['cleanup_confirmed'] is True and life['state'] == 'removed',
            'Builder failed or cleanup uncertain')
    require(read_regular(directory/'prompt.txt') == expected and manifest['prompt_sha256'] == sha256(expected), 'Builder prompt changed')
    require(manifest['base_task_prompt_sha256'] == route['prompt_sha256'], 'Public task binding changed')
    require(('boundary_tool' in manifest) == (assistance in BOUNDARY_CONDITIONS), 'Tool availability changed')
    if assistance in BOUNDARY_CONDITIONS:
        require(manifest['boundary_tool'] == boundary_tool.identity(), 'Boundary adapter changed')
    for number in range(1, result['request_count'] + 1):
        request = read(f'request-{number:02d}.json')
        require(request_inventory(request) == read(f'inventory-{number:02d}.json'), 'Request inventory changed')
    source = read_regular(directory/'candidate.py', limit=1_000_000)
    require(source == read_regular(directory/'answer.txt') and sha256(source) == result['answer_sha256']
            and len(source) == result['answer_bytes'], 'Builder answer/source identity mismatch')
    return source, dict(actor='llm_builder' if manifest['mode']=='subscription' else 'local_test_double',
        case=case, model=manifest['model'], adapter='codex_subscription', condition=manifest['condition'],
        prompt_sha256=manifest['prompt_sha256'], source_sha256=sha256(source), assessment_route=route,
        manifest_sha256=sha256(read_regular(directory/'manifest.json')),
        result_sha256=sha256(read_regular(directory/'result.json')))
