"""Retained references require exact physical bindings and fresh observations."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.confirmation import cases, references
from evaluation.representation import references as prospective
from evaluation.benchmark_suite import scoring
from evaluator.run import digest, write_json


class ReferenceRequalification(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.case='indc107_reflective_pin'
        (self.root/'reference.py').write_text('literal source')
        spec=cases.SPECS[self.case]
        records=[dict(kind=kind,keff=dict(mean=1.,std_dev=.0001),entropy_drift=0.) for kind in
                 ['primary']*3+['long_inactive','point_source']]
        self.value=dict(format='confirmation-private-reference-v1',case=self.case,
            case_version=spec['version'],task_sha256=spec['source_sha256'],
            technical_status='technically_qualified',rubric=scoring.identity(),
            protocol_sha256=digest(references.PROTOCOL.read_bytes()),grading_enabled=False,
            scientific_review='pending_owner_review',records=records,numerical=references.numerical(records),
            files=references.inventory(self.root))
        self.reseal(self.value)

    def reseal(self,value):
        write_json(self.root/'manifest.json',value)
        (self.root/'seal.sha256').write_text(digest((self.root/'manifest.json').read_bytes())+'\n')

    def test_predecessor_accepts_provenance_without_claiming_current_identity(self):
        self.assertEqual(prospective.predecessor(self.root,self.case),self.value)

    def test_changed_artifact_or_seal_is_rejected(self):
        (self.root/'reference.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'inventory'):prospective.predecessor(self.root,self.case)
        (self.root/'reference.py').write_text('literal source')
        (self.root/'seal.sha256').write_text('0'*64)
        with self.assertRaisesRegex(ValueError,'seal'):prospective.predecessor(self.root,self.case)

    def test_resealed_wrong_task_criteria_or_numerics_are_rejected(self):
        for key,value in [('task_sha256','0'*64),('case_version',99),('protocol_sha256','0'*64),
                          ('rubric',{}),('grading_enabled',True),('numerical',{})]:
            with self.subTest(key=key):
                changed=copy.deepcopy(self.value);changed[key]=value;self.reseal(changed)
                with self.assertRaises(ValueError):prospective.predecessor(self.root,self.case)

    def test_unchanged_variant_is_required_before_any_rebinding(self):
        folder=self.root/self.case;folder.mkdir()
        source=b'def build_model():\n    settings.seed = 1\n'
        (folder/'reference.py').write_bytes(source)
        run=folder/'run-1-primary';run.mkdir();(run/'reference.py').write_bytes(source)
        value=dict(records=[dict(folder=run.name,kind='primary',seed=11)])
        with self.assertRaisesRegex(ValueError,'variant differs'):
            prospective.reconstruct(self.case,folder,Path('unused'),value)


if __name__=='__main__':unittest.main()
