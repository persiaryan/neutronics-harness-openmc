"""Explicit offline native-CLI controls: no provider, model inference or transport."""
import argparse
import json
from pathlib import Path

from builder import region_skill
from builder.context import request_setup, write_json, sha256
from builder.run import run
from builder.trajectory import summarize
from prompts.prepare import prepare
from tests.fixtures.responses import mock_response


def qualify(output, model='gpt-5.6-luna'):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    prepare('reflective_pin_cell', output/'input')
    rows, setups = [], {}
    for label, assistance, read in (
            ('A', 'guided_construction', False),
            ('E-no-read', region_skill.SELECTIVE, False),
            ('E-read', region_skill.SELECTIVE, True)):
        def responder(number, body):
            if number == 1 and read:
                return mock_response(command='cat ' + region_skill.CONTAINER_PATH)
            return mock_response()
        folder = output/label
        result = run(folder, case='reflective_pin_cell', prepared_input=output/'input',
                     model=model, assistance=assistance, mode='mock', responder=responder,
                     max_requests=2, wall_seconds=60,
                     request_setup=setups.get('E') if label == 'E-read' else None)
        if result['status'] != 'completed' or not result['cleanup_confirmed']:
            raise ValueError('Offline qualification failed in ' + label + '; inspect retained artifacts')
        observed = request_setup(json.loads((folder/'request-01.json').read_bytes()))
        setups['A' if label == 'A' else 'E'] = observed
        exposure = summarize(folder, result).get('region_skill')
        if label.startswith('E'):
            expected = 'observed' if read else 'not_demonstrated'
            if (exposure['catalog_delivery'] != 'complete' or exposure['body_loading'] != expected
                    or result['request_count'] != (2 if read else 1)):
                raise ValueError('Native skill exposure control failed: ' + label)
        rows.append(dict(control=label, status='passed', requests=result['request_count'],
                         exposure=exposure, cleanup_confirmed=True))
    setups['D'] = setups['A']
    region_skill.reviewed_setups(setups)
    manifest = json.loads((output/'A/manifest.json').read_bytes())
    report = dict(format='region-skill-native-controls-v1', controls=rows,
                  requested_model=model, image_id=manifest['image_id'], entry_sha256=manifest['entry_sha256'],
                  model_inference=False, live_provider_calls=0, neutron_transport=False,
                  automatic_agent_selection_tested=False, skill_efficacy_tested=False,
                  request_setups=setups,
                  source_sha256={p:sha256(Path(p).read_bytes()) for p in (
                      'builder/region_skill.py','builder/skill_exposure.py',
                      'builder/region_skill_qualification.py','tests/fixtures/responses.py')})
    write_json(output/'report.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--model', choices=('gpt-5.6-luna','gpt-5.6-sol'), default='gpt-5.6-luna')
    args = parser.parse_args()
    report = qualify(args.output, args.model)
    print(json.dumps(dict(controls=len(report['controls']), status='passed',
                          live_provider_calls=0, automatic_agent_selection_tested=False)))
