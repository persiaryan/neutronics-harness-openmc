"""Native-control receipt and attribution tests with explicit process doubles."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.representation import controls, native
from evaluator.run import digest, write_json
from tests.fixtures.boundary_receipts import inspector_info


class NativeControlReceipts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.index=self.root/'cross_sections.xml';self.index.write_text('<cross_sections/>')
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.data=dict(index_sha256=digest(self.index.read_bytes()),files={},snapshot='synthetic')
        self.stack.enter_context(patch.object(native.transport,'data_identity',return_value=self.data))
        self.xml=controls.source_controls()[0]['xml']

    def retain(self):
        folder=self.root/'native'
        info=inspector_info();info['Image']=native.IMAGE
        info['Config'].update(Entrypoint=['python'],Cmd=['-I','-B','-c','import time; time.sleep(3600)'],Env=['OMP_NUM_THREADS=1'])
        info['HostConfig'].update(Memory=3*1024**3,Tmpfs=native.TMPFS)
        info['Mounts']=[dict(Type='bind',Source=str(self.root.resolve()),Destination='/data',RW=False)]
        xml=native.input_xml(self.xml,self.index)
        stdout=dict(status='sampled',openmc_version='0.15.3',mode='sample',model_xml_sha256=digest(xml),seed=41,
                    native_files={'/opt/openmc/bin/openmc':'a'*64,'/opt/openmc/lib/libopenmc.so':'b'*64},
                    python_binding_sha256={'core.py':'c'*64},positions=[[-.5,.25,.1],[.5,.25,.1]]*2048)
        def docker(*args):
            if args[:2]==('image','inspect'):return json.dumps([dict(Id=native.IMAGE)])
            if args[0]=='inspect':return json.dumps([info])
            return ''
        with patch.object(native.run,'docker',side_effect=docker),patch.object(native.run,'bounded',
            return_value=dict(exit_code=0,stop_reason=None,stdout=json.dumps(stdout).encode(),stderr=b'')):
            result=native.execute(self.xml,folder,self.index,'sample')
        return folder,result

    def test_controller_output_reconstructs_from_retained_receipts(self):
        folder,result=self.retain()
        self.assertEqual(native.record(folder,self.index,expected_xml=self.xml,mode='sample'),result)
        row=native.source_row(controls.source_controls()[0],result,None)
        self.assertTrue(row['passed']);self.assertEqual(row['counts']['fuel'],4096)

    def test_changed_worker_xml_process_data_and_mount_are_rejected(self):
        folder,_=self.retain()
        for name,raw in [('worker.py',b'# changed'),('model.xml',b'<model/>'),
                         ('execution.json',b'{"exit_code":0,"stop_reason":"timeout"}'),
                         ('data-after.json',b'{}'),('container-checks.json',b'{}')]:
            original=(folder/name).read_bytes();(folder/name).write_bytes(raw)
            with self.subTest(name=name),self.assertRaises((ValueError,KeyError)):
                native.record(folder,self.index,expected_xml=self.xml,mode='sample')
            (folder/name).write_bytes(original)

    def test_timeout_and_unrelated_crash_are_not_lost_particle_controls(self):
        folder=self.root/'failure';folder.mkdir()
        (folder/'stderr.txt').write_text('Maximum number of lost particles has been reached')
        for code,reason in [(255,'timeout'),(1,None),(0,None)]:
            result=dict(status='native_process_failed',execution=dict(exit_code=code,stop_reason=reason))
            self.assertFalse(native.lost_particle_failure(folder,result))
        result=dict(status='native_process_failed',execution=dict(exit_code=255,stop_reason=None))
        self.assertTrue(native.lost_particle_failure(folder,result))
        (folder/'stderr.txt').write_text('unrelated failure')
        self.assertFalse(native.lost_particle_failure(folder,result))

    def test_finite_sampling_never_accepts_water_as_equivalent_fuel_source(self):
        _,result=self.retain();result['positions']=[[0,.25,.1]]*4096
        row=native.source_row(controls.source_controls()[0],result,None)
        self.assertFalse(row['passed'])


if __name__=='__main__': unittest.main()
