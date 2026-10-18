"""Lost-particle classification and negative evidence controls; no live dispatch."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation.candidates import lost_particles, phase_evidence, run
from evaluator import run as exporter
from evaluator.evidence import InsufficientEvidence
from evaluator.profiles import PROFILE
from evaluator.transport_input import accepted_export
from tests import test_transport_receipts as transport_fixture


class LostParticleTests(unittest.TestCase):
    def setUp(self):
        # Reuse only the contained-execution fixture; all tested verification is real.
        fixture = transport_fixture.TransportReceiptTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.directory, self.folder, self.index = fixture.directory, fixture.folder, fixture.index
        self.source = b'# synthetic export source; never executed\n'
        (self.directory / 'candidate.py').write_bytes(self.source)
        self.source_hash = exporter.digest(self.source)
        self.set_field(self.directory/'export/manifest.json', 'candidate_sha256', self.source_hash)
        xml, identity = accepted_export(self.directory/'export')
        self.xml = xml
        self.write(self.folder/'export-provenance.json', identity)
        self.set_field(self.folder/'manifest.json', 'candidate_sha256', self.source_hash)
        for name in ('container.json', 'frozen-container.json'):
            self.set_field(self.folder/name, 'Image', PROFILE['transport_image'])
        self.set_field(self.folder/'manifest.json', 'image_id', PROFILE['transport_image'])
        self.value = dict(status='failed', reason='openmc_abnormal_exit', xml_load='passed',
                          transport='failed', statepoint_validation='not_run', cleanup_confirmed=True)
        self.write(self.folder/'result.json', self.value)
        self.write(self.folder/'openmc-process.json', dict(exit_code=255, stop_reason=None))
        (self.folder/'openmc-stderr.txt').write_text(' WARNING: particle lost\n '+lost_particles.FATAL+'\n')
        (self.folder/'staging-stdout.txt').write_text(exporter.digest(xml)+'\n')
        (self.folder/'model.xml').write_bytes(xml)
        (self.folder/'solver-version-stdout.txt').write_text('OpenMC version 0.15.3\n')
        worker = Path('evaluator/runtime/transport_worker.py').read_bytes()
        path = self.folder/'controller-sources/runtime/transport_worker.py'
        path.parent.mkdir(parents=True)
        path.write_bytes(worker)
        runtime = dict(worker_sha256=exporter.digest(worker), solver_files={'native':'synthetic-hash'})
        self.write(self.folder/'runtime-identity.json', runtime)
        self.write(self.folder/'runtime-identity-stdout.txt', runtime)
        data = dict(index_sha256='synthetic-data', files={
            'fuel.h5': dict(sha256='fuel-data', bytes=20, tables=[['neutron','U235'],['neutron','U238']])})
        self.write(self.folder/'data-before.json', data)
        self.write(self.folder/'data-after.json', data)
        self.goal = dict(protocol={k:PROFILE[k] for k in ('export_image','transport_image')},
                         runtime=runtime, data=data)
        loaded = dict(status='loaded', openmc_version='0.15.3', model_xml_sha256=exporter.digest(xml),
                      sampling=dict(particles=500,batches=20,inactive=5,generations_per_batch=2,seed=23),
                      scientific_inputs_changed=False, boundary_checks={'synthetic':True})
        # Literal sampling comes from the independently declared XML fixture.
        self.write(self.folder/'artifacts/xml-load.json', loaded)
        for path in (self.folder/'artifacts').iterdir():
            if path.name not in ('model.xml','xml-load.json'):
                path.unlink()
        self.write(self.folder/'artifacts.json', {
            p.name:dict(bytes=p.stat().st_size,sha256=exporter.digest(p.read_bytes()))
            for p in (self.folder/'artifacts').iterdir()})
        self.export_double = patch.object(lost_particles, 'export_outcome', return_value=dict(cause=None,reason=None))
        self.export_double.start()
        self.addCleanup(self.export_double.stop)

    def write(self, path, value):
        exporter.write_json(path, value)

    def set_field(self, path, key, value):
        data = json.loads(path.read_bytes());data[key]=value
        exporter.write_json(path,data)

    def review(self):
        return lost_particles.review(self.directory,self.goal,self.index)

    def snapshot(self):
        return {str(p.relative_to(self.directory)):p.read_bytes()
                for p in self.directory.rglob('*') if p.is_file()}

    def test_explicit_review_attributes_failure_without_scoring_or_editing(self):
        before=self.snapshot()
        result=self.review()
        self.assertEqual(result['attribution'],'model')
        self.assertIs(result['protocol_success'],False)
        self.assertIs(result['campaign_score_assigned'],False)
        self.assertEqual(before,self.snapshot())

    def test_legacy_policy_remains_unattributed(self):
        self.assertFalse(run.native_model_failure(self.value,self.folder))
        with self.assertRaises(InsufficientEvidence):
            phase_evidence.transport_failure(self.directory,self.goal,self.index,self.source_hash)

    def test_source_constraint_legacy_diagnostic_is_preserved(self):
        (self.folder/'openmc-stderr.txt').write_text('ERROR: Too few source sites satisfied the constraints\n')
        self.assertTrue(run.native_model_failure(self.value,self.folder))
        self.assertFalse(lost_particles.diagnostic(self.value,self.folder))

    def test_exit_code_alone_and_unrecognized_or_ambiguous_messages_are_rejected(self):
        for text in ('', 'ERROR: unknown failure', 'quoted '+lost_particles.FATAL,
                     'WARNING: '+lost_particles.FATAL, lost_particles.FATAL+' extra',
                     lost_particles.FATAL+'\nERROR: other failure',
                     lost_particles.FATAL+'\n'+lost_particles.FATAL):
            with self.subTest(text=text):
                (self.folder/'openmc-stderr.txt').write_text(text)
                self.assertFalse(lost_particles.diagnostic(self.value,self.folder))

    def test_interruptions_signals_and_malformed_receipts_are_rejected(self):
        for process in (dict(exit_code=255,stop_reason='timeout'), dict(exit_code=-9,stop_reason=None),
                        dict(exit_code=0,stop_reason=None), dict(exit_code=255.0,stop_reason=None),
                        dict(exit_code='255',stop_reason=None), dict(exit_code=255),
                        dict(exit_code=255,stop_reason=None,extra=True), []):
            with self.subTest(process=process):
                self.write(self.folder/'openmc-process.json',process)
                self.assertFalse(lost_particles.diagnostic(self.value,self.folder))

    def test_incomplete_phase_flags_never_establish_failure(self):
        for key,value in (('xml_load','failed'),('transport','not_run'),('status','budget_exceeded'),
                          ('statepoint_validation','passed'),('cleanup_confirmed',False)):
            with self.subTest(key=key):
                self.assertFalse(lost_particles.diagnostic(dict(self.value,**{key:value}),self.folder))

    def test_missing_process_receipts_and_native_artifacts_are_insufficient(self):
        names=[p+'-process.json' for p in
               ('preflight','solver-version','runtime-identity','staging','xml-load','openmc')]
        names+=['openmc-stderr.txt','artifacts/model.xml','artifacts/xml-load.json']
        for name in names:
            path=self.folder/name;raw=path.read_bytes()
            try:
                path.unlink()
                with self.subTest(name=name):
                    with self.assertRaises(InsufficientEvidence):self.review()
            finally:path.write_bytes(raw)

    def test_changed_xml_data_and_provenance_are_rejected(self):
        mutations=(
            ('manifest.json','candidate_sha256','another-source'),
            ('manifest.json','model_xml_sha256','another-xml'),
            ('export-provenance.json','candidate_sha256','another-source'),
            ('data-after.json','index_sha256','another-index'),
            ('runtime-identity.json','worker_sha256','another-worker'),
            ('xml-load-process.json','exit_code',1),
            ('frozen-container.json','Image','another-image'))
        for name,key,value in mutations:
            path=self.folder/name;raw=path.read_bytes()
            try:
                self.set_field(path,key,value)
                with self.subTest(name=name):
                    with self.assertRaises((ValueError,RuntimeError)):self.review()
            finally:path.write_bytes(raw)
        path=self.folder/'model.xml';raw=path.read_bytes()
        try:
            path.write_bytes(raw+b'\n')
            with self.assertRaisesRegex(ValueError,'XML bytes'):self.review()
        finally:path.write_bytes(raw)

    def test_changed_native_artifact_or_worker_is_rejected(self):
        for name in ('artifacts/model.xml','controller-sources/runtime/transport_worker.py'):
            path=self.folder/name;raw=path.read_bytes()
            try:
                path.write_bytes(raw+b'\n')
                with self.subTest(name=name):
                    with self.assertRaises((ValueError,RuntimeError)):self.review()
            finally:path.write_bytes(raw)

    def test_unconfirmed_cleanup_and_incomplete_freeze_are_rejected(self):
        for name,field in (('result.json','cleanup_confirmed'),('frozen-container.json','State')):
            path=self.folder/name;raw=path.read_bytes()
            try:
                self.set_field(path,field,False if field=='cleanup_confirmed' else dict(Running=True,Paused=False))
                with self.subTest(name=name):
                    with self.assertRaises((ValueError,RuntimeError)):self.review()
            finally:path.write_bytes(raw)

    def test_unverified_export_cannot_be_attributed(self):
        with patch.object(lost_particles,'export_outcome',return_value=dict(cause='model',reason='export-failed')):
            with self.assertRaisesRegex(ValueError,'export'):self.review()


if __name__=='__main__':
    unittest.main()
