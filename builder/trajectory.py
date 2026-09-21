"""Factual Codex trace projection. Authoring evidence never grades final physics."""
import json
import re
import shlex
from pathlib import Path
from builder.context import sha256
from builder.relay import event_frame
from builder.route import CONSTRUCTION_POLICY

VERSION = 'codex-trajectory-v2'


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
            inspections[event['frame']['id']] = turn
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
    return expected in output_values(item)


def delivered_output(requests, turn, call):
    """Bind a subsequent input's output to the actual matching tool invocation."""
    for number, path, body in requests:
        if number <= turn:
            continue
        items = body.get('input', [])
        for position in range(len(items)-1, -1, -1):
            item = items[position]
            if (item.get('type') == call.get('type') and item.get('call_id') == call.get('call_id')
                    and item.get('input', item.get('arguments')) == call.get('input', call.get('arguments'))):
                for reply in items[position+1:]:
                    if reply.get('type') in ('custom_tool_call', 'function_call') and reply.get('call_id') == call.get('call_id'):
                        break
                    if reply.get('type') in ('custom_tool_call_output', 'function_call_output') and reply.get('call_id') == call.get('call_id'):
                        return number, path.name, reply
    return None, None, None


def summarize(directory, result):
    directory = Path(directory)
    requests = [(int(p.stem.split('-')[-1]), p, json.loads(p.read_bytes()))
                for p in sorted(directory.glob('request-*.json'))]
    scratch = CONSTRUCTION_POLICY.read_text().split('```sh\n', 1)[1].split('\n```', 1)[0]
    actions, exports, tokens, responses, calls = [], [], [], [], []
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
        if completed:
            usage = completed[-1].get('usage', {})
            if all(type(usage.get(k)) is int for k in ('input_tokens','output_tokens','total_tokens')):
                tokens.append(usage)
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
        eligible = [c for c in calls if inspection_turn is None or c[0]==inspection_turn]
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
    return dict(format=VERSION, working_exports=exports, inspection_calls=inspections, tool_actions=actions,
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
            token_usage={k:sum(u[k] for u in tokens) for k in ('input_tokens','output_tokens','total_tokens')} if tokens else None,
            token_usage_response_count=len(tokens), token_usage_complete=count is not None and count==len(tokens)),
        session_outcome={k:result.get(k) for k in ('status','error_type','error','cleanup_confirmed')},
        coverage=dict(retained_requests=len(requests), retained_responses=len(list(directory.glob('response-*.sse')))),
        limitations=limitations)
