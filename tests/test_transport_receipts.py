"""Retained transport verification with synthetic files; no Docker or OpenMC."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.candidates import receipts, verify
from evaluator.evidence import InsufficientEvidence
from evaluator import run as exporter, transport
from evaluator.transport_input import accepted_export
from tests.test_transport import XML, SAMPLING, result_artifacts, save_export


# Required controller phases, declared independently of the verifier under test.
PHASES = ('preflight', 'solver-version', 'runtime-identity', 'staging',
          'xml-load', 'openmc', 'statepoint')


class TransportReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.folder = self.directory / 'transport'
        self.folder.mkdir()
        self.index = self.directory / 'data/cross_sections.xml'
        self.image = 'sha256:synthetic-transport'
        self.name = 'synthetic-transport'
        save_export(self.directory / 'export')
        _, provenance = accepted_export(self.directory / 'export')
        artifacts = result_artifacts()
        calculation = json.loads(artifacts['calculation.json'])
        calculation['keff']['uncertainty'] = 'one sigma'
        artifacts['calculation.json'] = json.dumps(calculation).encode()
        artifacts['convergence.csv'] = (
            'generation,active,k_generation,entropy_bits\n' +
            ''.join(f'{i},{i > 10},1.03,\n' for i in range(1, 41))
        ).encode()
        (self.folder / 'artifacts').mkdir()
        for name, raw in artifacts.items():
            (self.folder / 'artifacts' / name).write_bytes(raw)
        container = {
            'Image': self.image,
            'Config': {'User': '1000:1000',
                       'Entrypoint': ['python', '-I', '-B', '/opt/evaluator/idle.py']},
            'Mounts': [
                {'Type': 'bind', 'Source': str(self.index.parent),
                 'Destination': '/data', 'RW': False},
                {'Type': 'volume', 'Name': self.name + '-work',
                 'Destination': '/work', 'RW': True},
            ],
            'HostConfig': {
                'NetworkMode': 'none', 'ReadonlyRootfs': True,
                'Privileged': False, 'CapDrop': ['ALL'],
                'SecurityOpt': ['no-new-privileges=true'],
                'PidMode': '', 'IpcMode': 'private',
                'Memory': 3 * 1024**3, 'NanoCpus': 2_000_000_000, 'PidsLimit': 128,
                'Tmpfs': {'/input': '', '/tmp': ''},
            },
            'State': {'Running': True, 'Paused': True},
        }
        self.frozen = deepcopy(container)
        objects = {
            'manifest.json': {
                'image_id': self.image, 'candidate_sha256': 'source-hash',
                'container_name': self.name, 'model_xml_sha256': exporter.digest(XML),
                'candidate_python_access': False, 'reference_access': False,
                'scientific_inputs_changed': False,
            },
            'result.json': {
                'status': 'calculated_unreviewed', 'cleanup_confirmed': True,
                'statepoint_validation': 'passed', 'xml_load': 'passed',
                'transport': 'completed', 'sampling': SAMPLING,
                'keff': calculation['keff'],
            },
            'lifecycle.json': {'state': 'removed'},
            'container.json': container,
            'container-checks.json': {'synthetic': True},
            'preflight.json': {'checks': {'synthetic': True}},
            'frozen-container.json': container,
            'export-provenance.json': provenance,
            'artifacts.json': {
                name: {'bytes': len(raw), 'sha256': exporter.digest(raw)}
                for name, raw in artifacts.items()
            },
            'data-before.json': {'index_sha256': 'synthetic-data', 'files': {}},
            'data-after.json': {'index_sha256': 'synthetic-data', 'files': {}},
            'runtime-identity.json': {'synthetic': True},
        }
        for phase in PHASES:
            objects[phase + '-process.json'] = {'exit_code': 0, 'stop_reason': None}
        for name, value in objects.items():
            exporter.write_json(self.folder / name, value)
        exporter.write_json(self.directory / 'report.json', {
            'diagnostic_score': {'score': 100.0},
        })
        self.addCleanup(patch.stopall)
        patch.object(exporter, 'docker',
                     side_effect=AssertionError('Review must not dispatch Docker')).start()

    def record(self):
        return receipts.transport_record(
            self.directory, 'source-hash', self.image, self.index)

    def review(self):
        # Unrelated assessment reconstruction is replaced; transport verification
        # and the public review's missing/contradictory classification are real.
        with patch.object(verify, 'assessment_report',
                          side_effect=lambda *args, **kwargs: self.record()):
            return verify.review_assessment(self.directory, self.index)

    def snapshot(self):
        return {str(p.relative_to(self.directory)): p.read_bytes()
                for p in self.directory.rglob('*') if p.is_file()}

    def test_complete_receipts_pass_without_modifying_evidence(self):
        before = self.snapshot()
        record = self.record()
        self.assertEqual(record['keff']['mean'], 1.03)
        self.assertEqual(record['sampling'], SAMPLING)
        for phase in PHASES:
            self.assertIn(str(self.folder / (phase + '-process.json')),
                          record['receipts'])
        self.assertEqual(self.snapshot(), before)

    def test_each_missing_process_receipt_is_insufficient(self):
        for phase in PHASES:
            path = self.folder / (phase + '-process.json')
            original = path.read_bytes()
            try:
                path.unlink()
                with self.subTest(phase=phase):
                    with self.assertRaisesRegex(InsufficientEvidence, path.name):
                        self.record()
                    review = self.review()
                    self.assertEqual(review['evidence_status'], 'insufficient')
                    self.assertIsNone(review['score'])
                    self.assertEqual(review['reported_score'], 100.0)
            finally:
                path.write_bytes(original)

    def test_failed_or_interrupted_process_contradicts_success(self):
        for phase in PHASES:
            path = self.folder / (phase + '-process.json')
            original = path.read_bytes()
            try:
                for process in (
                    {'exit_code': 7, 'stop_reason': None},
                    {'exit_code': -9, 'stop_reason': 'timeout'},
                    {'exit_code': 0, 'stop_reason': 'output_limit'},
                ):
                    exporter.write_json(path, process)
                    with self.subTest(phase=phase, process=process):
                        review = self.review()
                        self.assertEqual(review['evidence_status'], 'contradictory')
                        self.assertIsNone(review['score'])
                        self.assertIn(path.name, review['reason'])
            finally:
                path.write_bytes(original)

    def test_malformed_process_receipts_cannot_prove_success(self):
        path = self.folder / 'openmc-process.json'
        for process in (
            {'exit_code': False, 'stop_reason': None},
            {'exit_code': 0.0, 'stop_reason': None},
            {'exit_code': '0', 'stop_reason': None},
            {'exit_code': 0},
            {'exit_code': 0, 'stop_reason': None, 'unexpected': True},
            [],
        ):
            exporter.write_json(path, process)
            with self.subTest(process=process):
                review = self.review()
                self.assertEqual(review['evidence_status'], 'contradictory')
                self.assertIsNone(review['score'])

    def test_frozen_container_must_be_running_and_paused(self):
        for field in ('Running', 'Paused'):
            for value in (False, 1):
                frozen = deepcopy(self.frozen)
                frozen['State'][field] = value
                exporter.write_json(self.folder / 'frozen-container.json', frozen)
                with self.subTest(field=field, value=value):
                    review = self.review()
                    self.assertEqual(review['evidence_status'], 'contradictory')
                    self.assertIsNone(review['score'])

    def test_frozen_container_boundary_must_match(self):
        frozen = deepcopy(self.frozen)
        frozen['Image'] = 'sha256:another-image'
        exporter.write_json(self.folder / 'frozen-container.json', frozen)
        review = self.review()
        self.assertEqual(review['evidence_status'], 'contradictory')
        self.assertIsNone(review['score'])

    def test_missing_frozen_container_is_insufficient(self):
        (self.folder / 'frozen-container.json').unlink()
        review = self.review()
        self.assertEqual(review['evidence_status'], 'insufficient')
        self.assertIsNone(review['score'])


if __name__ == '__main__':
    unittest.main()
