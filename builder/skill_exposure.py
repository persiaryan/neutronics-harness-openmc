"""Conservative evidence for E: metadata exposure and a literal full-file read.

Unrecognized read variants remain unresolved. No semantic application is inferred.
"""
import json
import shlex
from pathlib import Path

from builder import region_skill
from builder.trajectory import output_values, shell_command


def summarize(directory, requests, completed_turns, calls, actions):
    directory = Path(directory)
    manifest = directory / 'manifest.json'
    record = json.loads(manifest.read_bytes()) if manifest.exists() else {}
    if record.get('assistance') != region_skill.SELECTIVE:
        return None
    raw, identity = region_skill.material(region_skill.SELECTIVE)
    region_skill.verify(directory, record, region_skill.SELECTIVE)
    text = raw.decode()
    first = [r for r in requests if r[0] == 1]
    catalog = bool(first and region_skill.initial_context(first[0][2],
                         (directory/'prompt.txt').read_text(), region_skill.SELECTIVE))
    reads = []
    for turn, call, number, delivered, reply in calls:
        matching = [a for a in actions if a['turn'] == turn and a['call_id'] == call.get('call_id')]
        completion = matching[0].get('command_completion') if len(matching) == 1 else None
        item = completion['item'] if completion else {}
        command = shell_command(item) if item else None
        try:
            words = shlex.split(command) if command else []
        except ValueError:
            words = []
        if words not in (['cat', region_skill.CONTAINER_PATH], ['/bin/cat', region_skill.CONTAINER_PATH]):
            continue
        executed = (item.get('exit_code') == 0 and item.get('aggregated_output') == text)
        received = bool(reply and any(v.get('exit_code') == 0 and v.get('output') == text
                                     for v in output_values(reply)))
        complete = bool(executed and received and turn in completed_turns and number in completed_turns)
        reads.append(dict(request_turn=turn, call_id=call.get('call_id'),
            execution_evidence=completion['evidence'], full_file_execution_observed=executed,
            body_delivery='complete' if complete else 'not_demonstrated',
            delivered_in=delivered if complete else None))
    return dict(format='region-skill-exposure-v1', identity=identity,
        actor='llm_builder' if record.get('mode') == 'subscription' else 'scripted_test_double',
        catalog_present=catalog,
        catalog_delivery='complete' if catalog and 1 in completed_turns else 'not_demonstrated',
        body_loading='observed' if any(r['body_delivery'] == 'complete' for r in reads) else 'not_demonstrated',
        reads=reads, application='not_inferred', scientific_score_effect='none',
        limitations=['Only a uniquely bound literal cat of the fixed path with exact full output is recognized.',
                    'A completed response is required for the read invocation and subsequent body delivery.',
                    'Other read variants, partial reads and missing evidence remain unresolved.',
                    'Exposure proves neither comprehension, correct use nor automatic selection in a scripted test.'])
