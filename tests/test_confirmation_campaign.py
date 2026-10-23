"""Campaign inventory and negative launch paths; no model or native calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments import region_confirmation as campaign
from evaluation.confirmation import references
from prompts.confirmation import TASKS


class ConfirmationCampaignTests(unittest.TestCase):
    def prepare(self, root):
        mapping={case:str(root/'missing'/case) for case in TASKS}
        (root/'refs.json').write_text(json.dumps(mapping))
        (root/'data.xml').write_text('synthetic data identity')
        setups={m:dict(request_configuration=dict(reasoning=dict(effort='medium' if 'luna' in m else 'low')))
                for m in campaign.MODELS}
        (root/'setups.json').write_text(json.dumps(setups))
        for name in ('controls','end-to-end'):
            (root/(name+'.json')).write_text(json.dumps(dict(status='failed',rows=[])))
        with patch.object(references,'target',side_effect=ValueError('unqualified test reference')):
            campaign.prepare(root/'campaign',root/'refs.json',root/'data.xml',root/'setups.json',
                             root/'controls.json',root/'end-to-end.json')
        return root/'campaign'

    def test_240_assignments_and_pending_results_do_not_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(campaign,'execute') as execute:
            output=self.prepare(Path(tmp).resolve())
            m=references.read(output/'manifest.json')
            self.assertEqual((len(m['rows']),m['maximum_model_requests']),(240,3840))
            self.assertEqual(len({(r['case'],r['model'],r['arm'],r['repeat']) for r in m['rows']}),240)
            report=campaign.analyze(output)
            self.assertEqual(len(report['groups']),48)
            self.assertTrue(all(g['outcomes']['pending']==5 and g['success_fraction'] is None for g in report['groups']))
            self.assertTrue(all(r['requests_received'] is None for r in report['rows']))
            execute.assert_not_called()
            self.assertFalse((output/'launch.json').exists())

    def test_failures_incidents_and_resource_missingness_stay_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=self.prepare(Path(tmp).resolve())
            progress=references.read(output/'progress.json')
            sample=progress['rows'][0]
            cell=[r for r in progress['rows'] if (r['model'],r['case'],r['arm'])==
                  (sample['model'],sample['case'],sample['arm'])]
            for row,state in zip(cell,('finished','finished','incident')):
                row['state']=state
            (output/'progress.json').write_text(json.dumps(progress))
            for row in cell[:2]:
                folder=output/row['path']/'runs'/row['case']/'assessment'
                folder.mkdir(parents=True)
                (folder/'report.json').write_text(json.dumps(dict(elapsed_seconds=3.)))
            def review(folder,*args,**kwargs):
                success=cell[0]['path'] in str(folder)
                return dict(evidence_status='coherent',score=100. if success else 0.,strict_correct=success)
            with patch.object(campaign,'review_assessment',side_effect=review):
                report=campaign.analyze(output)
            group=next(g for g in report['groups'] if (g['model'],g['case'],g['arm'])==
                       (sample['model'],sample['case'],sample['arm']))
            self.assertEqual(group['outcomes'],dict(protocol_success=1,evaluated_failure=1,
                                                   unscored_incident=1,pending=2))
            self.assertIsNone(group['success_fraction'])
            self.assertEqual(group['conditional_success_fraction_scored'],.5)
            self.assertEqual(group['consumed'],3)
            self.assertEqual(group['effort']['requests_received'],dict(total=None,available=0,missing=3))
            self.assertEqual(group['effort']['assessment_seconds'],dict(total=6.,available=2,missing=1))
            self.assertEqual(next(r for r in report['rows'] if r['id']==cell[0]['id'])['state'],'finished')

    def test_unqualified_references_block_live_dispatch_without_consuming(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(campaign,'execute') as execute:
            output=self.prepare(Path(tmp).resolve())
            with self.assertRaisesRegex(ValueError,'Technical qualification'):
                campaign.dispatch(output,Path(tmp)/'provider-controls',3840)
            self.assertFalse((output/'launch.json').exists())
            execute.assert_not_called()

    def test_resealed_changed_budget_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=self.prepare(Path(tmp).resolve())
            m=references.read(output/'manifest.json');m['maximum_model_requests']=1
            (output/'manifest.json').write_text(json.dumps(m))
            (output/'manifest.sha256').write_text(campaign.historical.sha(output/'manifest.json')+'\n')
            with self.assertRaisesRegex(ValueError,'budgets changed'):campaign.check(output)

    def test_resealed_duplicate_identifier_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=self.prepare(Path(tmp).resolve())
            m=references.read(output/'manifest.json');m['rows'][1]['id']=m['rows'][0]['id']
            (output/'manifest.json').write_text(json.dumps(m))
            (output/'manifest.sha256').write_text(campaign.historical.sha(output/'manifest.json')+'\n')
            with self.assertRaisesRegex(ValueError,'Duplicate assignment'):campaign.check(output)
