"""Task version provenance and narrowly scoped prelaunch compatibility."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.candidates import run, verify
from evaluation.confirmation import references
from evaluator.profiles import PROFILE, CONFIRMATION_PROTOCOL


class ConfirmationVersionTests(unittest.TestCase):
    def test_version_two_is_written_and_wrong_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'source.py';source.write_text('def build_model():\n    return None\n')
            goal=dict(protocol={k:PROFILE[k] for k in ('export_image','transport_image')},
                      index={'manifest_sha256':'synthetic'},reference={})
            with patch.object(run,'target',return_value=goal),patch.object(run,'preflight',side_effect=ValueError('stop before native work')),patch.object(run,'clean_resources'):
                report=run.evaluate('cylindrical_void_sleeve',root/'assessment',index=root/'index',candidate=source,
                                    evaluator_protocol=CONFIRMATION_PROTOCOL)
            self.assertEqual(report['assignment']['case_version'],2)
            assignment=json.loads((root/'assessment/assignment.json').read_text())
            assignment['case_version']=1
            report['assignment']=assignment
            (root/'assessment/assignment.json').write_text(json.dumps(assignment))
            (root/'assessment/report.json').write_text(json.dumps(report))
            review=verify.review_assessment(root/'assessment',root/'index')
            self.assertEqual(review['evidence_status'],'contradictory')
            self.assertIn('task version changed',review['reason'])

    def test_compatibility_rejects_physical_or_criteria_changes(self):
        current=references.identity()
        previous=references.compatibility()['previous_identities'][1]
        self.assertTrue(references.identity_matches('cross_shaped_mixture',previous))
        self.assertFalse(references.identity_matches('indc107_reflective_pin',previous))
        bad=copy.deepcopy(previous);bad['evaluation/confirmation/protocol.json']='0'*64
        self.assertFalse(references.identity_matches('cross_shaped_mixture',bad))
        bad=copy.deepcopy(previous);bad['evaluation/confirmation/cases.py']='0'*64
        self.assertFalse(references.identity_matches('cross_shaped_mixture',bad))
        bad=copy.deepcopy(previous);bad['evaluation/confirmation/references.py']='0'*64
        self.assertFalse(references.identity_matches('cross_shaped_mixture',bad))
