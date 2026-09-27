"""Portable P6 controls. All request/stream/tool records below are synthetic."""
import copy
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

from builder import trajectory, trajectory_public, smoke_feedback
from builder.context import sha256


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value)+'\n')


def call(identifier='synthetic-call', command='python3 /work/smoke_openmc.py model.xml'):
    return dict(type='custom_tool_call', call_id=identifier, name='synthetic_tools',
                input='await tools.exec_command('+json.dumps(dict(cmd=command))+')')


def output(invocation, value):
    return dict(type=invocation['type']+'_output', call_id=invocation['call_id'],
                output=[dict(type='input_text', text=json.dumps(value))])


class Trace(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.folder=Path(tmp.name)
        self.result=dict(request_count=2, elapsed_seconds=12.5, status='completed', cleanup_confirmed=True)
        self.invocation=call()
        self.request(1, [])
        self.response(1, [self.invocation])
        self.smoke()
        self.events([dict(type='request',id=1),
                     dict(type='smoke_tool_request',frame=dict(id=1))])
        self.request(2, [self.invocation, output(self.invocation,self.feedback)])
        # Any accidental dispatch is a failure, not a health probe.
        self.tripwires=[]
        for target in ('builder.relay.forward', 'builder.run.run', 'subprocess.Popen'):
            guard=patch(target, side_effect=AssertionError('No live execution'))
            self.tripwires.append(guard.start()); self.addCleanup(guard.stop)

    def tearDown(self):
        for guard in self.tripwires:
            guard.assert_not_called()

    def request(self, turn, items):
        write(self.folder/f'request-{turn:02d}.json',dict(input=items))

    def response(self, turn, items, usage=None, duplicate_terminal=False):
        events=[dict(type='response.output_item.done',item=i) for i in items]
        terminal=dict(type='response.completed',response=dict(output=[],usage=usage or {}))
        events.append(terminal)
        if duplicate_terminal: events.append(terminal)
        (self.folder/f'response-{turn:02d}.sse').write_text(
            ''.join('data: '+json.dumps(e)+'\n\n' for e in events))

    def events(self, values):
        (self.folder/'events.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in values))

    def smoke(self, number=1, *, status='completed', native='completed', reference=None):
        folder=self.folder/f'smoke-tool/call-{number:02d}'
        reply=dict(format='candidate-smoke-result-v1',status=status,native_outcome=native,
            evidence_reference=reference or f'smoke-run:synthetic-session:{number}',
            working_xml_sha256='a'*64,smoke_xml_sha256='b'*64,logs={},processes={},
            cause=None,cleanup_confirmed=True)
        write(folder/'request.json',dict(model_xml='SYNTHETIC XML'))
        write(folder/'response.json',reply)
        self.feedback=smoke_feedback.compact(reply)
        write(folder/'feedback.json',self.feedback)
        write(self.folder/'smoke-tool/usage.json',dict(attempted_calls=number))
        return reply

    def summary(self):
        return trajectory.summarize(self.folder,self.result)

    def smoke_record(self):
        return self.summary()['smoke_calls'][0]


class SmokeDelivery(Trace):
    def test_native_completion_and_exact_delivery_are_separate_fields(self):
        row=self.smoke_record()
        self.assertEqual(row['native_outcome'],'completed')
        self.assertEqual(row['feedback_delivery'],dict(status='complete',request='request-02.json',
            turn=2,call_id='synthetic-call',cause=None))
        self.assertEqual(row['request_turn'],1)
        self.assertEqual(row['interpretation'],'not_inferred')
        self.assertEqual(row['scientific_score_effect'],'none')

    def test_completion_without_a_later_request_is_not_delivery(self):
        (self.folder/'request-02.json').unlink()
        row=self.smoke_record()
        self.assertEqual(row['native_outcome'],'completed')
        self.assertEqual(row['feedback_delivery']['status'],'not_demonstrated')
        self.assertIsNone(row['feedback_delivery']['request'])
        self.assertEqual(row['subsequent_actions'],[])

    def test_call_id_name_arguments_and_kind_must_match(self):
        for field,value in [('call_id','unrelated'),('name','another-tool'),
                            ('input','changed command'),('type','function_call')]:
            with self.subTest(field=field):
                changed=copy.deepcopy(self.invocation); changed[field]=value
                self.request(2,[changed,output(changed,self.feedback)])
                self.assertEqual(self.smoke_record()['feedback_delivery']['status'],'not_demonstrated')
        self.request(2,[output(self.invocation,self.feedback)])
        self.assertEqual(self.smoke_record()['feedback_delivery']['status'],'not_demonstrated')

    def test_reply_under_wrong_call_id_or_wrong_output_kind_is_not_delivery(self):
        for field,value in [('call_id','unrelated'),('type','function_call_output')]:
            reply=output(self.invocation,self.feedback);reply[field]=value
            self.request(2,[self.invocation,reply])
            self.assertEqual(self.smoke_record()['feedback_delivery']['status'],'not_demonstrated')

    def test_delayed_write_stdin_output_is_bound_to_its_actual_call(self):
        self.request(2,[self.invocation,output(self.invocation,dict(session_id=123))])
        poll=call('synthetic-poll');poll['input']='await tools.write_stdin({"session_id":123})'
        self.response(2,[poll])
        self.request(3,[poll,output(poll,self.feedback)])
        self.response(3,[call('later-action','echo followup')])
        self.result['request_count']=3
        row=self.smoke_record()
        self.assertEqual(row['feedback_delivery']['call_id'],'synthetic-poll')
        self.assertEqual(row['feedback_delivery']['request'],'request-03.json')
        self.assertEqual([a['turn'] for a in row['subsequent_actions']],[3])
        self.assertEqual([a['turn'] for a in row['subsequent_responses']],[3])
        self.assertEqual(row['interpretation'],'not_inferred')

    def test_repeated_history_is_one_delivery_at_its_first_request(self):
        self.request(3,[self.invocation,output(self.invocation,self.feedback)])
        self.result['request_count']=3
        self.assertEqual(self.smoke_record()['feedback_delivery']['request'],'request-02.json')

    def test_duplicate_invocation_or_reply_is_ambiguous(self):
        for history in ([self.invocation,self.invocation,output(self.invocation,self.feedback)],
                        [self.invocation,output(self.invocation,self.feedback),output(self.invocation,self.feedback)]):
            self.request(2,history)
            self.assertEqual(self.smoke_record()['feedback_delivery']['status'],'not_demonstrated')

    def test_duplicate_feedback_across_distinct_calls_is_ambiguous(self):
        second=call('second')
        self.response(1,[self.invocation,second])
        self.request(2,[self.invocation,output(self.invocation,self.feedback),second,output(second,self.feedback)])
        delivery=self.smoke_record()['feedback_delivery']
        self.assertEqual(delivery['status'],'not_demonstrated')
        self.assertEqual(delivery['cause'],'ambiguous_feedback_delivery')

    def test_truncated_duplicate_or_modified_feedback_never_proves_complete_delivery(self):
        cases=['Warning: truncated output\n'+json.dumps(self.feedback),
               json.dumps(self.feedback)+'\n'+json.dumps(self.feedback),
               json.dumps(dict(self.feedback,status='changed')),
               json.dumps(dict(self.feedback,feedback_complete=1)),
               json.dumps(self.feedback)[:-12]]
        for text in cases:
            reply=output(self.invocation,self.feedback);reply['output'][0]['text']=text
            self.request(2,[self.invocation,reply])
            self.assertEqual(self.smoke_record()['feedback_delivery']['status'],'not_demonstrated')

    def test_matching_incomplete_presentation_is_distinct_from_complete_delivery(self):
        expected=dict(format=smoke_feedback.VERSION,feedback_complete=False,
            presentation_cause='feedback_byte_limit',full_result=self.feedback['full_result'])
        write(self.folder/'smoke-tool/call-01/feedback.json',expected)
        self.request(2,[self.invocation,output(self.invocation,expected)])
        delivery=self.smoke_record()['feedback_delivery']
        self.assertEqual(delivery['status'],'incomplete_presentation')
        self.assertEqual(delivery['request'],'request-02.json')
        self.assertEqual(self.summary()['effort']['smoke_feedback_deliveries_observed'],0)

    def test_feedback_cannot_belong_to_a_different_or_duplicate_smoke_reference(self):
        reply_path=self.folder/'smoke-tool/call-01/response.json'
        reply=json.loads(reply_path.read_bytes());reply['evidence_reference']='wrong-reference'
        write(reply_path,reply)
        self.assertEqual(self.smoke_record()['feedback_delivery']['cause'],'feedback_reference_not_unique_or_unbound')
        self.smoke()
        self.smoke(2,reference='smoke-run:synthetic-session:1')
        self.events([dict(type='request',id=1),dict(type='smoke_tool_request',frame=dict(id=1)),
                     dict(type='smoke_tool_request',frame=dict(id=2))])
        self.assertTrue(all(r['feedback_delivery']['status']=='not_demonstrated' for r in self.summary()['smoke_calls']))

    def test_missing_or_duplicate_runtime_binding_does_not_infer_delivery(self):
        (self.folder/'events.jsonl').unlink()
        self.assertEqual(self.smoke_record()['feedback_delivery']['cause'],'smoke_call_binding_unavailable')
        self.events([dict(type='request',id=1),dict(type='smoke_tool_request',frame=dict(id=1)),
                     dict(type='smoke_tool_request',frame=dict(id=1))])
        self.assertIsNone(self.smoke_record()['request_turn'])
        self.assertEqual(self.smoke_record()['feedback_delivery']['status'],'not_demonstrated')

    def test_missing_feedback_preserves_completion_but_not_delivery(self):
        (self.folder/'smoke-tool/call-01/feedback.json').unlink()
        row=self.smoke_record()
        self.assertEqual(row['native_outcome'],'completed')
        self.assertEqual(row['feedback_delivery']['cause'],'missing_feedback')

    def test_missing_response_is_unknown_and_not_zero_native_completions(self):
        (self.folder/'smoke-tool/call-01/response.json').unlink()
        summary=self.summary();row=summary['smoke_calls'][0]
        self.assertEqual(row['status'],'missing_response')
        self.assertEqual(row['native_outcome'],'unknown')
        self.assertIsNone(summary['effort']['smoke_native_completions'])
        self.assertEqual(summary['effort']['smoke_native_completions_observed'],0)
        self.assertEqual(row['feedback_delivery']['status'],'not_demonstrated')

    def test_refusal_is_a_request_without_a_native_completion(self):
        self.smoke(status='not_started',native='not_started')
        self.request(2,[self.invocation,output(self.invocation,self.feedback)])
        summary=self.summary()
        self.assertEqual(summary['effort']['smoke_requests'],1)
        self.assertEqual(summary['effort']['smoke_native_completions'],0)
        self.assertEqual(summary['effort']['smoke_feedback_deliveries_observed'],1)

    def test_native_exit_completion_does_not_imply_completed_smoke_validation(self):
        self.smoke(status='incomplete',native='completed')
        self.request(2,[self.invocation,output(self.invocation,self.feedback)])
        row=self.smoke_record()
        self.assertEqual((row['status'],row['native_outcome']),('incomplete','completed'))
        self.assertEqual(row['scientific_score_effect'],'none')


class EffortCoverage(Trace):
    def test_absent_inventory_is_unknown_but_explicit_empty_usage_is_known_zero(self):
        import shutil
        shutil.rmtree(self.folder/'smoke-tool')
        missing=self.summary()
        self.assertIsNone(missing['effort']['smoke_requests'])
        self.assertIsNone(missing['effort']['smoke_native_completions'])
        self.assertEqual(missing['effort']['smoke_requests_observed'],0)
        self.events([dict(type='request',id=1)])
        write(self.folder/'smoke-tool/usage.json',dict(attempted_calls=0))
        known=self.summary()
        self.assertEqual(known['effort']['smoke_requests'],0)
        self.assertEqual(known['effort']['smoke_native_completions'],0)
        self.assertTrue(known['coverage']['smoke']['request_inventory_complete'])

    def test_runtime_call_prevents_stale_zero_usage_from_claiming_no_use(self):
        import shutil
        shutil.rmtree(self.folder/'smoke-tool')
        write(self.folder/'smoke-tool/usage.json',dict(attempted_calls=0))
        summary=self.summary()
        self.assertIsNone(summary['effort']['smoke_requests'])
        self.assertEqual(summary['coverage']['smoke']['runtime_requests'],1)

    def test_usage_mismatch_missing_request_and_noninteger_totals_stay_unknown(self):
        for count in (0,2,True,1.5,None):
            write(self.folder/'smoke-tool/usage.json',dict(attempted_calls=count))
            self.assertIsNone(self.summary()['effort']['smoke_requests'])
        write(self.folder/'smoke-tool/usage.json',dict(attempted_calls=0))
        (self.folder/'smoke-tool/call-01/request.json').unlink()
        self.assertIsNone(self.summary()['effort']['smoke_requests'])

    def test_available_token_sum_is_separate_from_completeness(self):
        usage=dict(input_tokens=10,output_tokens=2,total_tokens=12)
        self.response(1,[self.invocation],usage)
        summary=self.summary()
        self.assertEqual(summary['effort']['token_usage'],usage)
        self.assertEqual(summary['effort']['token_usage_response_count'],1)
        self.assertFalse(summary['effort']['token_usage_complete'])
        self.response(2,[],dict(input_tokens=0,output_tokens=0,total_tokens=0))
        summary=self.summary()
        self.assertEqual(summary['effort']['token_usage'],usage)
        self.assertTrue(summary['effort']['token_usage_complete'])

    def test_missing_usage_does_not_become_zero(self):
        self.assertIsNone(self.summary()['effort']['token_usage'])
        self.assertFalse(self.summary()['effort']['token_usage_complete'])
        for n in (1,2):
            self.response(n,[],dict(input_tokens=0,output_tokens=0,total_tokens=0))
        self.assertEqual(self.summary()['effort']['token_usage']['total_tokens'],0)
        self.assertTrue(self.summary()['effort']['token_usage_complete'])

    def test_matching_counts_with_gapped_or_missing_requests_do_not_establish_coverage(self):
        usage=dict(input_tokens=1,output_tokens=1,total_tokens=2)
        self.response(1,[],usage);self.response(3,[],usage)
        self.assertFalse(self.summary()['effort']['token_usage_complete'])
        (self.folder/'response-03.sse').rename(self.folder/'response-02.sse')
        (self.folder/'request-01.json').unlink()
        self.assertFalse(self.summary()['effort']['token_usage_complete'])

    def test_duplicate_terminal_negative_and_boolean_usage_are_unqualified(self):
        valid=dict(input_tokens=1,output_tokens=1,total_tokens=2)
        self.response(1,[],valid,duplicate_terminal=True)
        self.assertIsNone(self.summary()['effort']['token_usage'])
        for bad in (-1,True):
            self.response(1,[],dict(valid,input_tokens=bad))
            self.assertIsNone(self.summary()['effort']['token_usage'])

    def test_explicit_empty_session_has_zero_usage_but_unknown_count_does_not(self):
        for path in self.folder.glob('request-*.json'):path.unlink()
        for path in self.folder.glob('response-*.sse'):path.unlink()
        self.result['request_count']=0
        self.assertEqual(self.summary()['effort']['token_usage']['total_tokens'],0)
        self.assertTrue(self.summary()['effort']['token_usage_complete'])
        self.result['request_count']=None
        self.assertIsNone(self.summary()['effort']['token_usage'])
        self.assertFalse(self.summary()['effort']['token_usage_complete'])


class ExistingProjection(Trace):
    def test_done_items_are_deduplicated_when_terminal_output_is_empty(self):
        events=[dict(type='response.output_item.done',item=self.invocation)]*2
        events.append(dict(type='response.completed',response=dict(output=[])))
        self.assertEqual(trajectory.response_items(events),[self.invocation])
        events[-1]['response']['output']=[dict(type='message')]
        self.assertEqual(trajectory.response_items(events),[dict(type='message')])

    def test_structured_export_completion_is_separate_from_received_output(self):
        scratch=trajectory.CONSTRUCTION_POLICY.read_text().split('~~~sh\n'.replace('~',chr(96)),1)[1].split('\n~~~'.replace('~',chr(96)),1)[0]
        invocation=call(command=scratch);self.response(1,[invocation])
        self.request(2,[invocation,output(invocation,'')])
        self.events([dict(type='request',id=1),dict(type='stdout',text=json.dumps(dict(
            type='item.completed',item=dict(type='command_execution',
            command='/bin/bash -lc '+shlex.quote(scratch),exit_code=0,aggregated_output=''))))])
        result=self.summary()
        self.assertEqual(result['working_exports'][0]['outcome'],'completed')
        self.assertEqual(result['working_exports'][0]['execution_evidence'],'events.jsonl:2')
        self.assertIsNone(result['tool_actions'][0]['candidate_edit_requested'])

    def test_boundary_feedback_needs_runtime_binding_and_matching_call(self):
        boundary=self.folder/'boundary-tool/call-01'
        reply=dict(status='observed',artifact_sha256='c'*64,evidence_reference='synthetic-boundary')
        write(boundary/'request.json',{});write(boundary/'response.json',reply)
        write(boundary/'feedback.json',dict(reply,feedback_complete=True))
        self.request(2,[self.invocation,output(self.invocation,dict(reply,feedback_complete=True))])
        self.events([dict(type='request',id=1),dict(type='boundary_tool_request',frame=dict(id=1))])
        self.assertEqual(self.summary()['inspection_calls'][0]['feedback_delivery']['status'],'complete')
        (self.folder/'events.jsonl').unlink()
        row=self.summary()['inspection_calls'][0]
        self.assertTrue(row['completed'])
        self.assertEqual(row['feedback_delivery']['status'],'not_demonstrated')

    def test_projection_is_read_only_and_never_grades_physics(self):
        before={p.relative_to(self.folder):p.read_bytes() for p in self.folder.rglob('*') if p.is_file()}
        summary=self.summary();public=trajectory_public.public_view(summary)
        self.assertEqual(summary['format'],'codex-trajectory-v3')
        self.assertEqual(public['format'],'public-trajectory-v1')
        self.assertEqual(public['scientific_score_effect'],'none')
        self.assertEqual(before,{p.relative_to(self.folder):p.read_bytes() for p in self.folder.rglob('*') if p.is_file()})


class PublicProjection(Trace):
    def test_public_view_retains_bounded_identities_effort_and_delivery(self):
        summary=self.summary();view=trajectory_public.public_view(summary)
        self.assertEqual(view['smoke_calls'][0]['delivered_in'],'request-02.json')
        self.assertEqual(view['smoke_calls'][0]['call_id_sha256'],sha256(b'synthetic-call'))
        self.assertEqual(view['smoke_calls'][0]['working_xml_sha256'],'a'*64)
        self.assertEqual(view['effort']['smoke_requests'],1)
        self.assertFalse(view['effort']['token_usage_complete'])
        self.assertEqual(view['interpretation'],'not_inferred')
        self.assertEqual(view['evidence_status'],'descriptive_projection_not_verification')

    def test_allowlist_excludes_private_text_paths_commands_logs_and_errors(self):
        summary=self.summary();secret='SYNTHETIC_PRIVATE_CANARY'
        summary['session_outcome']['error']=secret
        summary['limits']=secret
        action=summary['tool_actions'][0]
        action.update(tool=secret,call_id=secret,evidence='../'+secret,
            output_delivered_in='/private/'+secret,
            command_completion=dict(item=dict(command=secret,aggregated_output=secret)),
            candidate_edit_events=[dict(path=secret)],input_sha256=secret,output_sha256=secret)
        smoke=summary['smoke_calls'][0]
        smoke.update(cause=secret,processes=dict(stderr=secret),status=secret,native_outcome=secret,
            evidence='../'+secret,working_xml_sha256=secret)
        smoke['feedback_delivery']['call_id']=secret
        summary['effort'].update(elapsed_seconds=secret,requests=secret)
        summary['effort']['token_usage']=dict(input_tokens=secret,output_tokens=0,total_tokens=secret,extra=secret)
        summary['coverage']['retained_requests']=secret
        view=trajectory_public.public_view(summary)
        self.assertNotIn(secret,json.dumps(view))
        self.assertNotIn('command_completion',view['tool_actions'][0])
        self.assertIsNone(view['tool_actions'][0]['evidence'])
        self.assertIsNone(view['effort']['requests'])

    def test_public_view_is_fresh_and_rejects_historical_summary_versions(self):
        summary=self.summary();before=copy.deepcopy(summary)
        view=trajectory_public.public_view(summary)
        view['smoke_calls'][0]['status']='modified'
        self.assertEqual(summary,before)
        summary['format']='codex-trajectory-v2'
        with self.assertRaisesRegex(ValueError,'historical'):
            trajectory_public.public_view(summary)


if __name__ == '__main__':
    unittest.main()
