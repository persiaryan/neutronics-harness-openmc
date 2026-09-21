"""Transport admission, provenance, numerical receipt and lifecycle controls."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from evaluator import transport as tr
from evaluator import run
from evaluator.transport_input import accepted_export, transport_profile

XML = b'''<model><materials><material id="1"><density units="g/cm3" value="1"/>
<nuclide name="U235" ao="0.04"/><nuclide name="U238" ao="0.96"/>
</material></materials><geometry><cell id="1" material="1" region="-1" universe="0"/>
<surface id="1" type="sphere" coeffs="0 0 0 50" boundary="vacuum"/></geometry>
<settings><run_mode>eigenvalue</run_mode><particles>500</particles><batches>20</batches>
<inactive>5</inactive><generations_per_batch>2</generations_per_batch><seed>23</seed>
<source type="independent"><space type="point"><parameters>0 0 0</parameters></space></source>
</settings></model>'''
SAMPLING = {'particles': 500, 'batches': 20, 'inactive': 5, 'generations_per_batch': 2, 'seed': 23}


def save_export(directory, xml=XML):
    (directory / 'artifacts').mkdir(parents=True)
    (directory / 'artifacts/model.xml').write_bytes(xml)
    for name, content in {
        'result.json': {'status': 'exported', 'xml_validation': 'passed', 'cleanup_confirmed': True},
        'manifest.json': {'format': 'isolated-export-evaluation-v2', 'delivery_contract':'openmc-model-factory-v1', 'candidate_sha256': 'source-hash'},
        'lifecycle.json': {'state': 'removed'},
        'artifacts.json': {'model.xml': {'bytes': len(xml), 'sha256': run.digest(xml)}},
    }.items():
        run.write_json(directory / name, content)


def result_artifacts():
    statepoint = b'synthetic statepoint bytes; never parsed by host'
    loaded = {'status': 'loaded', 'sampling': SAMPLING, 'model_xml_sha256': run.digest(XML),
              'boundary_checks': {'no_candidate_python': True}, 'scientific_inputs_changed': False,
              'entropy_requested': False}
    calculation = {'status': 'calculated_unreviewed', 'sampling': SAMPLING,
                   'model_xml_sha256': run.digest(XML), 'openmc_version': [0, 15, 3],
                   'keff': {'mean': 1.03, 'std_dev': 0.004},
                   'statepoint': {'name': 'statepoint.20.h5', 'bytes': len(statepoint),
                                  'sha256': run.digest(statepoint)}}
    return {'model.xml': XML, 'statepoint.20.h5': statepoint,
            'xml-load.json': json.dumps(loaded).encode(),
            'calculation.json': json.dumps(calculation).encode()}


def archive(artifacts):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as tar:
        for name, data in artifacts.items():
            member = tarfile.TarInfo('work/' + name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    return buffer.getvalue()


class AdmissionTests(unittest.TestCase):
    def test_profile_preserves_sampling_and_identifies_actual_data(self):
        profile = transport_profile(XML, 'cross_sections.xml')
        self.assertEqual(profile['sampling'], SAMPLING)
        self.assertEqual(profile['required_tables'], [['neutron', 'U235'], ['neutron', 'U238']])
        self.assertFalse(profile['scientific_inputs_changed'])

    def test_openmc_exported_temperature_and_entropy_elements_are_admitted(self):
        xml = XML.replace(b'</settings>', b'''<temperature_default>293.6</temperature_default>
            <temperature_method>nearest</temperature_method><temperature_tolerance>1.0</temperature_tolerance>
            <entropy_mesh>1</entropy_mesh><mesh id="1"><dimension>7 7 12</dimension>
            <lower_left>-4.41 -4.41 -30</lower_left><upper_right>4.41 4.41 30</upper_right></mesh></settings>''')
        self.assertTrue(transport_profile(xml, 'cross_sections.xml')['entropy_requested'])

    def test_external_sources_paths_meshes_and_unsupported_options_are_rejected(self):
        options = [b'<source type="compiled" library="/tmp/evil.so"/>',
                   b'<source file="/data/U235.h5"/>', b'<source><library>/tmp/evil.so</library></source>',
                   b'<mesh id="1" type="unstructured" filename="/data/x.h5"/>',
                   b'<weight_windows_file>/tmp/x.h5</weight_windows_file>',
                   b'<output><path>/input</path></output>', b'<trigger><active>true</active></trigger>']
        for option in options:
            with self.subTest(option=option), self.assertRaises(ValueError):
                transport_profile(XML.replace(b'</settings>', option + b'</settings>'), 'cross_sections.xml')

    def test_budget_and_final_statepoint_settings_are_not_silently_repaired(self):
        for xml in (XML.replace(b'<particles>500', b'<particles>5000000'),
                    XML.replace(b'<inactive>5', b'<inactive>19'),
                    XML.replace(b'</settings>', b'<state_point><batches>10</batches></state_point></settings>'),
                    XML.replace(b'<seed>23</seed>', b'<seed>23</seed><seed>24</seed>')):
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                transport_profile(xml, 'cross_sections.xml')

    def test_failed_export_and_changed_artifact_cannot_start_transport(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            save_export(directory)
            self.assertEqual(accepted_export(directory)[0], XML)
            (directory / 'artifacts/model.xml').write_bytes(XML + b' ')
            with self.assertRaisesRegex(ValueError, 'identity'):
                accepted_export(directory)
            (directory / 'artifacts/model.xml').write_bytes(XML)
            run.write_json(directory / 'result.json', {'status': 'rejected', 'cleanup_confirmed': True})
            with self.assertRaisesRegex(ValueError, 'successful export'):
                accepted_export(directory)

    def test_symlink_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            save_export(directory)
            (directory / 'artifacts/model.xml').unlink()
            (directory / 'artifacts/model.xml').symlink_to(directory / 'result.json')
            with self.assertRaisesRegex(ValueError, 'regular'):
                accepted_export(directory)

    def test_data_identity_hashes_content_and_requires_unique_table(self):
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / 'cross_sections.xml'
            index.write_text('<cross_sections><library type="neutron" materials="U235 U238" path="U.h5"/></cross_sections>')
            (index.parent / 'U.h5').write_bytes(b'abc')
            profile = transport_profile(XML, index.name)
            identity = tr.data_identity(index, profile)
            self.assertEqual(identity['files']['U.h5']['sha256'],
                             'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
            (index.parent / 'U.h5').write_bytes(b'abd')
            self.assertNotEqual(tr.data_identity(index, profile), identity)
            index.write_text('<cross_sections/>')
            with self.assertRaisesRegex(ValueError, 'one admitted library'):
                tr.data_identity(index, profile)

    def test_receipts_cannot_hide_changed_settings_or_statepoint(self):
        profile = transport_profile(XML, 'cross_sections.xml')
        artifacts = result_artifacts()
        self.assertEqual(tr.validate_calculation(artifacts, profile, XML)['keff']['mean'], 1.03)
        artifacts['statepoint.20.h5'] += b'tampered'
        with self.assertRaisesRegex(ValueError, 'Statepoint bytes'):
            tr.validate_calculation(artifacts, profile, XML)
        artifacts = result_artifacts()
        record = json.loads(artifacts['calculation.json'])
        record['sampling']['seed'] = 99
        artifacts['calculation.json'] = json.dumps(record).encode()
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            tr.validate_calculation(artifacts, profile, XML)

    def test_nonfinite_or_zero_uncertainty_is_not_accepted(self):
        profile = transport_profile(XML, 'cross_sections.xml')
        for value in (float('nan'), float('inf'), 0, -1, True):
            artifacts = result_artifacts()
            record = json.loads(artifacts['calculation.json'])
            record['keff']['std_dev'] = value
            artifacts['calculation.json'] = json.dumps(record).encode()
            with self.subTest(value=value), self.assertRaises(ValueError):
                tr.validate_calculation(artifacts, profile, XML)


class TransportLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.export, self.output = self.root / 'export', self.root / 'result'
        save_export(self.export)
        self.index = self.root / 'data/cross_sections.xml'
        self.calls = []
        self.present = self.volume_present = False
        self.failure, self.stop, self.prior = None, None, None
        self.failure_code, self.stop_reason = 7, 'timeout'
        self.freeze_ok, self.writable_data, self.worker_mismatch = True, False, False
        self.artifacts = result_artifacts()
        for name, replacement in [('docker', self.docker), ('bounded', self.bounded),
                                  ('data_directory', lambda _: (self.index, {}))]:
            p = patch.object(run, name, side_effect=replacement)
            p.start()
            self.addCleanup(p.stop)
        self.identity = patch.object(tr, 'data_identity', return_value={'synthetic': True}).start()
        self.addCleanup(patch.stopall)

    def docker(self, *args):
        self.calls.append(args)
        if args[:2] == ('image', 'inspect'):
            return '[{"Id":"sha256:test"}]'
        if args[0] == 'ps':
            return 'prior' if self.prior == 'container' else (self.name if self.present else '')
        if args[:2] == ('volume', 'ls'):
            return 'prior-work' if self.prior == 'volume' else (self.name + '-work' if self.volume_present else '')
        if args[:2] == ('volume', 'create'):
            self.name, self.volume_present = args[-1].removesuffix('-work'), True
        if args[:2] == ('volume', 'inspect'):
            return json.dumps([{'Driver': 'local', 'Options': tr.WORK_OPTIONS}])
        if args[:2] == ('volume', 'rm'):
            self.volume_present = False
        if args[0] == 'create':
            self.present = True
            self.config = {
                'Image': 'sha256:test', 'Config': {'User': '1000:1000',
                    'Entrypoint': ['python', '-I', '-B', '/opt/evaluator/idle.py']},
                'Mounts': [{'Type': 'bind', 'Source': str(self.index.parent), 'Destination': '/data', 'RW': self.writable_data},
                           {'Type': 'volume', 'Name': self.name + '-work', 'Destination': '/work', 'RW': True}],
                'HostConfig': {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Privileged': False,
                    'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges=true'], 'PidMode': '',
                    'IpcMode': 'private', 'Memory': tr.MEMORY, 'NanoCpus': 2_000_000_000, 'PidsLimit': 128,
                    'Tmpfs': {'/input': 'rw,nosuid,nodev,size=16777216,uid=1000,gid=1000,mode=700', '/tmp': ''}},
                'State': {'Running': True, 'Paused': self.freeze_ok}}
            return 'test-container'
        if args[0] == 'inspect':
            return json.dumps([self.config])
        if args[0] == 'rm':
            self.present = False
        return ''

    def bounded(self, args, **kwargs):
        self.calls.append(tuple(args))
        result = {'exit_code': 0, 'stop_reason': None, 'stdout': b'', 'stderr': b''}
        if args[-1] == '/opt/evaluator/probe.py':
            result['stdout'] = b'{"checks":{"synthetic":true}}'
        elif args[-1] == '--version':
            result['stdout'] = b'OpenMC version 0.15.3\n'
        elif args[-1] == 'probe':
            worker = Path(tr.__file__).parent / 'runtime/transport_worker.py'
            result['stdout'] = json.dumps({'worker_sha256': 'changed' if self.worker_mismatch else run.digest(worker.read_bytes())}).encode()
        elif '-i' in args:
            self.assertEqual(kwargs['data'], XML)
            result['stdout'] = run.digest(XML).encode()
        elif args[-1] in {'load', 'extract', '1'}:
            if args[-1] == self.failure:
                result['exit_code'] = self.failure_code
            if args[-1] == self.stop:
                result.update(exit_code=-9, stop_reason=self.stop_reason)
        elif args[:2] == ['docker', 'cp']:
            self.assertTrue(any(c[0] == 'pause' for c in self.calls))
            result['stdout'] = archive(self.artifacts)
        return result

    def evaluate(self):
        return tr.transport(self.export, self.output, index=self.index)

    def test_transport_is_xml_only_preserves_sampling_and_cleans_up(self):
        result = self.evaluate()
        self.assertEqual(result['status'], 'calculated_unreviewed')
        self.assertEqual(result['sampling'], SAMPLING)
        self.assertEqual(result['reference_comparison'], 'not_run')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertFalse(self.present or self.volume_present)
        self.assertFalse(any('candidate.py' in ' '.join(c) for c in self.calls))

    def test_load_failure_does_not_start_solver(self):
        self.failure = 'load'
        result = self.evaluate()
        self.assertEqual(result['reason'], 'xml-load_exit_nonzero')
        self.assertEqual(result['transport'], 'not_run')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertFalse(any(c[-1] == '1' for c in self.calls))

    def test_native_failure_does_not_extract_or_report_keff(self):
        self.failure = '1'
        result = self.evaluate()
        self.assertEqual(result['reason'], 'openmc_exit_nonzero')
        self.assertNotIn('keff', result)
        self.assertFalse(any(c[-1] == 'extract' for c in self.calls))

    def test_native_signal_exit_is_not_counted_as_a_model_rejection(self):
        self.failure, self.failure_code = '1', 137
        result = self.evaluate()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['reason'], 'openmc_abnormal_exit')

    def test_extraction_failure_prevents_numerical_success(self):
        self.failure = 'extract'
        result = self.evaluate()
        self.assertEqual(result['transport'], 'completed')
        self.assertEqual(result['statepoint_validation'], 'failed')
        self.assertNotIn('keff', result)

    def test_changed_statepoint_bytes_fail_after_retrieval(self):
        self.artifacts['statepoint.20.h5'] += b'changed'
        result = self.evaluate()
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('keff', result)
        self.assertTrue(result['cleanup_confirmed'])

    def test_unfrozen_runtime_prevents_artifact_retrieval(self):
        self.freeze_ok = False
        result = self.evaluate()
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(any(c[:2] == ('docker', 'cp') for c in self.calls))

    def test_writable_data_boundary_stops_before_xml_loading(self):
        self.writable_data = True
        result = self.evaluate()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['xml_load'], 'not_run')

    def test_stale_runtime_worker_stops_before_staging_xml(self):
        self.worker_mismatch = True
        result = self.evaluate()
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(any('-i' in c for c in self.calls))

    def test_timeout_removes_runtime_without_retrieving_live_files(self):
        self.stop = '1'
        result = self.evaluate()
        self.assertEqual(result['status'], 'budget_exceeded')
        self.assertEqual(result['reason'], 'openmc_timeout')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertFalse(any(c[:2] == ('docker', 'cp') for c in self.calls))

    def test_output_limit_also_removes_runtime_without_fetch(self):
        self.stop, self.stop_reason = '1', 'output_limit'
        result = self.evaluate()
        self.assertEqual(result['reason'], 'openmc_output_limit')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertFalse(any(c[:2] == ('docker', 'cp') for c in self.calls))

    def test_changed_data_invalidates_the_result(self):
        self.identity.side_effect = [{'synthetic': True}, {'synthetic': False}]
        result = self.evaluate()
        self.assertEqual(result['reason'], 'nuclear_data_changed_during_run')
        self.assertNotIn('keff', result)

    def test_cleanup_uncertainty_cannot_claim_completion(self):
        with patch.object(run, 'cleanup', side_effect=RuntimeError('daemon unavailable')):
            result = self.evaluate()
        self.assertEqual(result['status'], 'cleanup_uncertain')
        self.assertFalse(result['cleanup_confirmed'])

    def test_prior_volume_blocks_container_creation(self):
        self.prior = 'volume'
        result = self.evaluate()
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(any(c[0] == 'create' for c in self.calls))

    def test_failed_export_is_recorded_without_docker_calls(self):
        run.write_json(self.export / 'result.json', {'status': 'rejected'})
        result = self.evaluate()
        self.assertEqual(result['reason'], 'input_not_admitted')
        self.assertEqual(self.calls, [])
        self.assertTrue((self.output / 'result.json').is_file())


if __name__ == '__main__':
    unittest.main()
