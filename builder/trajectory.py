"""Factual Codex trace projection. Authoring evidence never grades final physics."""
import json
import re
import shlex
from pathlib import Path
from builder.context import sha256
from builder.relay import event_frame
from builder.route import CONSTRUCTION_POLICY

VERSION = 'codex-trajectory-v3'


def response_items(events):
    """Done items carry executed calls even when completed.output is empty."""
    done = [e['item'] for e in events if e.get('type') == 'response.output_item.done']
    terminal = [e['response'].get('output', []) for e in events if e.get('type') == 'response.completed']
    items = (terminal[-1] if terminal and terminal[-1] else done)
    unique = []
    for item in items:
        if item not in unique:
            unique.append(item)
    return unique


def runtime_items(directory):
    """Structured CLI completion events, scoped to the preceding request number."""
    path = directory/'events.jsonl'
    if not path.exists():
        return [], {}
    records, inspections, turn = [], {}, None
    for number, line in enumerate(path.read_text().splitlines(), 1):
        event = json.loads(line)
        if event.get('type') == 'request':
            turn = event['id']
        elif event.get('type') == 'boundary_tool_request':
            number = event['frame']['id']
            inspections[number] = turn if number not in inspections else None
        elif event.get('type') == 'stdout':
            try:
                record = json.loads(event['text'])
            except (ValueError, TypeError):
                continue
            if record.get('type') == 'item.completed':
                records.append(dict(turn=turn, evidence=f'events.jsonl:{number}', item=record['item']))
    return records, inspections


def shell_command(item):
    try:
        parts = shlex.split(item.get('command', ''))
    except ValueError:
        return None
    return parts[2] if len(parts)==3 and parts[1] in ('-lc', '-c') else None


def json_values(text):
    """Whole JSON values at line starts, including an execution result's stdout."""
    if not isinstance(text, str):
        return []
    values = []
    for line in re.finditer(r'(?m)^[ \t]*(?=[{\[])', text):
        try:
            value, _ = json.JSONDecoder().raw_decode(text[line.end():])
        except ValueError:
            continue
        if isinstance(value, dict):
            values.append(value)
            if isinstance(value.get('output'), str):
                values.extend(json_values(value['output']))
    return values


def output_values(item):
    output = item.get('output', [])
    parts = output if isinstance(output, list) else [dict(text=output)]
    return [v for p in parts if isinstance(p, dict) for v in json_values(p.get('text'))]


def complete_value(item, expected):
    output = item.get('output', [])
    parts = output if isinstance(output, list) else [dict(text=output)]
    if any(re.search(r'Warning: truncated output|…\d+ tokens truncated…', p.get('text', ''))
           for p in parts if isinstance(p, dict)):
        return False
    expected_json = json.dumps(expected, sort_keys=True)
    return sum(json.dumps(value, sort_keys=True) == expected_json
               for value in output_values(item)) == 1


def delivered_output(requests, turn, call):
    """Bind one output to one exact invocation in a subsequent request."""
    call_id = call.get('call_id')
    if not isinstance(call_id, str) or not call_id:
        return None, None, None
    for number, path, body in requests:
        if number <= turn:
            continue
        items = body.get('input', [])
        invocations = [(p, i) for p, i in enumerate(items)
                       if i.get('type') in ('custom_tool_call', 'function_call')
                       and i.get('call_id') == call_id]
        if not invocations:
            continue
        if len(invocations) != 1:
            return None, None, None
        position, item = invocations[0]
        if (item.get('type') != call.get('type') or item.get('name') != call.get('name')
                or item.get('input', item.get('arguments')) != call.get('input', call.get('arguments'))):
            return None, None, None
        replies = [i for i in items[position+1:]
                   if i.get('type') in ('custom_tool_call_output', 'function_call_output')
                   and i.get('call_id') == call_id]
        if len(replies) > 1:
            return None, None, None
        if replies:
            if replies[0].get('type') != call['type'] + '_output':
                return None, None, None
            return number, path.name, replies[0]
    return None, None, None


def summarize(directory, result):
    directory = Path(directory)
    requests = [(int(p.stem.split('-')[-1]), p, json.loads(p.read_bytes()))
                for p in sorted(directory.glob('request-*.json'))]
    scratch = CONSTRUCTION_POLICY.read_text().split('```sh\n', 1)[1].split('\n```', 1)[0]
    actions, exports, tokens, responses, calls = [], [], [], [], []
    token_turns = []
    runtime, inspection_turns = runtime_items(directory)
    limitations = ['Recognizes the literal documented scratch recipe and literal cmd strings only.',
        'Authoring execution outputs are descriptive; independent final assessment supplies scientific evidence.',
        'An edit request is not proof of a persisted revision. No understanding or intent is inferred.']
    for path in sorted(directory.glob('response-*.sse')):
        turn = int(path.stem.split('-')[-1])
        events = [event_frame(b) for b in path.read_text().replace('\r\n','\n').split('\n\n') if b.strip()]
        events = [e for e in events if isinstance(e, dict)]
        completed = [e['response'] for e in events if e.get('type') == 'response.completed']
        items = response_items(events)
        if len(completed) == 1:
            usage = completed[-1].get('usage', {})
            if all(type(usage.get(k)) is int and usage[k] >= 0 for k in ('input_tokens','output_tokens','total_tokens')):
                tokens.append(usage)
                token_turns.append(turn)
        responses.append(dict(turn=turn, evidence=path.name, output_types=[i.get('type') for i in items]))
        for call in items:
            if call.get('type') not in ('custom_tool_call', 'function_call'):
                continue
            code = call.get('input', call.get('arguments', ''))
            commands = [json.loads(m.group(1)) for m in re.finditer(r'(?:\bcmd\b|"cmd")\s*:\s*("(?:[^"\\]|\\.)*")', code)]
            number, delivered, reply = delivered_output(requests, turn, call)
            calls.append((turn, call, number, delivered, reply))
            values = output_values(reply) if reply else []
            outcomes = [v for v in values if 'exit_code' in v and 'output' in v]
            # Join actual command completion to the unique literal invocation in
            # this response. Ambiguous/multi-command wrappers remain unresolved.
            runtime_commands = [r for r in runtime if r['turn']==turn and
                r['item'].get('type')=='command_execution' and len(commands)==1 and
                shell_command(r['item'])==commands[0]]
            turn_calls = [i for i in items if i.get('type') in ('custom_tool_call','function_call')]
            bound = runtime_commands if len(turn_calls)==1 and len(runtime_commands)==1 else []
            edits = [r for r in runtime if r['turn']==turn and r['item'].get('type')=='file_change'
                     and any(c.get('path')=='/work/workspace/candidate.py' for c in r['item'].get('changes',[]))]
            action = dict(turn=turn, call_id=call.get('call_id'), tool=call.get('name'),
                evidence=path.name, input_sha256=sha256(code.encode()),
                literal_command_count=len(commands), command_sha256=[sha256(c.encode()) for c in commands],
                command_classification='literal' if commands else 'unclassified', output_delivered_in=delivered,
                output_sha256=sha256(json.dumps(reply,sort_keys=True).encode()) if reply else None,
                command_completion=bound[0] if bound else None,
                candidate_edit_requested=True if edits and len(turn_calls)==1 else None,
                candidate_edit_events=edits if len(turn_calls)==1 else [])
            actions.append(action)
            if any(scratch in c for c in commands):
                # Multiple execution outputs cannot be safely attributed to one command here.
                observed = [dict(exit_code=bound[0]['item'].get('exit_code'))] if bound else outcomes
                unambiguous = len(commands) == 1 and len(observed) == 1
                success = unambiguous and observed[0].get('exit_code') == 0
                failed = unambiguous and type(observed[0].get('exit_code')) is int and observed[0]['exit_code'] != 0
                exports.append(dict(turn=turn, evidence=path.name, call_id=call.get('call_id'),
                    outcome='completed' if success else 'command_failed' if failed else 'indeterminate',
                    execution_exit_codes=[v['exit_code'] for v in observed],
                    execution_evidence=bound[0]['evidence'] if bound else delivered,
                    output_delivered_in=delivered,
                    error_delivered_before_later_turn=bool(failed and number and (
                        any(v.get('exit_code')==observed[0]['exit_code'] for v in outcomes) or
                        bound and bound[0]['item'].get('aggregated_output') and
                        any(p.get('text')==bound[0]['item']['aggregated_output']
                            for p in reply.get('output', []) if isinstance(p, dict))))))
    inspections = []
    for request in sorted((directory/'boundary-tool').glob('call-*/request.json')):
        path = request.with_name('response.json')
        if not path.exists():
            inspections.append(dict(evidence=str(request.relative_to(directory)), requested=True,
                completed=False, status='indeterminate', cause='missing_inspection_response',
                complete_response_delivered_in=None, subsequent_tool_actions=[], subsequent_responses=[]))
            continue
        reply = json.loads(path.read_bytes())
        feedback_path = path.with_name('feedback.json')
        feedback = json.loads(feedback_path.read_bytes()) if feedback_path.exists() else reply
        inspection_turn = inspection_turns.get(int(request.parent.name.split('-')[-1]))
        eligible = [c for c in calls if inspection_turn is not None and c[0]==inspection_turn]
        matching = [c for c in eligible if c[4] and complete_value(c[4], feedback)]
        delivery = (matching[0][2], matching[0][3]) if len(matching)==1 else None
        delivery_cause = ('inspection_call_binding_unavailable' if inspection_turn is None else
                         'delivered_output_differs_from_feedback' if any(c[4] for c in eligible) else
                         'no_matching_subsequent_request')
        complete = bool(delivery and feedback.get('feedback_complete', True))
        later = [dict(turn=a['turn'], evidence=a['evidence'], tool=a['tool'],
                      candidate_edit_requested=a['candidate_edit_requested'])
                 for a in actions if delivery and a['turn'] >= delivery[0]]
        inspections.append(dict(evidence=str(path.relative_to(directory)), requested=True,
            completed=reply.get('status')=='observed', status=reply.get('status'), cause=reply.get('cause'),
            artifact_sha256=reply.get('artifact_sha256'), evidence_reference=reply.get('evidence_reference'),
            domain=(reply.get('observations') or {}).get('domain'),
            complete_response_delivered_in=delivery[1] if delivery and not feedback_path.exists() else None,
            complete_feedback_delivered_in=delivery[1] if complete else None,
            feedback_delivery=dict(format=feedback.get('format'),
                status='complete' if complete else 'incomplete_presentation' if delivery else 'not_demonstrated',
                delivered_in=delivery[1] if delivery else None,
                call_id=matching[0][1]['call_id'] if delivery else None,
                inspection_request_turn=inspection_turn,
                cause=feedback.get('presentation_cause') if delivery else delivery_cause),
            subsequent_tool_actions=later,
            subsequent_responses=[r for r in responses if delivery and r['turn'] >= delivery[0]],
            interpretation='not_inferred'))
    count = result.get('request_count')
    expected_turns = list(range(1, count+1)) if type(count) is int and count >= 0 else None
    request_inventory_complete = expected_turns is not None and [r[0] for r in requests] == expected_turns
    response_inventory_complete = expected_turns is not None and [r['turn'] for r in responses] == expected_turns
    token_complete = request_inventory_complete and response_inventory_complete and token_turns == expected_turns
    summary=dict(format=VERSION, working_exports=exports, inspection_calls=inspections, tool_actions=actions,
        working_export_attempt='observed' if exports else 'not_demonstrated',
        feedback_interpretation='not_inferred',
        workflow_evidence=dict(working_export_attempt='observed' if exports else 'not_demonstrated',
            successful_working_export='observed' if any(e['outcome']=='completed' for e in exports) else 'not_demonstrated',
            completed_inspection='observed' if any(i['completed'] for i in inspections) else 'not_demonstrated',
            complete_inspection_feedback='observed' if any(i['completed'] and i.get('complete_feedback_delivered_in') for i in inspections) else 'not_demonstrated',
            scientific_score_effect='none', scope='Observed steps only; unrecognized export variants require manual trace review'),
        final_source_sha256=sha256((directory/'candidate.py').read_bytes()) if (directory/'candidate.py').exists() else None,
        effort=dict(requests=count, elapsed_seconds=result.get('elapsed_seconds'),
            tool_calls_observed=len(actions), inspection_requests=len(inspections),
            inspections_completed=sum(i['completed'] for i in inspections),
            token_usage={k:sum(u[k] for u in tokens) for k in ('input_tokens','output_tokens','total_tokens')} if tokens or (count == 0 and token_complete) else None,
            token_usage_response_count=len(tokens), token_usage_complete=token_complete),
        session_outcome={k:result.get(k) for k in ('status','error_type','error','cleanup_confirmed')},
        coverage=dict(retained_requests=len(requests), retained_responses=len(responses),
            request_inventory_complete=request_inventory_complete, response_inventory_complete=response_inventory_complete),
        limitations=limitations)
    summary['smoke_calls'] = smoke_calls(directory, calls, actions, responses)
    smoke = summary['smoke_calls']
    usage_path = directory/'smoke-tool/usage.json'
    usage = json.loads(usage_path.read_bytes()) if usage_path.exists() else {}
    declared = usage.get('attempted_calls')
    event_path = directory/'events.jsonl'
    runtime_smoke_ids = None
    if event_path.exists():
        runtime_events = [json.loads(line) for line in event_path.read_text().splitlines()]
        runtime_smoke_ids = [e['frame']['id'] for e in runtime_events if e.get('type') == 'smoke_tool_request']
    inventory_complete = (type(declared) is int and declared >= 0 and
        [r['call_number'] for r in smoke] == list(range(1, declared+1)) and
        {p.name for p in (directory/'smoke-tool').glob('call-*')} ==
        {f'call-{n:02d}' for n in range(1, declared+1)} and
        (runtime_smoke_ids is None or runtime_smoke_ids == list(range(1, declared+1))))
    outcomes_complete = inventory_complete and all(r['native_outcome'] in
        ('completed', 'failed', 'interrupted', 'not_started') for r in smoke)
    observed_completions = sum(r['native_outcome'] == 'completed' for r in smoke)
    summary['coverage']['smoke'] = dict(retained_requests=len(smoke),
        declared_requests=declared if type(declared) is int and declared >= 0 else None,
        request_inventory_complete=inventory_complete, native_outcomes_complete=outcomes_complete,
        runtime_requests=len(runtime_smoke_ids) if runtime_smoke_ids is not None else None)
    summary['effort'].update(smoke_requests=len(smoke) if inventory_complete else None,
        smoke_requests_observed=len(smoke),
        smoke_native_completions=observed_completions if outcomes_complete else None,
        smoke_native_completions_observed=observed_completions,
        smoke_feedback_deliveries_observed=sum(r['feedback_delivery']['status']=='complete' for r in smoke))
    return summary


def smoke_calls(directory, calls, actions, responses):
    """Completion and exact subsequent-request delivery are independent facts."""
    turns, turn = {}, None
    events = directory/'events.jsonl'
    for line in events.read_text().splitlines() if events.exists() else []:
        event = json.loads(line)
        if event.get('type') == 'request':
            turn = event['id']
        if event.get('type') == 'smoke_tool_request':
            number = event['frame']['id']
            turns[number] = turn if number not in turns else None
    retained = []
    for path in sorted((directory/'smoke-tool').glob('call-*/request.json')):
        response, feedback = path.with_name('response.json'), path.with_name('feedback.json')
        reply = json.loads(response.read_bytes()) if response.exists() else {}
        expected = json.loads(feedback.read_bytes()) if feedback.exists() else None
        retained.append((path, reply, expected))
    references = [reply.get('evidence_reference') for _, reply, _ in retained]
    records = []
    for path, reply, expected in retained:
        number = int(path.parent.name.split('-')[-1]); started = turns.get(number)
        reference = reply.get('evidence_reference')
        feedback_reference = (expected.get('evidence_reference') or
            expected.get('full_result', {}).get('evidence_reference')) if expected else None
        bound = (isinstance(reference, str) and bool(reference) and
                 references.count(reference) == 1 and reference == feedback_reference)
        # A long command may return through a later write_stdin call. Calls have
        # already been joined to outputs by actual invocation and call ID.
        matching = [c for c in calls if started is not None and c[0] >= started and c[4]
                    and bound and complete_value(c[4], expected)]
        delivery = matching[0] if len(matching) == 1 else None
        complete = bool(delivery and expected.get('feedback_complete') is True)
        cause = ('missing_feedback' if expected is None else
                 'feedback_reference_not_unique_or_unbound' if not bound else
                 'smoke_call_binding_unavailable' if started is None else
                 'ambiguous_feedback_delivery' if len(matching) > 1 else
                 'no_exact_subsequent_output' if not delivery else
                 'incomplete_presentation' if not complete else None)
        records.append(dict(evidence=str(path.parent.relative_to(directory)), call_number=number,
            request_turn=started, requested=True,
            status=reply.get('status', 'missing_response'), native_outcome=reply.get('native_outcome', 'unknown'),
            working_xml_sha256=reply.get('working_xml_sha256'), smoke_xml_sha256=reply.get('smoke_xml_sha256'),
            processes=reply.get('processes', {}), cause=reply.get('cause'),
            feedback_delivery=dict(status='complete' if complete else
                'incomplete_presentation' if delivery else 'not_demonstrated',
                request=delivery[3] if delivery else None, turn=delivery[2] if delivery else None,
                call_id=delivery[1]['call_id'] if delivery else None, cause=cause),
            subsequent_actions=[a for a in actions if delivery and a['turn'] >= delivery[2]],
            subsequent_responses=[r for r in responses if delivery and r['turn'] >= delivery[2]],
            interpretation='not_inferred', scientific_score_effect='none'))
    return records
