"""Frozen A/D protocol, launch gating and annotation evidence; no live calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from builder import region_skill
from builder.context import write_json
from experiments import region_ad as ad, region_ad_analysis as analysis, dashboard_campaign as campaign
from tests.test_request_profiles import synthetic_body, launch
from builder.context import request_setup
from tests.fixtures.responses import mock_response


class ADTests(unittest.TestCase):
    def prepared(self, root):
        index=root/'index';index.write_text('synthetic')
        setups={}
        for model in campaign.MODELS:
            body=synthetic_body();body['reasoning']['effort']='medium' if 'luna' in model else 'low'
            setups[model]=request_setup(body)
        file=root/'setups.json';write_json(file,setups)
        with patch.object(ad,'dependencies',return_value=dict(status='passed',checks={},provider_contacted=False)):
            ad.prepare(root/'pilot',index=index,setups=file)
        return root/'pilot'

    def test_freezes_36_slots_protocol_and_annotations_without_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ad.builder,'run') as dispatch:
            root=self.prepared(Path(tmp));m=ad.verify_plan(root)
            self.assertEqual((m['sessions'],m['maximum_model_requests']),(36,576))
            self.assertEqual((root/'scientific-protocol.json').read_bytes(),ad.protocol()[0])
            self.assertEqual((root/'region-procedure.md').read_bytes(),region_skill.material()[0])
            labels=ad.read(root/'annotations-template.json')['records']
            self.assertEqual(len(labels),36)
            self.assertEqual({r['status'] for r in labels},{'pending'})
            dispatch.assert_not_called()

    def test_manifest_protocol_and_skill_tampering_fail_before_dispatch(self):
        for change in ('manifest','protocol','skill','local'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root=self.prepared(Path(tmp))
                name={'manifest':'manifest.json','protocol':'scientific-protocol.json',
                      'skill':'region-procedure.md','local':'local-qualification.json'}[change]
                if change=='manifest':
                    value=ad.read(root/name);value['authoring_seconds']=1;write_json(root/name,value)
                else:
                    (root/name).write_text('{}')
                with patch.object(campaign,'execute') as dispatch, self.assertRaises(ValueError):
                    campaign.run_campaign(root)
                dispatch.assert_not_called()
                self.assertFalse((root/'launch.json').exists())

    def test_missing_real_delivery_blocks_launch_without_consuming_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.prepared(Path(tmp))
            with patch.object(ad,'dependencies',return_value=dict(status='passed')), \
                 patch.object(campaign,'execute') as dispatch:
                self.assertEqual(ad.readiness(root)['checks']['provider_controls'],'blocked')
                with self.assertRaisesRegex(ValueError,'qualification incomplete'):
                    campaign.run_campaign(root)
                dispatch.assert_not_called()
            self.assertFalse((root/'launch.json').exists())

    def test_newly_sealed_references_cannot_replace_frozen_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.prepared(Path(tmp))
            changed=dict(status='passed',checks={'reference_and_data:two_composition_5x5':
                dict(status='passed',detail=dict(package_sha256='different-reference'))})
            with patch.object(ad,'dependencies',return_value=changed):
                self.assertEqual(ad.readiness(root)['checks']['frozen_dependency_identity'],'blocked')

    def test_native_receipt_cannot_count_as_live_delivery(self):
        folder,result,_,setup,_=launch(self,assistance=region_skill.ASSISTANCE,cap=1,
            profile='authoring-requests-16-v1',constrain_setup=True,response_bytes=mock_response())
        self.assertEqual(result['status'],'completed')
        manifest=ad.read(folder/'manifest.json');manifest['wall_seconds']=60
        write_json(folder/'manifest.json',manifest)
        with patch.object(ad,'CASE','reflective_pin_cell'):
            self.assertFalse(ad.delivery_receipt(folder,'test-model','D',setup,live=False)['provider_contacted'])
            with self.assertRaisesRegex(ValueError,'actor/model/arm'):
                ad.delivery_receipt(folder,'test-model','D',setup,live=True)

    def live_fixture(self):
        folder,result,_,setup,_=launch(self,assistance=region_skill.ASSISTANCE,cap=1,
            profile='authoring-requests-16-v1',constrain_setup=True,response_bytes=mock_response())
        self.assertEqual(result['status'],'completed')
        m=ad.read(folder/'manifest.json');m.update(mode='subscription',wall_seconds=120)
        write_json(folder/'manifest.json',m)
        size=len((folder/'response-01.sse').read_bytes())
        write_json(folder/'upstream-01.json',dict(http_status=200,completion_observed=True,
            stream_validation='passed',response_bytes_forwarded=size,stop_reason='response_completed'))
        return folder,setup

    def test_live_proof_requires_exact_prompt_setup_and_complete_provider_response(self):
        for change in ('none','response','upstream','prompt','extra-response'):
            with self.subTest(change=change):
                folder,setup=self.live_fixture()
                if change=='response':(folder/'response-01.sse').write_bytes(b'')
                if change=='upstream':write_json(folder/'upstream-01.json',dict(http_status=200,completion_observed=False))
                if change=='extra-response':(folder/'response-02.sse').write_bytes(mock_response())
                if change=='prompt':
                    body=ad.read(folder/'request-01.json');body['input'][-1]['content'][0]['text']='changed'
                    write_json(folder/'request-01.json',body)
                with patch.object(ad,'CASE','reflective_pin_cell'):
                    if change=='none':
                        self.assertTrue(ad.delivery_receipt(folder,'test-model','D',setup,live=True)['provider_contacted'])
                    else:
                        with self.assertRaises((ValueError,RuntimeError)):
                            ad.delivery_receipt(folder,'test-model','D',setup,live=True)

    def test_unstarted_assignments_do_not_become_failures_or_zero_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.prepared(Path(tmp))
            report=analysis.summarize(root,root/'annotations-template.json')
            self.assertEqual(len(report['groups']),12)
            for group in report['groups']:
                self.assertEqual(group['outcomes']['pending'],3)
                self.assertEqual(group['outcomes']['evaluated_failure'],0)
                self.assertIsNone(group['protocol_success_fraction'])
            self.assertTrue(all(c['D_minus_A'] is None for c in report['comparisons']))

    def test_scientific_failure_and_unscored_incident_keep_different_denominators(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.prepared(Path(tmp));progress=ad.read(root/'progress.json')
            sample=progress['rows'][0]
            cell=[r for r in progress['rows'] if (r['model'],r['arm'],r['case']) ==
                  (sample['model'],sample['arm'],sample['case'])]
            for row,state in zip(cell,('finished','finished','incident')):
                row['state']=state
            write_json(root/'progress.json',progress)
            for row in cell[:2]:
                folder=root/row['path']/'runs'/row['case']/'assessment'
                folder.mkdir(parents=True);write_json(folder/'report.json',{})
            def review(folder,index):
                success=cell[0]['id'] in str(folder)
                return dict(evidence_status='coherent',score=100 if success else 0,strict_correct=success)
            with patch.object(analysis,'review_assessment',side_effect=review):
                result=analysis.summarize(root)
            group=next(g for g in result['groups'] if (g['model'],g['arm'],g['case']) ==
                       (sample['model'],sample['arm'],sample['case']))
            self.assertEqual(group['outcomes'],dict(protocol_success=1,evaluated_failure=1,unscored_incident=1,pending=0))
            self.assertAlmostEqual(group['protocol_success_fraction'],1/3)
            self.assertEqual(group['conditional_success_fraction_scored'],.5)

    def test_manual_annotation_is_bound_to_source_and_line_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.prepared(Path(tmp));row=ad.read(root/'manifest.json')['rows'][0]
            path=Path(row['path'])/'runs'/row['case']/'candidate.py'
            (root/path).parent.mkdir(parents=True)
            (root/path).write_text('derived = base\nderived &= constraint\noutside = domain & ~base\n')
            digest=ad.campaign.sha(root/path)
            value=dict(status='demonstrated',source_sha256=digest,reviewer='synthetic-reviewer',
                sharing='assignment shares the same object',mutation='shared intersection changes',
                downstream_use='complement observes the shared object',
                damaging_consequence='synthetic semantic evidence; not a real scientific annotation',
                evidence=[dict(path=str(path),sha256=digest,lines=[1,3])],limitations='test fixture')
            self.assertEqual(analysis.annotation(root,row,value),'demonstrated')
            for change in ('source','line','consequence'):
                bad=copy.deepcopy(value)
                if change=='source':bad['source_sha256']='0'*64
                if change=='line':bad['evidence'][0]['lines']=[1,99]
                if change=='consequence':bad['damaging_consequence']=None
                with self.subTest(change=change),self.assertRaises(ValueError):
                    analysis.annotation(root,row,bad)
