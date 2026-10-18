"""Reference evidence binding failures before any native work or code import."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.confirmation_reference_review import review
from evaluation.confirmation import references
from evaluator.run import digest


class ConfirmationReferenceReviewTests(unittest.TestCase):
    def fixture(self, root):
        source=b"raise AssertionError('reference source must never run on the host')\n"
        (root/'reference.py').write_bytes(source)
        rows=[dict(seed=s,folder='run-'+str(i)) for i,s in enumerate((11,23,37,53,71),1)]
        value=dict(records=rows,numerical={'passed':True},technical_status='technically_qualified',
                   source_sha256=digest(source))
        (root/'manifest.json').write_text(json.dumps(value))
        (root/'qualification.json').write_text(json.dumps(copy.deepcopy(value)))
        return value

    def test_changed_seed_cannot_be_promoted_by_a_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);value=self.fixture(root)
            value['records'][0]['seed']=99
            (root/'manifest.json').write_text(json.dumps(value))
            (root/'qualification.json').write_text(json.dumps(value))
            with patch.object(references,'target',return_value={}),self.assertRaisesRegex(ValueError,'seed matrix'):
                review('cross_shaped_mixture',root,root/'unused-index')

    def test_manifest_and_qualification_disagreement_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);value=self.fixture(root)
            value['records'][0]['seed']=99
            (root/'manifest.json').write_text(json.dumps(value))
            with patch.object(references,'target',return_value={}),self.assertRaisesRegex(ValueError,'summary binding'):
                review('cross_shaped_mixture',root,root/'unused-index')
