"""Conformance/coverage separation and prospective retained-report integration.

Execution providers below are doubles. Native geometry and source-law controls
are deliberately run and recorded by separate qualification commands.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from evaluation.candidates import assessment, representation, verify
from evaluation.benchmark_suite import scoring, suite_checks
from evaluation.benchmark_suite.suite_cases import probes, SPECS
from evaluator.profiles import REPRESENTATION_PROTOCOL, CONFIRMATION_PROTOCOL, FACTORY_PROFILE, assessment_route
from evaluator.contracts import FACTORY
from evaluator.run import digest, write_json
from observation_contracts import evaluation_definition
from tests.test_source_space import model
from tests import test_source_evidence as legacy_evidence


class ConformanceTests(unittest.TestCase):
    def test_missing_reference_at_admission_is_insufficient_not_a_forged_v6_report(self):
        import tempfile
        from evaluation.candidates import run
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'report'
            with patch.object(run,'target',side_effect=ValueError('reference unavailable')),patch.object(run,'clean_resources'):
                report=run.evaluate('indc107_reflective_pin',output,index=Path(tmp)/'index',candidate=Path(tmp)/'unused.py',
                                    evaluator_protocol=REPRESENTATION_PROTOCOL)
            self.assertEqual(report['status'],'incomplete')
            self.assertEqual(report['conclusion']['conformance'],'indeterminate')
            self.assertEqual(verify.review_assessment(output,Path(tmp)/'index')['evidence_status'],'insufficient')

    def test_false_requirement_survives_unknown_without_inventing_score(self):
        gates={name:dict(passed=True,cause=None) for name in assessment.blank_gates()}
        checks={category:{name:True for name in items} for category,items in assessment.blank_checks().items()}
        checks['geometry'].update(domain=False,boundaries=None)
        score=scoring.score(gates,checks)
        result=representation.conclusion(gates,checks,{},score)
        self.assertIsNone(score['score'])
        self.assertEqual(result['conformance'],'nonconforming')
        self.assertFalse(result['evaluation_complete'])
        self.assertFalse(result['score_complete'])
        self.assertIn('geometry.domain',result['known_mismatches'])
        invalid=representation.conclusion(gates,checks,{},score,evidence_available=False)
        self.assertEqual(invalid['conformance'],'indeterminate')
        self.assertEqual(invalid['known_mismatches'],[])

    def test_source_unknown_preserves_independent_settings_and_detailed_failure(self):
        root,sampling=model('reflective_pin_cell')
        settings=suite_checks.settings_checks('reflective_pin_cell',root,sampling)
        settings['checks']=[c for c in settings['checks'] if c['field']!='source_fissionable']
        settings['checks'].append(dict(field='source_accepted_support',passed=False))
        settings['unassessed_options']=['constraints/energy_bounds']
        fidelity=dict(settings=settings)
        values=representation.fidelity_checks('reflective_pin_cell',fidelity)['physics_settings']
        self.assertEqual(values,dict(physics=True,sampling=True,source=None,entropy_mesh_and_output=True))
        self.assertTrue(all(v is None for v in assessment.fidelity_checks('reflective_pin_cell',fidelity)['physics_settings'].values()))
        checks=representation.fidelity_checks('reflective_pin_cell',fidelity)
        result=representation.conclusion(assessment.blank_gates(),checks,fidelity,dict(score=None))
        self.assertEqual(result['conformance'],'nonconforming')
        self.assertIn('settings.source_accepted_support',result['known_mismatches'])


class ProspectiveEvidence(unittest.TestCase):
    # Reuse the established synthetic receipt harness, not its legacy test methods.
    setUp=legacy_evidence.SourceEvidence.setUp
    review=legacy_evidence.SourceEvidence.review
    snapshot=legacy_evidence.SourceEvidence.snapshot

    def retain_prospective(self):
        self.observation['observations']=[['ok',[[1,293.6]]]]*len(probes(self.case)[0])
        report=legacy_evidence.SourceEvidence.retain(self)
        case='indc107_reflective_pin'
        self.observation['observations']=[['ok',[[1,293.6]]]]*len(probes(case)[0])
        roles=({'1':'uranium_metal'},[])
        self.stack.enter_context(patch.object(representation,'check_materials',return_value=roles))
        source_observation=dict(observer_version='source-domain-observation-v1',limitations=[],
                                cells=[dict(id=1,material_id=1)],witnesses=[])
        self.stack.enter_context(patch.object(verify.source_domains,'record',return_value=source_observation))
        root=ET.fromstring((self.folder/'model.xml').read_bytes())
        assignment=report['assignment'];assignment['case']=case;assignment['case_version']=SPECS[case]['version']
        route=assessment_route(FACTORY,FACTORY_PROFILE,REPRESENTATION_PROTOCOL)
        prompt=verify.build_prompt(case,contract=FACTORY).encode();route['prompt_sha256']=digest(prompt)
        assignment['assessment_route']=route
        assignment['representation_semantics']=representation.identity()
        specification=verify.boundaries.requirements(case)
        assignment['scientific_boundary']=dict(observer=verify.boundaries.NEXT_VERSION,comparison=verify.boundaries.COMPARISON,
            requirements_sha256=digest(json.dumps(specification,sort_keys=True).encode()))
        fidelity=representation.assess(case,root,self.observation,assignment['sampling'],boundary_result=self.boundary,
                                      source_observation=source_observation)
        checks=representation.fidelity_checks(case,fidelity,self.observation)
        comparison=assessment.complete_checks(checks,self.record,self.goal['reference']['primary_mean'],
            dict(leakage_probability=True,leakage_boundary_consistency=True))
        score=scoring.score(report['gates'],checks)
        report.update(format='private-candidate-diagnostic-v6',case=case,fidelity=fidelity,checks=checks,
                      diagnostic_score=score,comparison=comparison,
                      observation_definition=evaluation_definition(scoring.RUBRIC,scoring.identity()['sha256'],REPRESENTATION_PROTOCOL))
        phase=dict(status='inspected',cleanup_confirmed=True)
        report['phases']['export-source-domains']=phase
        report['conclusion']=representation.conclusion(report['gates'],checks,fidelity,score)
        for name,value in [('assignment.json',assignment),('report.json',report),('export-fidelity.json',fidelity),
                           ('boundary-requirements.json',specification),('export-source-domains/result.json',phase)]:
            p=self.folder/name;p.parent.mkdir(exist_ok=True);write_json(p,value)
        (self.folder/'prompt.txt').write_bytes(prompt)
        return report

    def test_prospective_report_reconstructs_both_conclusion_and_score(self):
        report=self.retain_prospective();before=self.snapshot()
        reviewed=self.review()
        self.assertEqual(reviewed['evidence_status'],'coherent',reviewed)
        self.assertEqual(report['conclusion']['conformance'],'nonconforming')
        self.assertEqual(before,self.snapshot())

    def test_forged_conclusion_and_semantics_are_rejected(self):
        report=self.retain_prospective()
        report['conclusion']['conformance']='conforming_within_protocol'
        write_json(self.folder/'report.json',report)
        self.assertEqual(self.review()['evidence_status'],'contradictory')
        report=self.retain_prospective()
        report['assignment']['representation_semantics']['files']['evaluation/candidates/representation.py']='0'*64
        write_json(self.folder/'assignment.json',report['assignment']);write_json(self.folder/'report.json',report)
        self.assertEqual(self.review()['evidence_status'],'contradictory')

    def test_prospective_receipt_cannot_be_relabelled_as_original_campaign(self):
        report=self.retain_prospective()
        report['assignment']['assessment_route']['evaluator_protocol']=CONFIRMATION_PROTOCOL
        write_json(self.folder/'report.json',report)
        self.assertEqual(self.review()['evidence_status'],'contradictory')

    def test_missing_source_receipt_remains_insufficient(self):
        self.retain_prospective()
        with patch.object(verify.source_domains,'record',side_effect=FileNotFoundError('missing source receipt')):
            self.assertEqual(self.review()['evidence_status'],'insufficient')

    def test_reader_preserves_reviewed_conclusion_without_recalculating_score(self):
        from dashboard.contracts import normalize_evaluation
        report=self.retain_prospective();review=self.review()
        view=normalize_evaluation(report,review)
        self.assertEqual(view['status'],'supported',view)
        self.assertTrue(view['trusted'],view)
        self.assertEqual(view['report']['conclusion'],report['conclusion'])
        review.pop('conclusion')
        self.assertFalse(normalize_evaluation(report,review)['trusted'])

    def test_execution_selects_new_workers_and_records_separate_source_phase(self):
        from evaluation.candidates import run
        self.retain_prospective()
        xml=(self.folder/'model.xml').read_bytes();source=self.folder/'candidate.py'
        record=dict(self.record,receipts={})
        def solver(export,output,**kwargs):
            output.mkdir()
            (output/'openmc-stdout.txt').write_text('Leakage Fraction = 0 +/- 0\n')
            return dict(status='calculated_unreviewed',cleanup_confirmed=True)
        with ExitStack() as stack:
            stack.enter_context(patch.object(run,'clean_resources'))
            stack.enter_context(patch.object(run,'preflight',return_value=(self.folder/'index.xml',dict(status='passed'))))
            stack.enter_context(patch.object(run.exporter,'evaluate',return_value=self.phase))
            stack.enter_context(patch.object(run,'accepted_export',return_value=(xml,dict(candidate_sha256=digest(source.read_bytes())))))
            stack.enter_context(patch.object(run,'inspect_xml',return_value=self.observation))
            stack.enter_context(patch.object(run,'inspection_record',return_value=self.observation))
            observer=stack.enter_context(patch.object(run.boundaries,'observe',return_value=dict(status='inspected',cleanup_confirmed=True)))
            sources=stack.enter_context(patch.object(run.source_domains,'observe',return_value=dict(status='inspected',cleanup_confirmed=True)))
            stack.enter_context(patch.object(run,'transport_profile',return_value=dict(required_tables=[])))
            stack.enter_context(patch.object(run.solver,'transport',side_effect=solver))
            stack.enter_context(patch.object(run.receipts,'transport_record',return_value=record))
            report=run.evaluate('indc107_reflective_pin',self.folder/'prospective-run',index=self.folder/'index.xml',
                                candidate=source,evaluator_protocol=REPRESENTATION_PROTOCOL)
        self.assertEqual(report['status'],'assessed',report.get('error'))
        self.assertEqual(report['format'],'private-candidate-diagnostic-v6')
        self.assertIn('export-source-domains',report['phases'])
        self.assertEqual(observer.call_args.kwargs['version'],run.boundaries.NEXT_VERSION)
        self.assertEqual(sources.call_args.kwargs['wall_seconds'],120)
        self.assertEqual(report['conclusion']['conformance'],'nonconforming')


if __name__=='__main__': unittest.main()
