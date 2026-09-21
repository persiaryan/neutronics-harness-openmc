"""Factory protocol boundaries; actual candidate execution is qualified in Docker."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_evaluator as fixtures
from evaluator import run
from evaluator.contracts import FACTORY, export_contract
from evaluator.evidence import InsufficientEvidence
from evaluation.candidates.phase_evidence import export_outcome
from prompts import prepare

ROOT = Path(__file__).resolve().parents[1]




class FactoryLifecycleTests(unittest.TestCase):
    setUp = fixtures.LifecycleTests.setUp
    docker = fixtures.LifecycleTests.docker

    def bounded(self, args, **kwargs):
        if '/input/factory.py' in args:
            self.calls.append(tuple(args))
            return dict(exit_code=0, stop_reason=None, stderr=b'', stdout=json.dumps(dict(
                format='candidate-process-v2', returncode=self.candidate_code, stop_reason=self.stop,
                termination='signal' if self.candidate_code < 0 else 'exit', observer_protected=True,
                stdout_b64=base64.b64encode(getattr(self, 'candidate_stdout', b'')).decode(), stderr_b64='')).encode())
        return fixtures.LifecycleTests.bounded(self, args, **kwargs)

    def evaluate(self):
        return run.evaluate(self.candidate, self.output, index=self.index, contract=FACTORY)

    def verdict(self):
        return export_outcome(self.output, fixtures.IMAGE, self.index, run.digest(self.candidate.read_bytes()))

    def test_host_only_stages_source_and_driver_and_verifies_retrieved_xml(self):
        # Fixture body would raise if invoked on the host. No candidate import.
        with patch('importlib.util.spec_from_file_location', side_effect=AssertionError('host import forbidden')):
            result = self.evaluate()
        self.assertEqual(result['status'], 'exported')
        launch = json.loads((self.output / 'execution-launch.json').read_bytes())
        self.assertEqual(launch['entrypoint'], '/input/factory.py')
        self.assertEqual(launch['delivery_contract'], FACTORY)
        self.assertEqual(self.verdict(), dict(cause=None, reason=None))
        self.assertEqual(len([c for c in self.calls if '/input/factory.py' in c]), 1)
        self.assertFalse(any('/input/candidate.py' in c for c in self.calls))

    def test_noncallable_is_resolved_inside_driver_not_by_top_level_ast_shape(self):
        self.candidate.write_text('build_model = None\n')
        self.candidate_code = 1
        self.assertEqual(self.evaluate()['reason'], 'candidate_exit_nonzero')
        self.assertEqual(self.verdict()['cause'], 'model')
        self.assertTrue((self.output / 'execution-launch.json').exists())

    def test_xml_and_forged_candidate_receipt_do_not_rescue_nonzero_exit(self):
        self.candidate_code = 255
        self.candidate_stdout = b'{"format":"candidate-process-v2","returncode":0,"observer_protected":true}'
        self.assertEqual(self.evaluate()['reason'], 'candidate_exit_nonzero')
        self.assertEqual(self.verdict(), dict(cause='model', reason='candidate_exit_nonzero'))
        self.assertEqual(json.loads((self.output / 'candidate-process.json').read_bytes())['returncode'], 255)

    def test_signal_keeps_indeterminate_attribution(self):
        self.candidate_code = -9
        self.evaluate()
        self.assertEqual(self.verdict(), dict(cause='indeterminate', reason='candidate_signal_or_oom'))

    def test_extra_artifacts_are_not_part_of_factory_envelope(self):
        self.archive = fixtures.archive([('work/model.xml', fixtures.XML), ('work/other.xml', b'<model/>')])
        self.assertEqual(self.evaluate()['reason'], 'unexpected_factory_artifacts')
        self.assertEqual(self.verdict()['reason'], 'unexpected_factory_artifacts')

    def test_missing_staging_receipt_is_insufficient(self):
        self.evaluate()
        (self.output / 'driver-staging.json').unlink()
        with self.assertRaises(InsufficientEvidence):
            self.verdict()

    def test_changed_driver_or_launch_is_contradictory(self):
        self.evaluate()
        launch = self.output / 'execution-launch.json'
        value = json.loads(launch.read_bytes()); value['entrypoint'] = '/input/candidate.py'
        run.write_json(launch, value)
        with self.assertRaisesRegex(ValueError, 'execution path'):
            self.verdict()
        value['entrypoint'] = '/input/factory.py'; run.write_json(launch, value)
        (self.output / 'evaluator-factory.py').write_text('print("not the driver")')
        with self.assertRaisesRegex(ValueError, 'Changed factory driver'):
            self.verdict()

    def test_new_export_cannot_discard_its_declared_contract(self):
        self.evaluate()
        path = self.output / 'manifest.json'
        value = json.loads(path.read_bytes()); del value['delivery_contract']
        run.write_json(path, value)
        with self.assertRaisesRegex(ValueError, 'export delivery contract'):
            self.verdict()

    def test_factory_failure_never_launches_script_fallback(self):
        self.candidate_code = 1
        self.evaluate()
        commands = [c for c in self.calls if '/input/factory.py' in c or '/input/candidate.py' in c]
        self.assertEqual(len(commands), 1)
        self.assertIn('/input/factory.py', commands[0])

    def test_cleanup_refuses_to_remove_unexpected_resource_identity(self):
        calls = []
        def unexpected(*args):
            calls.append(args)
            return 'other-operators-container' if args[0] == 'ps' else ''
        with patch.object(run, 'docker', side_effect=unexpected), self.assertRaisesRegex(RuntimeError, 'cleanup identity'):
            run.cleanup('this-test-container')
        self.assertFalse(any(c[0] == 'rm' for c in calls))


if __name__ == '__main__':
    unittest.main()
