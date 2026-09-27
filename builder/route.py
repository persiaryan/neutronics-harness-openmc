"""Explicit factory routing; only public prompt bytes enter the builder."""
import hashlib
import json
from pathlib import Path

from evaluator.contracts import FACTORY
from evaluator.profiles import assessment_route
from prompts.prepare import build_prompt


def prepare(case, contract, profile, protocol, prepared_input):
    if contract != FACTORY or case is None or prepared_input is None:
        raise ValueError('Factory route requires a public case and prepared input')
    route = assessment_route(contract, profile, protocol)
    directory = Path(prepared_input)
    if directory.is_symlink() or any((directory / n).is_symlink() for n in ('prompt.txt', 'manifest.json', 'messages.json')):
        raise ValueError('Prepared factory input must not use links')
    prompt = (directory / 'prompt.txt').read_bytes()
    expected = build_prompt(case, contract=contract).encode()
    manifest = json.loads((directory / 'manifest.json').read_bytes())
    messages = (directory / 'messages.json').read_bytes()
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    if (prompt != expected or manifest.get('delivery_contract') != contract or manifest.get('case') != case
            or manifest.get('prompt_sha256') != digest(prompt) or manifest.get('messages_sha256') != digest(messages)
            or json.loads(messages) != [dict(role='user', content=expected.decode())]):
        raise ValueError('Prepared factory prompt/contract identity changed')
    route['prompt_sha256'] = digest(prompt)
    return prompt.decode(), route


AUTHORING = """
The authoring container includes OpenMC Python 0.15.3 and generic coding tools.
Native transport and nuclear data are not available during authoring. If a local
export needs a data-index setting, a temporary placeholder is acceptable only
for your local inspection; the submitted factory must use OPENMC_CROSS_SECTIONS.
No evaluator results or private reference are available in this session.
"""


CONDITIONS = {
    'generic': 'generic_coding_v1',
    'boundaries': 'generic_coding_boundaries_v2',
    'guided_construction': 'generic_coding_guided_construction_v1',
    'guided_boundaries': 'generic_coding_guided_boundaries_v3',
    'guided_boundaries_smoke': 'generic_coding_guided_boundaries_smoke_v1',
}
SMOKE_CONDITIONS = frozenset({'guided_boundaries_smoke'})
BOUNDARY_CONDITIONS = frozenset({'boundaries', 'guided_boundaries'}) | SMOKE_CONDITIONS
GUIDED_CONDITIONS = frozenset({'guided_construction', 'guided_boundaries'}) | SMOKE_CONDITIONS
CONSTRUCTION_POLICY = Path(__file__).with_name('guided_construction.md')
GUIDED_POLICY = Path(__file__).with_name('guided_authoring.md')


EXTENDED_REQUEST_BUDGET = 'authoring-requests-16-v1'


def request_limit(profile=None):
    if profile not in (None, EXTENDED_REQUEST_BUDGET):
        raise ValueError('Unknown authoring request-budget profile')
    return 16 if profile else 8


def condition_prompt(prompt, assistance, *, request_budget=None):
    limit = request_limit(request_budget)
    if assistance not in CONDITIONS:
        raise ValueError('Unknown assistance condition')
    environment=AUTHORING
    if assistance in SMOKE_CONDITIONS:
        environment=environment.replace('Native transport and nuclear data are not available during authoring.',
            'Native transport is available only through the bounded smoke_openmc command in a separate container.\n'
            'The coding container itself has no native solver or nuclear data.')
    result = prompt + environment
    if assistance in GUIDED_CONDITIONS:
        policy=CONSTRUCTION_POLICY.read_text()
        if assistance in SMOKE_CONDITIONS:
            policy=policy.replace('Never run native transport.',
                'Use only the provided smoke_openmc command for bounded working-model transport.')
        result += policy
    if assistance in BOUNDARY_CONDITIONS:
        from builder.boundary_tool import INSTRUCTION
        instruction = INSTRUCTION
        if assistance in GUIDED_CONDITIONS:
            instruction = instruction.replace('You may inspect', 'Inspect')
            instruction = instruction.replace(
                'Export\nXML locally if you want to use it. Tool availability does not require tool use.',
                'Follow the required working-export sequence above.')
            instruction += '\n' + GUIDED_POLICY.read_text()
        result += instruction
    if assistance in SMOKE_CONDITIONS:
        result += '\n'+Path(__file__).with_name('guided_smoke.md').read_text()
    if limit == 16:
        # Change only existing budget declarations in guidance, never public physics.
        guidance = result[len(prompt):].replace('eight-request', 'sixteen-request').replace('8-request', '16-request')
        result = prompt + guidance
    return result
