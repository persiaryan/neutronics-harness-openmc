"""Revision policy and campaign guards; synthetic evidence, no live execution."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from evaluation.candidates import assessment, verdict_migration as revision
from evaluation.benchmark_suite import scoring
from evaluator import run as exporter
from experiments import migrate_confirmation_verdicts as migration
from prompts.confirmation import TASKS


class VerdictRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.checks=assessment.blank_checks()
        self.checks['geometry'].update(interfaces=True,extent_and_map=True,domain=False,boundaries=None)
        self.gates=assessment.blank_gates()
        for n in ('model_builds','valid_geometry','required_data'):
            self.gates[n]=dict(passed=True,cause=None)
        self.gates['openmc_runs']['detail']='openmc_abnormal_exit'
        self.report=dict(status='stopped',case='synthetic',
            stop=dict(stage='transport',cause='evaluator',detail='openmc_abnormal_exit'),
            gates=self.gates,checks=self.checks,diagnostic_score=scoring.score(self.gates,self.checks),
            fidelity={'synthetic':'verified by legacy replay'},
            phases={p:{} for p in ('export','export-inspection','export-boundaries','transport')})
        self.legacy=dict(evidence_status='insufficient',score=None,reason=revision.LEGACY_REASON)
        self.save()
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(exporter,'docker',side_effect=AssertionError('No live execution')))
        self.replay=self.stack.enter_context(patch.object(revision.verify,'review_assessment',return_value=self.legacy))
        self.native=self.stack.enter_context(patch.object(revision.lost_particles,'review',
            return_value=dict(evidence_status='coherent',attribution='model',reason='maximum_lost_particles')))
        self.stack.enter_context(patch.object(revision.run,'target',
            return_value=dict(protocol={'export_image':'synthetic'})))
        self.stack.enter_context(patch.object(revision,'accepted_export',return_value=(b'<xml/>',{})))
        self.stack.enter_context(patch.object(revision,'inspection_record',return_value={}))
        self.stack.enter_context(patch.object(revision.assessment,'fidelity_checks',return_value=self.checks))

    def save(self):
        exporter.write_json(self.root/'report.json',self.report)
        exporter.write_json(self.root/'review.json',self.legacy)

    def revise(self):
        return revision.revise(self.root,self.root/'data.xml',self.root/'reference')

    def test_qualified_failure_uses_existing_zero_gate_rule_and_keeps_unknowns(self):
        original={p.name:p.read_bytes() for p in self.root.iterdir()}
        result=self.revise()
        self.assertEqual(result['verdict']['score'],0.)
        self.assertIs(result['verdict']['strict_correct'],False)
        self.assertIsNone(result['verdict']['checks']['geometry']['boundaries'])
        self.assertIsNone(result['verdict']['gates']['finite_statepoint']['passed'])
        self.assertEqual(result['verdict']['stop']['cause'],'model')
        self.assertEqual(result['verdict']['diagnostic_score']['status'],'model_gate_failure')
        self.assertEqual({p.name:p.read_bytes() for p in self.root.iterdir()},original)

    def test_success_is_reconstructed_without_change(self):
        self.legacy.clear()
        self.legacy.update(evidence_status='coherent',status='verified_from_retained_execution',
                           score=100.,strict_correct=True)
        self.report.update(status='assessed',gates={n:dict(passed=True,cause=None) for n in self.gates})
        self.report.pop('stop')
        checks={g:{n:True for n in values} for g,values in self.checks.items()}
        self.report['checks']=checks
        self.report['diagnostic_score']=scoring.score(self.report['gates'],checks)
        self.save()
        result=self.revise()
        self.assertEqual(result['decision'],'unchanged_after_reconstruction')
        self.assertEqual(result['verdict']['score'],100.)
        self.assertEqual(result['verdict']['checks'],checks)
        self.native.assert_not_called()

    def test_other_missing_or_contradictory_evidence_is_not_reclassified(self):
        for status,reason in (('contradictory',revision.LEGACY_REASON),('insufficient','missing XML')):
            with self.subTest(status=status):
                self.legacy.update(evidence_status=status,reason=reason)
                self.save()
                with self.assertRaisesRegex(ValueError,'does not resolve'):self.revise()
        self.native.assert_not_called()

    def test_failed_native_qualification_propagates(self):
        self.native.side_effect=ValueError('provenance mismatch')
        with self.assertRaisesRegex(ValueError,'provenance'):self.revise()

    def test_unknown_gate_cannot_be_promoted(self):
        self.report['gates']['finite_statepoint']=dict(passed=True,cause=None)
        self.save()
        with self.assertRaisesRegex(ValueError,'gates'):self.revise()

    def test_altered_checks_and_unreached_phases_are_rejected(self):
        for field,value in (
            ('checks',assessment.blank_checks()),
            ('phases',dict(self.report['phases'],extra={})),
            ('candidate_keff',{'mean':1.})):
            original=deepcopy(self.report)
            try:
                self.report[field]=value;self.save()
                with self.subTest(field=field):
                    with self.assertRaises(ValueError):self.revise()
            finally:self.report=original;self.save()

    def test_changed_original_review_is_rejected(self):
        exporter.write_json(self.root/'review.json',dict(self.legacy,score=0.))
        with self.assertRaisesRegex(ValueError,'Original review'):self.revise()


class MigrationGuardTests(unittest.TestCase):
    def setUp(self):
        rows=[]
        for c in TASKS:
            for m in migration.MODELS:
                for a in migration.ARMS:
                    for n in range(1,6):
                        i=str(len(rows)+1).zfill(3)
                        rows.append(dict(id=i,model=m,arm=a,case=c,repeat=n,path='runs/'+i,
                                         plan_sha256='plan',state='pending'))
        self.manifest=dict(rows=rows)
        self.progress=dict(state='stopped',rows=deepcopy(rows))
        for r in self.progress['rows'][:11]:r['state']='finished'
        self.progress['rows'][11]['state']='incident'

    def test_exact_consumed_prefix_preserved(self):
        consumed=migration.consumed_rows(self.manifest,self.progress)
        self.assertEqual([r['id'] for r in consumed],[str(i).zfill(3) for i in range(1,13)])
        self.assertEqual(consumed[-1]['state'],'incident')

    def test_changed_assignments_active_trials_and_nonprefix_consumption_rejected(self):
        for change in ('identity','order','active','gap','running','escape'):
            progress=deepcopy(self.progress);manifest=deepcopy(self.manifest)
            if change=='identity':progress['rows'][0]['arm']='other'
            if change=='order':progress['rows'][0],progress['rows'][1]=progress['rows'][1],progress['rows'][0]
            if change=='active':progress['rows'][11]['state']='started'
            if change=='gap':progress['rows'][0]['state']='pending'
            if change=='running':progress['state']='running'
            if change=='escape':
                progress['rows'][0]['path']=manifest['rows'][0]['path']='runs/../../other'
            with self.subTest(change=change):
                with self.assertRaises(ValueError):migration.consumed_rows(manifest,progress)

    def test_duplicate_and_missing_trials_are_rejected(self):
        self.manifest['rows'][1]['id']=self.manifest['rows'][0]['id']
        with self.assertRaisesRegex(ValueError,'Duplicate'):migration.consumed_rows(self.manifest,self.progress)
        self.manifest['rows'].pop()
        with self.assertRaisesRegex(ValueError,'count'):migration.consumed_rows(self.manifest,self.progress)

    def test_source_changes_are_narrowly_allowlisted(self):
        qualification=json.loads(migration.QUALIFICATION.read_text())
        recorded={'builder/route.py':'unchanged','evaluation/candidates/phase_evidence.py':'previous'}
        current={p:exporter.digest(Path(p).read_bytes()) for p in migration.ADDITIONS}
        current.update({'builder/route.py':'unchanged',
            'evaluation/candidates/phase_evidence.py':qualification['implementation']['evaluation/candidates/phase_evidence.py']})
        migration.source_revision(recorded,current,qualification)
        for changed in (dict(current,**{'builder/route.py':'changed'}),
                        dict(current,**{'unexpected.py':'new'}),
                        dict(current,**{'evaluation/candidates/lost_particles.py':'changed'})):
            with self.assertRaises(ValueError):migration.source_revision(recorded,changed,qualification)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'keep').write_text('original')
            with self.assertRaisesRegex(ValueError,'fresh'):migration.migrate(root/'missing',root)
            self.assertEqual((root/'keep').read_text(),'original')

    def test_counts_keep_pending_separate(self):
        rows=[dict(verdict=dict(strict_correct=True)) for _ in range(11)]
        rows.append(dict(verdict=dict(strict_correct=False)))
        self.assertEqual(migration.summary(rows,228),
            dict(protocol_success=11,evaluated_failure=1,unscored_incident=0,pending=228))

    def test_migration_writes_and_reverifies_separate_records_without_changing_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);campaign=root/'campaign';campaign.mkdir()
            output=root/'revision'
            for name,value in (('manifest.json',self.manifest),('progress.json',self.progress),
                               ('launch.json',{})):
                exporter.write_json(campaign/name,value)
            (campaign/'manifest.sha256').write_text('retained original seal')
            before=migration.inventory(campaign)
            sources={'README.md':exporter.digest(Path('README.md').read_bytes())}
            def reconstructed(campaign,manifest,row,index):
                success=row['id']!='012'
                return dict(decision='unchanged_after_reconstruction' if success else 'qualified_lost_particle_model_failure',
                            verdict=dict(strict_correct=success,score=100. if success else 0.,
                                         evidence_status='coherent'))
            with patch.object(migration,'bindings',return_value=(
                    self.manifest,self.progress,self.progress['rows'][:12],root/'data.xml')), \
                 patch.object(migration.historical,'sources',return_value=sources), \
                 patch.object(migration,'reconstruct',side_effect=reconstructed):
                report=migration.migrate(campaign,output)
                self.assertEqual(report['status'],'passed')
                self.assertEqual(report['changed_ids'],['012'])
                self.assertEqual(len(list((output/'verdicts').glob('*.json'))),12)
                result=migration.verify_migration(output)
                self.assertEqual(result['verdicts_verified'],12)
                self.assertEqual(migration.inventory(campaign),before)
                path=output/'verdicts/012.json'
                value=json.loads(path.read_text());value['verdict']['score']=100.
                exporter.write_json(path,value)
                with self.assertRaisesRegex(ValueError,'verdict'):migration.verify_migration(output)


if __name__=='__main__':
    unittest.main()
