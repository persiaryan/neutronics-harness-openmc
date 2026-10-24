"""Real prospective controllers with Docker/process doubles; no native claim."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.scientific import boundaries, inspection, source_domains
from evaluator.run import digest, write_json
from tests.fixtures.boundary_receipts import inspector_info, model


class ProspectiveReceipts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.xml=model('1')

    def retain(self, capability, stdout):
        folder=self.root/capability
        def docker(*args):
            if args[0]=='ps': return ''
            if args[:2]==('image','inspect'): return json.dumps([dict(Id=inspection.IMAGE)])
            if args[0]=='inspect': return json.dumps([inspector_info()])
            return ''
        points=[[.1,.2,.3]] if capability=='source-domains-v1' else []
        with patch.object(inspection,'docker',side_effect=docker), patch.object(inspection,'bounded',
            return_value=dict(exit_code=0,stop_reason=None,stdout=json.dumps(stdout).encode(),stderr=b'')):
            inspection.inspect_xml(self.xml,points,folder,capability=capability)
        return folder,points

    def source(self):
        stdout=dict(status='inspected',openmc_version='0.15.3',observer_version='source-domain-observation-v1',
                    model_xml_sha256=digest(self.xml),cells=[],witnesses=[],limitations=['synthetic'])
        return self.retain('source-domains-v1',stdout)

    def test_source_binding_rejects_changed_input_worker_process_and_query(self):
        folder,points=self.source()
        self.assertEqual(source_domains.record(folder,self.xml,points)['limitations'],['synthetic'])
        with self.assertRaises(ValueError): source_domains.record(folder,self.xml,[[.1,.2,.4]])
        for name,value in [('worker.py',b'# changed'),('execution.json',b'{"exit_code":0,"stop_reason":"timeout"}'),
                           ('input.json',b'{}'),('container-checks.json',b'{}')]:
            original=(folder/name).read_bytes();(folder/name).write_bytes(value)
            with self.subTest(name=name),self.assertRaises((ValueError,KeyError)):
                source_domains.record(folder,self.xml,points)
            (folder/name).write_bytes(original)

    def test_missing_and_unclean_receipts_cannot_claim_observations(self):
        from evaluator.evidence import InsufficientEvidence
        folder,points=self.source()
        result=json.loads((folder/'result.json').read_bytes());result['cleanup_confirmed']=False
        write_json(folder/'result.json',result)
        with self.assertRaises(InsufficientEvidence): source_domains.record(folder,self.xml,points)
        (folder/'execution.json').unlink()
        with self.assertRaises(InsufficientEvidence): source_domains.record(folder,self.xml,points)

    def test_v3_worker_cannot_be_accepted_as_v2(self):
        stdout=dict(status='inspected',openmc_version='0.15.3',observer_version=boundaries.NEXT_VERSION,
                    model_xml_sha256=digest(self.xml),surfaces=[],faces=[],coverage={},domain=dict(status='indeterminate',cause='synthetic'))
        folder,_=self.retain('effective-boundary-v3',stdout)
        self.assertEqual(boundaries.record(folder,self.xml,version=boundaries.NEXT_VERSION),stdout)
        with self.assertRaises(ValueError): boundaries.record(folder,self.xml)
        manifest=json.loads((folder/'manifest.json').read_bytes())
        manifest['format']='private-boundary-inspection-v2';write_json(folder/'manifest.json',manifest)
        with self.assertRaises(ValueError): boundaries.record(folder,self.xml)

    def test_shape_mismatch_is_versioned_and_keeps_face_unknowns(self):
        from evaluation.representation.controls import specification
        obs=dict(observer_version=boundaries.NEXT_VERSION,model_xml_sha256='synthetic',surfaces=[],faces=[],coverage={},
                 domain=dict(status='indeterminate',cause='unbounded_root_domain',
                             shape_evidence=dict(kind='unbounded',method='complete_arrangement_occupancy')))
        result=boundaries.compare(obs,specification())
        self.assertEqual(result['verdicts'][-1]['verdict'],'nonconforming')
        self.assertTrue(all(r['verdict']=='indeterminate' for r in result['verdicts'][:-1]))
        obs['observer_version']=boundaries.VERSION
        self.assertTrue(all(r['verdict']=='indeterminate' for r in boundaries.compare(obs,specification())['verdicts']))


if __name__=='__main__': unittest.main()
