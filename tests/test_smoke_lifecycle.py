"""P4 isolation, resource and receipt controls; all processes are local doubles."""
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from builder import boundary_tool, run as launcher, smoke_tool, smoke_feedback
from builder.route import condition_prompt
from evaluator import run as exporter, smoke, transport
from evaluator.transport_input import accepted_export
from experiments import run as experiment
from prompts.prepare import prepare
from tests import test_transport as transport_doubles
from tests import test_isolated_builder as builder_doubles

XML = transport_doubles.XML


def read(path):
    return json.loads(path.read_bytes())


class SmokeProjection(unittest.TestCase):
    def test_profile_is_the_bounded_v7_contract(self):
        self.assertEqual(smoke.PROFILE, dict(id='candidate-smoke-v1', particles=1000,
            batches=8, inactive=2, generations_per_batch=1, seed=1, native_seconds=60,
            max_calls=2, minimum_session_seconds_to_start=180, max_xml_bytes=500000,
            log_bytes_per_stream=80000))

    def test_only_declared_fields_change_and_original_bytes_are_retained(self):
        xml = XML.replace(b'</settings>', b'<temperature_default>293.6</temperature_default>'
            b'<temperature_method>nearest</temperature_method><temperature_tolerance>1</temperature_tolerance>'
            b'<state_point><batches>10 20</batches></state_point>'
            b'<source_point><write>true</write><batches>20</batches></source_point></settings>')
        xml = xml.replace(b'<materials>', b'<materials><cross_sections>placeholder.xml</cross_sections>')
        before = ET.fromstring(xml)
        derived, changes = smoke.prepare_xml(xml, 'cross_sections.xml')
        after = ET.fromstring(derived)
        self.assertEqual([c['field'] for c in changes], [
            'settings/particles', 'settings/batches', 'settings/inactive',
            'settings/generations_per_batch', 'settings/seed', 'settings/state_point',
            'settings/source_point', 'materials/cross_sections'])
        expected = dict(particles='1000', batches='8', inactive='2',
                        generations_per_batch='1', seed='1')
        for tag, value in expected.items():
            self.assertEqual(after.findtext('settings/'+tag), value)
        self.assertEqual(after.findtext('settings/state_point/batches'), '8')
        self.assertEqual(after.findtext('settings/source_point/write'), 'false')
        self.assertEqual(after.findtext('materials/cross_sections'), '/data/cross_sections.xml')
        # Remove only the eight declared overrides; all physical XML is identical.
        for tree in (before, after):
            for change in changes:
                parent, tag = change['field'].split('/')
                for child in list(tree.find(parent)):
                    if child.tag == tag:
                        tree.find(parent).remove(child)
        self.assertEqual(ET.tostring(before), ET.tostring(after))
        with tempfile.TemporaryDirectory() as tmp, patch.object(
                transport, 'smoke_xml', return_value=dict(status='calculated_unreviewed',
                cleanup_confirmed=True, statepoint_validation='passed')) as execute:
            output = Path(tmp)/'smoke'
            reply = smoke.execute(xml, output, index=Path(tmp)/'cross_sections.xml')
            self.assertEqual((output/'working.xml').read_bytes(), xml)
            self.assertEqual((output/'smoke.xml').read_bytes(), derived)
            binding = read(output/'input.json')
            self.assertEqual(binding['working_xml_sha256'], exporter.digest(xml))
            self.assertEqual(binding['model_xml_sha256'], exporter.digest(derived))
            self.assertEqual(binding['overrides'], changes)
            self.assertFalse(binding['independent_final_export'])
            self.assertIsNone(binding['candidate_sha256'])
            self.assertEqual(execute.call_args.kwargs['wall_seconds'], 60)
            self.assertFalse(reply['scoring'] or reply['reference_access'] or reply['automatic_repair'])
            with self.assertRaises(FileExistsError):
                smoke.execute(xml, output, index=Path(tmp)/'cross_sections.xml')
            self.assertEqual(execute.call_count, 1)

    def test_public_process_outcomes_and_log_hashes_are_bounded_not_grades(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/'transport').mkdir()
            exporter.write_json(folder/'input.json', dict(working_xml_sha256='working',
                model_xml_sha256='diagnostic', overrides=[]))
            raw = b'HEAD'+b'x'*100000+b'TAIL'
            (folder/'transport/openmc-stderr.txt').write_bytes(raw)
            for process, expected in ((None, 'not_started'),
                    (dict(exit_code=0, stop_reason=None), 'completed'),
                    (dict(exit_code=7, stop_reason=None), 'failed'),
                    (dict(exit_code=-9, stop_reason='timeout'), 'interrupted')):
                path = folder/'transport/openmc-process.json'
                if process is None:
                    path.unlink(missing_ok=True)
                else:
                    exporter.write_json(path, process)
                result = smoke.public_result(folder, dict(status='failed', cleanup_confirmed=True,
                    error='/host/private/not-for-feedback', keff={'mean':1.0,'std_dev':0.1}))
                self.assertEqual(result['native_outcome'], expected)
                self.assertEqual(result['status'], 'incomplete')
                self.assertEqual(result['task_conformity'], 'not_evaluated')
                self.assertNotIn('keff', result)
                self.assertNotIn('/host/private', json.dumps(result))
                log = result['logs']['openmc_stderr']
                self.assertEqual(log['bytes'], len(raw))
                self.assertEqual(log['sha256'], exporter.digest(raw))
                self.assertFalse(log['complete'])
                self.assertTrue(log['text'].startswith('HEAD') and log['text'].endswith('TAIL'))
                self.assertEqual(len(log['text'].encode()), 80000+len(b'\n[omitted middle]\n'))

    def test_oversized_full_stream_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); (folder/'transport').mkdir()
            exporter.write_json(folder/'input.json', {})
            (folder/'transport/openmc-stdout.txt').write_bytes(b'x'*4_000_001)
            with self.assertRaisesRegex(ValueError, 'byte limit'):
                smoke.public_result(folder, {})

    def test_unusual_feedback_metadata_signals_incomplete_presentation(self):
        reply = dict(status='incomplete', native_outcome='failed', logs={},
                     limitations=['x'*40000])
        value = smoke_feedback.compact(reply)
        self.assertLessEqual(len(smoke_feedback.encode(value)), 16000)
        self.assertFalse(value['feedback_complete'])
        self.assertEqual(value['native_outcome'], 'failed')
        self.assertEqual(value['full_result']['sha256'], exporter.digest(smoke_feedback.encode(reply)))


class SmokeTransportLifecycle(unittest.TestCase):
    def setUp(self):
        self.fixture = transport_doubles.TransportLifecycleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.xml, _ = smoke.prepare_xml(XML, 'cross_sections.xml')
        # Reuse public synthetic worker/statepoint fixtures with explicit smoke sampling.
        self.enterContext(patch.object(transport_doubles, 'XML', self.xml))
        self.enterContext(patch.object(transport_doubles, 'SAMPLING',
            dict(particles=1000,batches=8,inactive=2,generations_per_batch=1,seed=1)))
        self.fixture.artifacts = transport_doubles.result_artifacts()
        statepoint = self.fixture.artifacts.pop('statepoint.20.h5')
        self.fixture.artifacts['statepoint.8.h5'] = statepoint
        calculation = json.loads(self.fixture.artifacts['calculation.json'])
        calculation['statepoint']['name'] = 'statepoint.8.h5'
        self.fixture.artifacts['calculation.json'] = json.dumps(calculation).encode()
        self.output = self.fixture.root/'smoke'

    def execute(self):
        with patch.object(transport, 'accepted_export', side_effect=AssertionError('No final export')):
            return smoke.execute(XML, self.output, index=self.fixture.index)

    def test_smoke_reuses_containment_and_separates_final_transport_receipts(self):
        with patch.object(exporter, 'bounded', side_effect=self.fixture.bounded) as process:
            reply = self.execute()
        self.assertEqual(reply['status'], 'completed')
        self.assertEqual(reply['native_outcome'], 'completed')
        self.assertEqual(reply['task_conformity'], 'not_evaluated')
        receipt = read(self.output/'transport/manifest.json')
        self.assertEqual(receipt['format'], 'candidate-smoke-transport-v1')
        self.assertIsNone(receipt['candidate_sha256'])
        self.assertEqual(receipt['threads'], 1)
        self.assertFalse(receipt['candidate_python_access'] or receipt['reference_access'])
        self.assertEqual(read(self.output/'transport/export-provenance.json')['kind'],
                         'candidate-session-smoke-v1')
        calls = [c for c in process.call_args_list if c.args[0][-3:] == ['/opt/openmc/bin/openmc','-s','1']]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].kwargs['timeout'], 60)
        with self.assertRaisesRegex(ValueError, 'export delivery contract'):
            accepted_export(self.output/'transport')
        self.assertTrue(reply['cleanup_confirmed'])
        self.assertFalse(self.fixture.present or self.fixture.volume_present)

    def test_load_failure_never_starts_solver(self):
        self.fixture.failure = 'load'
        reply = self.execute()
        self.assertEqual(reply['native_outcome'], 'not_started')
        self.assertEqual(reply['cause'], 'xml-load_exit_nonzero')
        self.assertFalse(any(c[-1] == '1' for c in self.fixture.calls))

    def test_native_failure_never_extracts_and_is_not_scientific_attribution(self):
        self.fixture.failure = '1'
        reply = self.execute()
        self.assertEqual(reply['native_outcome'], 'failed')
        self.assertEqual(reply['status'], 'incomplete')
        self.assertFalse(any(c[-1] == 'extract' for c in self.fixture.calls))
        self.assertFalse(reply['scoring'])
        self.assertIn('A failed run does not by itself establish model-versus-infrastructure attribution.',
                      reply['limitations'])

    def test_timeout_removes_runtime_without_retry_or_live_artifact_collection(self):
        self.fixture.stop = '1'
        reply = self.execute()
        self.assertEqual(reply['native_outcome'], 'interrupted')
        self.assertTrue(reply['cleanup_confirmed'])
        self.assertFalse(any(c[:2] == ('docker','cp') for c in self.fixture.calls))
        self.assertEqual(sum(c[-1] == '1' for c in self.fixture.calls), 1)

    def test_output_limit_is_interruption_not_completion(self):
        self.fixture.stop, self.fixture.stop_reason = '1', 'output_limit'
        reply = self.execute()
        self.assertEqual(reply['cause'], 'openmc_output_limit')
        self.assertEqual(reply['native_outcome'], 'interrupted')
        self.assertTrue(reply['cleanup_confirmed'])

    def test_cleanup_uncertainty_prevents_completed_smoke(self):
        with patch.object(exporter, 'cleanup', side_effect=RuntimeError('synthetic unavailable')):
            reply = self.execute()
        self.assertEqual(reply['status'], 'incomplete')
        self.assertFalse(reply['cleanup_confirmed'])

    def test_changed_data_cannot_qualify(self):
        self.fixture.identity.side_effect = [{'synthetic': True}, {'synthetic': False}]
        reply = self.execute()
        self.assertEqual(reply['status'], 'incomplete')
        self.assertEqual(reply['cause'], 'nuclear_data_changed_during_run')

    def test_tampered_statepoint_is_incomplete_despite_native_exit_zero(self):
        self.fixture.artifacts['statepoint.8.h5'] += b'tampered'
        reply = self.execute()
        self.assertEqual(reply['native_outcome'], 'completed')
        self.assertEqual(reply['status'], 'incomplete')
        self.assertTrue(reply['cleanup_confirmed'])

    def test_stale_worker_blocks_before_staging(self):
        self.fixture.worker_mismatch = True
        reply = self.execute()
        self.assertEqual(reply['native_outcome'], 'not_started')
        self.assertFalse(any('-i' in c for c in self.fixture.calls))

    def test_writable_data_is_rejected_before_execution(self):
        self.fixture.writable_data = True
        reply = self.execute()
        self.assertEqual(reply['native_outcome'], 'not_started')
        self.assertFalse(any(c[-1] == 'load' for c in self.fixture.calls))


class SmokeAdmissionAndBridge(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)

    def session(self, name='tool'):
        return smoke_tool.Session(self.root/name, dict(container_id='synthetic'), self.root/'index.xml')

    def test_xml_byte_cap_and_invalid_requests_never_dispatch(self):
        for number, request in enumerate(({}, {'tool':'other','xml':XML.decode()},
                {'tool':'smoke_openmc','xml':''}, {'tool':'smoke_openmc','xml':'x'*500001},
                {'tool':'smoke_openmc','xml':XML.decode(),'path':'candidate.py'})):
            with patch.object(smoke, 'execute', side_effect=AssertionError('No dispatch')) as execute:
                reply = self.session(str(number)).invoke(request, remaining_seconds=600)
            self.assertEqual(reply['status'], 'not_started')
            execute.assert_not_called()

    def test_two_attempts_then_refusal_and_native_attempts_are_distinct(self):
        tool = self.session()
        def execute(xml, output, *, index):
            output.mkdir(parents=True)
            (output/'transport').mkdir()
            exporter.write_json(output/'transport/openmc-process.json',dict(exit_code=7,stop_reason=None))
            return dict(status='incomplete',native_outcome='failed',cleanup_confirmed=True)
        with patch.object(smoke, 'execute', side_effect=execute) as dispatch:
            for _ in range(2):
                tool.invoke(dict(tool='smoke_openmc',xml=XML.decode()),remaining_seconds=180)
            third = tool.invoke({},remaining_seconds=600)
            with self.assertRaises(ValueError):
                tool.invoke({},remaining_seconds=600)
        self.assertEqual(dispatch.call_count, 2)
        self.assertEqual(third['cause'], 'tool_call_budget_exhausted')
        self.assertEqual(read(tool.output/'usage.json'),
                         dict(attempted_calls=3,maximum_calls=2,native_attempts=2))

    def test_refusal_at_179_seconds_is_retained_and_consumes_one_attempt(self):
        tool = self.session()
        with patch.object(smoke, 'execute') as dispatch:
            reply = tool.invoke(dict(tool='smoke_openmc',xml=XML.decode()),remaining_seconds=179)
        dispatch.assert_not_called()
        self.assertEqual(reply['cause'], 'insufficient_remaining_session_budget')
        self.assertEqual(read(tool.output/'usage.json')['attempted_calls'], 1)
        self.assertEqual(read(tool.output/'usage.json')['native_attempts'], 0)
        self.assertEqual(read(tool.output/'call-01/response.json'), reply)

    def test_invalid_xml_is_retained_without_transport_and_no_grade(self):
        tool = self.session()
        with patch.object(transport, 'smoke_xml', side_effect=AssertionError('No transport')) as native:
            reply = tool.invoke(dict(tool='smoke_openmc',xml='<not_model/>'),remaining_seconds=600)
        native.assert_not_called()
        self.assertEqual(reply['cause'], 'smoke_input_not_admitted')
        self.assertFalse(reply['scoring'])
        self.assertEqual((tool.output/'call-01/execution/working.xml').read_bytes(), b'<not_model/>')

    def test_bridge_sequence_and_cleanup_failure_stop_without_retry(self):
        adapter = smoke_tool.AttachedSession.__new__(smoke_tool.AttachedSession)
        adapter.session = self.session()
        adapter.process = types.SimpleNamespace(stdin=io.BytesIO())
        for frame in ({}, dict(id=2,request={}), dict(id=1,request={},extra=True)):
            with self.assertRaises(ValueError):
                adapter.handle(frame, 600)
        self.assertEqual(adapter.session.calls, 0)
        with patch.object(smoke,'execute',side_effect=OSError('synthetic host failure')) as dispatch:
            with self.assertRaisesRegex(RuntimeError,'cleanup uncertain'):
                adapter.handle(dict(id=1,request=dict(tool='smoke_openmc',xml=XML.decode())),600)
        self.assertEqual(dispatch.call_count,1)
        self.assertFalse(adapter.session.cleanup_confirmed)
        written = json.loads(adapter.process.stdin.getvalue())
        self.assertEqual(written['response']['cause'],'smoke_controller_failure')
        self.assertNotIn('synthetic host failure',json.dumps(written))

    def test_oversized_bridge_response_stops_before_forwarding(self):
        adapter = smoke_tool.AttachedSession.__new__(smoke_tool.AttachedSession)
        adapter.session = self.session()
        adapter.process = types.SimpleNamespace(stdin=io.BytesIO())
        with patch.object(adapter.session, 'invoke', return_value={'logs': 'x'*1_800_001}):
            with self.assertRaisesRegex(ValueError, 'response byte limit'):
                adapter.handle(dict(id=1,request={}),600)
        self.assertEqual(adapter.process.stdin.getvalue(), b'')

    def test_attach_rejects_wrong_owner_or_mounts_before_staging(self):
        for change in ('owner','stopped','mount'):
            info=builder_doubles.container()
            info.update(Id='owner',Image=launcher.IMAGE,State=dict(Running=True))
            if change=='owner':info['Id']='different'
            if change=='stopped':info['State']['Running']=False
            if change=='mount':info['Mounts']=[dict(Source='/synthetic/private')]
            with patch.object(launcher,'docker',return_value=json.dumps([info])), \
                 patch.object(smoke_tool,'bounded') as stage, patch.object(smoke_tool.subprocess,'Popen') as process:
                with self.assertRaises(ValueError):
                    smoke_tool.AttachedSession('owner',self.root/change,Mock(),self.root/'index.xml')
                stage.assert_not_called();process.assert_not_called()


class SmokeRouting(unittest.TestCase):
    def test_preexisting_condition_prompts_remain_byte_identical(self):
        # Recorded from merged public P3 main, before any P4 edits.
        expected = {
            'generic': '05c84d9c253c4f574a3a6e6b4cc155eb4d2b036fc4235b3b175041a23fe03075',
            'boundaries': '15efe721919352c448681bb87275c487ba93fb4a1c79417153a3340c07acc3fd',
            'guided_construction': 'b08b071a713e8719a9c053059ab9d6c2da8033398b3784855be30bf234329928',
            'guided_boundaries': 'cbceb91827338b5d606c6c57ab7809c184fb1e887ac3debdd3415be63ff7791b'}
        for condition, sha in expected.items():
            self.assertEqual(exporter.digest(condition_prompt('PUBLIC_TASK', condition).encode()), sha)

    def test_only_c_can_declare_data_and_preparation_never_dispatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);index=root/'cross_sections.xml';index.write_text('<cross_sections/>')
            with patch.object(experiment.agent,'run',side_effect=AssertionError('No authoring')), \
                 patch.object(transport,'smoke_xml',side_effect=AssertionError('No native transport')):
                for mode in ('generic','boundaries','guided_construction','guided_boundaries'):
                    with self.assertRaises(ValueError):
                        experiment.prepare(root/mode,assistance=mode,smoke_data_index=index)
                with self.assertRaises(ValueError):
                    experiment.prepare(root/'missing',assistance='guided_boundaries_smoke')
                with patch.object(exporter,'data_directory',return_value=(index,{})):
                    plan=experiment.prepare(root/'C',assistance='guided_boundaries_smoke',smoke_data_index=index)
            self.assertEqual(plan['budgets']['model_requests'],8)
            self.assertEqual(plan['budgets']['authoring_seconds'],600)
            self.assertEqual(plan['budgets']['automatic_retries'],0)
            self.assertEqual(plan['smoke']['data_index_sha256'],exporter.digest(index.read_bytes()))

    def test_changed_data_adapter_policy_or_budgets_stop_before_authoring(self):
        for change in ('data','adapter','policy','budget'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);index=root/'cross_sections.xml';index.write_text('<cross_sections/>')
                folder=root/'C'
                with patch.object(exporter,'data_directory',return_value=(index,{})):
                    plan=experiment.prepare(folder,assistance='guided_boundaries_smoke',smoke_data_index=index)
                if change=='data':index.write_text('<changed/>')
                if change=='adapter':plan['smoke']['adapter']['version']='changed'
                if change=='policy':plan['authoring_prompt_sha256']['reflective_pin_cell']='changed'
                if change=='budget':plan['budgets']['model_requests']=16
                exporter.write_json(folder/'plan.json',plan)
                with patch.object(experiment.agent,'run') as dispatch, self.assertRaises(ValueError):
                    experiment.execute(folder)
                dispatch.assert_not_called()
                self.assertFalse((folder/'runs').exists())

    def test_undeclared_smoke_in_a_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'A'
            plan=experiment.prepare(folder,assistance='guided_construction')
            plan['smoke']={}
            exporter.write_json(folder/'plan.json',plan)
            with patch.object(experiment.agent,'run') as dispatch, self.assertRaises(ValueError):
                experiment.execute(folder)
            dispatch.assert_not_called()


class SmokeBuilderLifecycle(unittest.TestCase):
    def setUp(self):
        self.fixture=builder_doubles.BuilderDouble()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.output.parent
        self.prepared=self.root/'input'
        prepare('reflective_pin_cell',self.prepared)
        self.index=self.root/'cross_sections.xml';self.index.write_text('<cross_sections/>')

    def run_builder(self, assistance='guided_boundaries_smoke', event=None, cleanup=True):
        prompt=condition_prompt((self.prepared/'prompt.txt').read_text(),assistance)
        body=builder_doubles.request()
        body['input'][-1]['content'][0]['text']=prompt
        process=self.fixture.fake_process(body=body)
        frames=[json.loads(line) for line in process.stdout.getvalue().splitlines()]
        if event is not None:frames.insert(2,event)
        process.stdout=io.BytesIO(b''.join(json.dumps(f).encode()+b'\n' for f in frames))
        self.adapter=Mock()
        self.adapter.session.cleanup_confirmed=cleanup
        kwargs=dict(smoke_data_index=self.index) if assistance=='guided_boundaries_smoke' else {}
        with patch.object(launcher.subprocess,'Popen',return_value=process), \
             patch.object(exporter,'data_directory',return_value=(self.index,{})), \
             patch.object(boundary_tool,'AttachedSession') as boundary, \
             patch.object(smoke_tool,'AttachedSession',return_value=self.adapter) as attach, \
             patch.object(launcher,'forward',side_effect=AssertionError('No provider call')):
            result=launcher.run(self.fixture.output,case='reflective_pin_cell',prepared_input=self.prepared,
                model='test-model',assistance=assistance,mode='mock',responder=lambda n,b:b'synthetic',**kwargs)
        self.boundary,self.attach=boundary,attach
        return result

    def test_c_attaches_both_tools_and_routes_smoke_within_session(self):
        result=self.run_builder(event=dict(type='smoke_tool_request',frame=dict(id=1,request={})))
        self.assertEqual(result['status'],'completed')
        self.assertTrue(result['cleanup_confirmed'])
        self.attach.assert_called_once()
        self.boundary.assert_called_once()
        self.adapter.handle.assert_called_once()
        self.assertLessEqual(self.adapter.handle.call_args.args[1],600)
        self.adapter.close.assert_called_once()
        manifest=read(self.fixture.output/'manifest.json')
        self.assertEqual(manifest['max_requests'],8)
        self.assertEqual(manifest['wall_seconds'],600)
        self.assertEqual(manifest['smoke_data_index_sha256'],exporter.digest(self.index.read_bytes()))
        self.assertFalse(self.fixture.present)

    def test_a_cannot_dispatch_smoke(self):
        result=self.run_builder('guided_construction',dict(type='smoke_tool_request',frame={}))
        self.assertEqual(result['status'],'failed')
        self.assertIn('Undeclared',result['error'])
        self.attach.assert_not_called()
        self.adapter.handle.assert_not_called()

    def test_smoke_bridge_error_stops_builder_and_closes_both_tools(self):
        result=self.run_builder(event=dict(type='smoke_tool_error'))
        self.assertEqual(result['status'],'failed')
        self.adapter.close.assert_called_once()
        self.boundary.return_value.close.assert_called_once()
        self.assertFalse(self.fixture.present)

    def test_nested_cleanup_uncertainty_prevents_later_experiment_session(self):
        result=self.run_builder(cleanup=False)
        self.assertFalse(result['cleanup_confirmed'])
        folder=self.root/'experiment'
        with patch.object(exporter,'data_directory',return_value=(self.index,{})):
            experiment.prepare(folder,assistance='guided_boundaries_smoke',smoke_data_index=self.index)
        with patch.object(experiment.agent,'run',return_value=dict(status='failed',cleanup_confirmed=False)) as dispatch:
            with self.assertRaisesRegex(RuntimeError,'later sessions not launched'):
                experiment.execute(folder,responder=lambda n,b:b'synthetic')
        self.assertEqual(dispatch.call_count,1)

    def test_builder_limits_reject_16_requests_before_any_process(self):
        with patch.object(launcher.subprocess,'Popen') as process, self.assertRaises(ValueError):
            launcher.run(self.fixture.output,case='reflective_pin_cell',prepared_input=self.prepared,
                assistance='guided_boundaries_smoke',max_requests=16,smoke_data_index=self.index,
                mode='mock',responder=lambda n,b:b'synthetic')
        process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
