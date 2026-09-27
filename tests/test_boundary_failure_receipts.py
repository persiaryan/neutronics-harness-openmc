"""P3 receipt and adapter regressions; only synthetic, local execution doubles."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from builder import boundary_feedback, inspection_receipts
from evaluation.scientific import boundaries
from evaluator.evidence import InsufficientEvidence
from evaluator.run import digest, write_json
from tests.fixtures.boundary_receipts import (
    model, failure, observation, retain_inspection, session, invoke, close_session, snapshot)


def read(path):
    return json.loads(path.read_bytes())


class BoundaryFailureEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root/'inspection'
        self.xml = model()
        retain_inspection(self.folder, self.xml, failure())

    def test_missing_material_is_bound_to_xml_without_observation_or_credit(self):
        before = snapshot(self.root)
        result = boundaries.missing_material_failure(self.folder, self.xml)
        self.assertEqual(result, dict(cause='undefined_cell_material_reference',
            missing_material_ids=['74'], artifact_sha256=digest(self.xml),
            observation_status='unavailable', scientific_credit='none'))
        self.assertEqual(boundaries.execution_record(self.folder, self.xml), failure())
        with self.assertRaises(InsufficientEvidence):
            boundaries.record(self.folder, self.xml)
        self.assertEqual(snapshot(self.root), before)

    def test_distributed_references_and_all_missing_ids_are_reconstructed_from_xml(self):
        for number, (materials, error, expected) in enumerate([
                ('1 203', '203', ['203']), ('203 74', '203', ['203', '74']),
                ('74 74', '74', ['74'])]):
            folder = self.root/str(number)
            xml = model(materials)
            retain_inspection(folder, xml, failure(error))
            self.assertEqual(boundaries.missing_material_failure(folder, xml)['missing_material_ids'],
                             expected)

    def test_valid_material_void_and_absent_material_are_not_missing_references(self):
        variants = [model('1'), model('void'), model().replace(b' material="74"', b'')]
        for number, xml in enumerate(variants):
            folder = self.root/str(number)
            retain_inspection(folder, xml, failure())
            with self.assertRaisesRegex(InsufficientEvidence, 'cause unresolved'):
                boundaries.missing_material_failure(folder, xml)

    def test_wrong_exception_id_type_status_or_message_is_unqualified(self):
        variants = [failure('1'), failure('999'), failure(error_type='RuntimeError'),
                    dict(failure(), error='74'), dict(failure(), status='inspected'),
                    dict(failure(), error="'74' extra text")]
        for number, stdout in enumerate(variants):
            folder = self.root/str(number)
            retain_inspection(folder, self.xml, stdout)
            with self.assertRaises(InsufficientEvidence):
                boundaries.missing_material_failure(folder, self.xml)

    def test_unexpected_worker_status_rejected_by_controller_cannot_qualify(self):
        folder = self.root/'unexpected-status'
        result = retain_inspection(folder, self.xml, dict(failure(), status='infrastructure_failure'))
        self.assertEqual(result['status'], 'infrastructure_failure')
        self.assertEqual(result['error'], 'Unexpected inspector response')
        with self.assertRaisesRegex(ValueError, 'Boundary result changed'):
            boundaries.missing_material_failure(folder, self.xml)

    def test_successful_or_indeterminate_boundary_observations_are_not_load_failures(self):
        xml = model('1')
        folder = self.root/'observed'
        expected = observation(xml)
        retain_inspection(folder, xml, expected)
        self.assertEqual(boundaries.record(folder, xml), expected)
        self.assertEqual(boundaries.execution_record(folder, xml), expected)
        with self.assertRaises(InsufficientEvidence):
            boundaries.missing_material_failure(folder, xml)

    def test_missing_execution_receipt_remains_insufficient(self):
        (self.folder/'execution.json').unlink()
        with self.assertRaises(InsufficientEvidence):
            boundaries.missing_material_failure(self.folder, self.xml)

    def test_uncertain_cleanup_stays_insufficient(self):
        path = self.folder/'result.json'
        value = read(path); value['cleanup_confirmed'] = False; write_json(path, value)
        with self.assertRaises(InsufficientEvidence):
            boundaries.missing_material_failure(self.folder, self.xml)

    def test_nonzero_exit_timeout_or_output_limit_does_not_qualify(self):
        for number, execution in enumerate([
                dict(exit_code=1, stop_reason=None), dict(exit_code=0, stop_reason='timeout'),
                dict(exit_code=0, stop_reason='output_limit')]):
            folder = self.root/str(number)
            retain_inspection(folder, self.xml, failure(), **execution)
            with self.assertRaisesRegex(ValueError, 'execution incomplete'):
                boundaries.missing_material_failure(folder, self.xml)

    def test_xml_input_and_worker_tampering_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'input changed'):
            boundaries.missing_material_failure(self.folder, self.xml+b'\n')
        for name in ('input.json', 'worker.py'):
            folder = self.root/name.replace('.', '-')
            shutil.copytree(self.folder, folder)
            path = folder/name
            path.write_bytes(path.read_bytes()+b'\n')
            with self.assertRaises(ValueError):
                boundaries.missing_material_failure(folder, self.xml)

    def test_manifest_format_image_and_access_tampering_are_rejected(self):
        variants = [('format', 'private-boundary-inspection-v1'), ('image_id', 'unqualified'),
                    ('candidate_python_access', True), ('nuclear_data_access', True),
                    ('host_mounts', True), ('native_transport', 'run'), ('points', 1),
                    ('model_xml_sha256', 'changed'), ('input_sha256', 'changed'),
                    ('worker_sha256', 'changed')]
        for number, (key, value) in enumerate(variants):
            folder = self.root/str(number); shutil.copytree(self.folder, folder)
            path = folder/'manifest.json'; manifest = read(path)
            manifest[key] = value; write_json(path, manifest)
            with self.assertRaises(ValueError, msg=key):
                boundaries.missing_material_failure(folder, self.xml)

    def test_result_or_containment_tampering_is_rejected(self):
        variants = [('result.json', lambda r: r.update(error="'999'"), ValueError),
                    ('container-checks.json', lambda r: r.update(no_mounts=False), ValueError),
                    ('container-inspect.json', lambda r: r['HostConfig'].update(NetworkMode='host'), RuntimeError)]
        for number, (name, change, error_type) in enumerate(variants):
            folder = self.root/str(number); shutil.copytree(self.folder, folder)
            path = folder/name; value = read(path); change(value); write_json(path, value)
            with self.assertRaises(error_type, msg=name):
                boundaries.missing_material_failure(folder, self.xml)

    def test_relocated_receipts_verify_without_rewriting_originals(self):
        before = snapshot(self.root)
        with tempfile.TemporaryDirectory() as tmp:
            relocated = Path(tmp)/'different-location'
            shutil.copytree(self.folder, relocated)
            self.assertEqual(boundaries.missing_material_failure(relocated, self.xml),
                             boundaries.missing_material_failure(self.folder, self.xml))
        self.assertEqual(snapshot(self.root), before)

    def test_current_observation_identity_is_still_required(self):
        for number, (key, value) in enumerate([
                ('observer_version', 'effective-boundary-observation-v1'),
                ('openmc_version', '0.0'), ('model_xml_sha256', 'changed')]):
            xml = model('1'); stdout = observation(xml); stdout[key] = value
            folder = self.root/str(number); retain_inspection(folder, xml, stdout)
            with self.assertRaisesRegex(ValueError, 'semantic identity'):
                boundaries.record(folder, xml)

    def test_verification_is_read_only_and_never_starts_a_new_inspector(self):
        with patch.object(boundaries, 'observe', side_effect=AssertionError('No new inspection')), \
             patch('evaluation.scientific.inspection.docker', side_effect=AssertionError('No Docker')):
            boundaries.missing_material_failure(self.folder, self.xml)
            boundaries.execution_record(self.folder, self.xml)


class BoundaryAdapterFailureReceipts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tool = session(self.root/'boundary-tool')
        self.xml = model()

    def verify(self):
        return inspection_receipts.verify(self.tool.output, mode='mock')

    def test_failed_call_verifies_without_scientific_credit_or_feedback_change(self):
        reply = invoke(self.tool, self.xml, failure())
        self.assertEqual((reply['status'], reply['cause'], reply['observations']),
                         ('indeterminate', 'inspection_evidence_incomplete', None))
        feedback = read(self.tool.output/'call-01/feedback.json')
        self.assertEqual(feedback, boundary_feedback.compact(reply))
        self.assertEqual(feedback['task_conformity'], 'not_evaluated')
        self.assertIsNone(feedback['domain'])
        self.assertEqual(feedback['faces'], [])
        for key in ('error_type', 'error', 'missing_material_ids', 'scientific_credit', 'score'):
            self.assertNotIn(key, reply)
            self.assertNotIn(key, feedback)
        before = snapshot(self.root)
        result = self.verify()
        self.assertEqual((result['attempted_calls'], result['started_inspections'],
                          result['inspections'], result['model_calls']), (1, 1, 0, 0))
        self.assertEqual(result['failed_inspections'], [dict(call=1,
            cause='undefined_cell_material_reference', missing_material_ids=['74'],
            artifact_sha256=digest(self.xml), observation_status='unavailable', scientific_credit='none')])
        self.assertEqual(snapshot(self.root), before)

    def test_mixed_success_and_failure_counts_both_orders(self):
        for number, order in enumerate(('failure_first', 'success_first')):
            tool = session(self.root/f'owner-{number}'/'boundary-tool')
            good = model('1')
            pairs = [(self.xml, failure()), (good, observation(good))]
            if order=='success_first':
                pairs.reverse()
            for xml, stdout in pairs:
                invoke(tool, xml, stdout)
            result = inspection_receipts.verify(tool.output, mode='mock')
            self.assertEqual((result['attempted_calls'], result['started_inspections'],
                              result['inspections']), (2, 2, 1))
            self.assertEqual(result['failed_inspections'][0]['call'], 1 if order=='failure_first' else 2)

    def test_failed_attempts_consume_allowance_and_are_never_retried(self):
        for _ in range(2):
            invoke(self.tool, self.xml, failure())
        with patch.object(boundaries, 'observe', side_effect=AssertionError('No third inspection')):
            reply = self.tool.inspect_boundaries(dict(tool='inspect_boundaries', xml=self.xml.decode()),
                                                 remaining_seconds=600)
            close_session(self.tool)
            self.assertEqual(reply['cause'], 'tool_call_budget_exhausted')
            with self.assertRaisesRegex(ValueError, 'already exhausted'):
                self.tool.inspect_boundaries({}, remaining_seconds=600)
        with patch.object(boundaries, 'observe', side_effect=AssertionError('No verification dispatch')):
            result = self.verify()
        self.assertEqual((result['attempted_calls'], result['started_inspections'],
                          result['inspections'], len(result['failed_inspections'])), (3, 2, 0, 2))

    def test_unknown_failure_remains_insufficient(self):
        invoke(self.tool, self.xml, failure(error_type='RuntimeError'))
        with self.assertRaises(InsufficientEvidence):
            self.verify()

    def test_cleanup_uncertain_failure_remains_insufficient(self):
        invoke(self.tool, self.xml, failure())
        path = self.tool.output/'call-01/inspection/result.json'
        result = read(path); result['cleanup_confirmed'] = False; write_json(path, result)
        with self.assertRaises(InsufficientEvidence):
            self.verify()

    def test_usage_owner_staging_and_bridge_tampering_are_rejected(self):
        invoke(self.tool, self.xml, failure())
        variants = [('usage.json', lambda r: r.update(started_inspections=0)),
                    ('usage.json', lambda r: r.update(artifact_snapshots=0)),
                    ('../lifecycle.json', lambda r: r.update(state='running')),
                    ('../lifecycle.json', lambda r: r.update(container_id='different-owner')),
                    ('client-staging.json', lambda r: r.update(exit_code=1)),
                    ('feedback-staging.json', lambda r: r.update(stop_reason='timeout')),
                    ('bridge-cleanup.json', lambda r: r.update(host_bridge_closed=False))]
        for name, change in variants:
            path = self.tool.output/name; original = path.read_bytes()
            value = json.loads(original); change(value); write_json(path, value)
            with self.assertRaises(ValueError, msg=name):
                self.verify()
            path.write_bytes(original)

    def test_forged_failed_reply_observation_cause_or_hash_is_rejected(self):
        invoke(self.tool, self.xml, failure())
        folder = self.tool.output/'call-01'
        original = read(folder/'response.json')
        variants = [dict(original, artifact_sha256='different'), dict(original, observations={}),
                    dict(original, cause='claimed_other_failure'), dict(original, status='observed')]
        for reply in variants:
            write_json(folder/'response.json', reply)
            write_json(folder/'feedback.json', boundary_feedback.compact(reply))
            with self.assertRaises((ValueError, InsufficientEvidence)):
                self.verify()

    def test_request_snapshot_feedback_and_controller_tampering_are_rejected(self):
        invoke(self.tool, self.xml, failure())
        changes = [('call-01/model.xml', self.xml+b'\n'),
                   ('call-01/request.json', json.dumps(dict(tool='other', xml=self.xml.decode())).encode()),
                   ('call-01/feedback.json', b'{}'), ('adapter.py', b'# changed'),
                   ('feedback.py', b'# changed'), ('client.py', b'# changed'), ('bridge.py', b'# changed')]
        for name, content in changes:
            path = self.tool.output/name; original = path.read_bytes(); path.write_bytes(content)
            with self.assertRaises(ValueError, msg=name):
                self.verify()
            path.write_bytes(original)

    def test_success_only_and_zero_use_keep_existing_verification_shape(self):
        empty = self.verify()
        self.assertEqual((empty['attempted_calls'], empty['inspections']), (0, 0))
        self.assertNotIn('failed_inspections', empty)
        good = model('1'); invoke(self.tool, good, observation(good))
        result = self.verify()
        self.assertEqual((result['attempted_calls'], result['inspections']), (1, 1))
        self.assertNotIn('failed_inspections', result)
        self.assertNotIn('started_inspections', result)



if __name__ == '__main__':
    unittest.main()
