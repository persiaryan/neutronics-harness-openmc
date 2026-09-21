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
}
BOUNDARY_CONDITIONS = frozenset({'boundaries', 'guided_boundaries'})
GUIDED_CONDITIONS = frozenset({'guided_construction', 'guided_boundaries'})
CONSTRUCTION_POLICY = Path(__file__).with_name('guided_construction.md')
GUIDED_POLICY = Path(__file__).with_name('guided_authoring.md')


def condition_prompt(prompt, assistance):
    if assistance not in CONDITIONS:
        raise ValueError('Unknown assistance condition')
    result = prompt + AUTHORING
    if assistance in GUIDED_CONDITIONS:
        result += CONSTRUCTION_POLICY.read_text()
    if assistance in BOUNDARY_CONDITIONS:
        from builder.boundary_tool import INSTRUCTION
        instruction = INSTRUCTION
        if assistance == 'guided_boundaries':
            instruction = instruction.replace('You may inspect', 'Inspect')
            instruction = instruction.replace(
                'Export\nXML locally if you want to use it. Tool availability does not require tool use.',
                'Follow the required working-export sequence above.')
            instruction += '\n' + GUIDED_POLICY.read_text()
        result += instruction
    return result
