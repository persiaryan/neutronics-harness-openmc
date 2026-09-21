"""Evaluator boundaries and independent fixtures; no model calls or transport."""
import io
import base64
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from evaluator.profiles import PROFILE
IMAGE = PROFILE['export_image']
from evaluator import run
from evaluator.inspect import inspect_model

XML = b'<model><materials><material id="1"/></materials><geometry><cell id="1"/></geometry><settings/></model>'


def archive(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as tar:
        for name, content in files:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def configuration(index):
    return {'Image': IMAGE, 'Mounts': [{'Type': 'bind', 'Source': str(index.parent),
        'Destination': '/data', 'RW': False}], 'Config': {'User': '1000:1000',
        'Entrypoint': ['python', '-I', '-B', '/opt/evaluator/idle.py']},
        'HostConfig': {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Privileged': False,
            'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges=true'], 'PidMode': '',
            'IpcMode': 'private', 'Memory': 2 * 1024**3, 'NanoCpus': 2_000_000_000,
            'PidsLimit': 128, 'Tmpfs': {'/input': '', '/tmp': ''}},
        'State': {'Running': True, 'Paused': True, 'OOMKilled': False}}


class ArtifactTests(unittest.TestCase):
    def test_regular_artifacts_are_preserved_exactly(self):
        self.assertEqual(run.artifact_bytes(archive([('work/model.xml', XML)])), {'model.xml': XML})

    def test_paths_duplicates_links_and_size_are_rejected(self):
        for names in ([('work/../escape', b'x')], [('work/sub/file', b'x')], [('/etc/file', b'x')],
                      [('work/model.xml', b'a'), ('work/model.xml', b'b')]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                run.artifact_bytes(archive(names))
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE):
            buffer = io.BytesIO()
            with tarfile.open(fileobj=buffer, mode='w') as tar:
                member = tarfile.TarInfo('work/model.xml')
                member.type, member.linkname = kind, '/data/cross_sections.xml'
                tar.addfile(member)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                run.artifact_bytes(buffer.getvalue())
        with patch.object(run, 'MAX_ARTIFACT', 1), self.assertRaises(ValueError):
            run.artifact_bytes(archive([('work/model.xml', XML)]))

    def test_structural_pass_does_not_claim_physical_correctness(self):
        result = inspect_model(XML)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['scientific_fidelity'], 'not_checked')
        self.assertEqual(result['openmc_xml_load'], 'not_run')

    def test_xml_rejects_external_entities_includes_and_missing_sections(self):
        for xml in (b'<!DOCTYPE model [<!ENTITY x SYSTEM "file:///etc/passwd">]><model>&x;</model>',
                    '<!DOCTYPE model [<!ENTITY x "hidden">]><model>&x;</model>'.encode('utf-16-le'),
                    b'<model/>', b'<geometry/>', XML.replace(b'<settings/>', b''),
                    XML.replace(b'<settings/>', b'<settings/><settings/>'),
                    XML.replace(b'<settings/>', b'<settings xmlns="urn:other"/>')):
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                inspect_model(xml)

    def test_bounded_process_enforces_output_and_time_limits(self):
        result = run.bounded([sys.executable, '-c', 'print("x"*200000)'], timeout=5, limit=1000)
        self.assertEqual(result['stop_reason'], 'output_limit')
        self.assertLessEqual(len(result['stdout']) + len(result['stderr']), 1000)
        result = run.bounded([sys.executable, '-c', 'import time; time.sleep(60)'], timeout=0.1)
        self.assertEqual(result['stop_reason'], 'timeout')


class DataTests(unittest.TestCase):
    def test_data_directory_contains_only_listed_regular_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = root / 'cross_sections.xml'
            index.write_text('<cross_sections><library type="neutron" materials="H1" path="H1.h5"/></cross_sections>')
            (root / 'H1.h5').write_bytes(b'synthetic')
            self.assertEqual(len(run.data_directory(index)[1]['files']), 2)
            (root / 'private-result.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'unlisted'):
                run.data_directory(index)
            (root / 'private-result.json').unlink()
            (root / 'H1.h5').unlink()
            (root / 'H1.h5').symlink_to(index)
            with self.assertRaisesRegex(ValueError, 'links'):
                run.data_directory(index)

    def test_data_index_cannot_escape_its_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / 'cross_sections.xml'
            for name in ('../secret.h5', '/secret.h5', 'sub/file.h5'):
                index.write_text(f'<cross_sections><library type="neutron" path="{name}"/></cross_sections>')
                with self.subTest(name=name), self.assertRaises(ValueError):
                    run.data_directory(index)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / 'candidate.py'
        self.candidate.write_text('def build_model():\n    raise RuntimeError("must not run on host")\n')
        self.index = self.root / 'data/cross_sections.xml'
        self.output = self.root / 'result'
        self.calls = []
        self.present = False
        self.volume_present = False
        self.archive = archive([('work/model.xml', XML)])
        self.candidate_code, self.stop = 0, None
        self.config = configuration(self.index)
        for name, replacement in (('docker', self.docker), ('bounded', self.bounded),
                                  ('data_directory', lambda p: (self.index, {}))):
            patcher = patch.object(run, name, side_effect=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def docker(self, *args):
        self.calls.append(args)
        if args[:2] == ('image', 'inspect'):
            return json.dumps([{'Id':IMAGE}])
        if args[0] == 'ps':
            return self.name if self.present else ''
        if args[:2] == ('volume', 'ls'):
            return self.name + '-work' if self.volume_present else ''
        if args[:2] == ('volume', 'create'):
            self.name = args[-1].removesuffix('-work')
            self.volume_present = True
        if args[:2] == ('volume', 'inspect'):
            return json.dumps([{'Driver': 'local', 'Options': {'type': 'tmpfs', 'device': 'tmpfs',
                'o': 'size=134217728,uid=1000,gid=1000,mode=700,nosuid,nodev'}}])
        if args[:2] == ('volume', 'rm'):
            self.volume_present = False
        if args[0] == 'create':
            self.name = args[args.index('--name') + 1]
            self.present = True
            self.config['Mounts'].append({'Type': 'volume', 'Name': self.name + '-work',
                                          'Destination': '/work', 'RW': True})
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
        elif args[:3] == ['docker', 'exec', '-i']:
            result['stdout'] = run.digest(kwargs['data']).encode() + b'\n'
        elif '/input/factory.py' in args:
            result['stdout'] = json.dumps(dict(format='candidate-process-v2', returncode=self.candidate_code,
                stop_reason=self.stop, termination='signal' if self.candidate_code < 0 else 'exit',
                observer_protected=True, stdout_b64='', stderr_b64='')).encode()
        elif args[:2] == ['docker', 'cp'] and args[-1] == '-':
            self.assertTrue(any(c[0] == 'pause' for c in self.calls))
            result['stdout'] = self.archive
        return result

    def evaluate(self):
        return run.evaluate(self.candidate, self.output, index=self.index, contract='openmc-model-factory-v1')

    def test_valid_xml_is_exported_after_freezing_and_preserved(self):
        result = self.evaluate()
        self.assertEqual(result['status'], 'exported')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual((self.output / 'candidate.py').read_bytes(), self.candidate.read_bytes())
        self.assertEqual((self.output / 'artifacts/model.xml').read_bytes(), XML)
        self.assertEqual(result['transport'], 'not_run')

    def test_separate_files_are_a_retained_contract_failure(self):
        self.archive = archive([('work/settings.xml', b'<settings/>'), ('work/geometry.xml', b'<geometry/>')])
        result = self.evaluate()
        self.assertEqual(result['reason'], 'unexpected_factory_artifacts')
        self.assertEqual(result['candidate_exit_code'], 0)
        self.assertTrue((self.output / 'artifacts/geometry.xml').is_file())
        self.assertTrue(result['cleanup_confirmed'])

    def test_nonzero_exit_cannot_pass_even_with_model_xml(self):
        self.candidate_code = 7
        self.assertEqual(self.evaluate()['reason'], 'candidate_exit_nonzero')

    def test_timeout_does_not_retrieve_live_artifacts(self):
        self.stop = 'timeout'
        result = self.evaluate()
        self.assertEqual(result['reason'], 'candidate_timeout')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertFalse(any(c[:2] == ('docker', 'cp') and c[-1] == '-' for c in self.calls))

    def test_unsafe_archive_is_rejected_and_cleaned_up(self):
        self.archive = archive([('work/../escape', b'x')])
        result = self.evaluate()
        self.assertEqual(result['reason'], 'invalid_artifact_archive')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertFalse((self.root / 'escape').exists())

    def test_boundary_change_stops_before_candidate_execution(self):
        self.config['Mounts'][0]['RW'] = True
        result = self.evaluate()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['candidate_execution'], 'not_run')
        self.assertTrue(result['cleanup_confirmed'])

    def test_freeze_failure_prevents_artifact_inspection(self):
        self.config['State']['Paused'] = False
        result = self.evaluate()
        self.assertEqual(result['status'], 'failed')
        self.assertFalse((self.output / 'artifacts').exists())

    def test_cleanup_uncertainty_cannot_be_exported(self):
        with patch.object(run, 'cleanup', side_effect=RuntimeError('daemon unavailable')):
            result = self.evaluate()
        self.assertEqual(result['status'], 'cleanup_uncertain')
        self.assertFalse(result['cleanup_confirmed'])

    def test_prior_container_and_existing_output_block_replay(self):
        self.present, self.name = True, 'prior'
        with self.assertRaisesRegex(RuntimeError, 'prior evaluator'):
            self.evaluate()
        self.present = False
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.evaluate()

    def test_prior_volume_blocks_replay(self):
        self.volume_present, self.name = True, 'prior'
        with self.assertRaisesRegex(RuntimeError, 'prior evaluator volume'):
            self.evaluate()
        self.assertFalse(self.output.exists())

    def test_log_limit_cleans_up_without_retrieving_live_artifacts(self):
        self.stop = 'output_limit'
        result = self.evaluate()
        self.assertEqual(result['reason'], 'candidate_output_limit')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertFalse(self.present)
        self.assertFalse(self.volume_present)

    def test_boundary_rejects_unrelated_mount_paths_and_host_privileges(self):
        info = configuration(self.index)
        info['Mounts'].append({'Type': 'volume', 'Name': 'test-work', 'Destination': '/work', 'RW': True})
        self.assertTrue(all(run.verify_container(info, IMAGE, self.index, 'test').values()))
        for key, value in (('NetworkMode', 'host'), ('ReadonlyRootfs', False), ('Privileged', True),
                           ('CapDrop', []), ('CapAdd', ['SYS_ADMIN']), ('PidMode', 'host'),
                           ('Memory', 0), ('NanoCpus', 0), ('PidsLimit', 0)):
            changed = json.loads(json.dumps(info))
            changed['HostConfig'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                run.verify_container(changed, IMAGE, self.index, 'test')
        with patch.object(run.sys, 'platform', 'darwin'):
            info['Mounts'][0]['Source'] = '/host_mnt' + str(self.index.parent)
            run.verify_container(info, IMAGE, self.index, 'test')
            info['Mounts'][0]['Source'] = '/host_mnt/Users/private-references'
            with self.assertRaises(RuntimeError):
                run.verify_container(info, IMAGE, self.index, 'test')


if __name__ == '__main__':
    unittest.main()
