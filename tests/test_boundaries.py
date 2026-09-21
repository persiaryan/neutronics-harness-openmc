"""Literal comparator regressions, independent of the boundary observer."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from evaluation.scientific import boundaries
from evaluation.candidates import boundary_assessment


def observation():
    return dict(observer_version=boundaries.VERSION,model_xml_sha256='fixture',
        domain=dict(status='established',bounds_cm=[[-1.,1.],[-2.,2.],[-3.,3.]]),coverage={},
        surfaces=[dict(ref='surface:81',boundary_type='white',effective_albedo=.25,albedo_applicable=True)],
        faces=[dict(ref='face',axis=0,side='lower',coordinate_cm=-1.,limitations=[],surface_refs=['surface:81'])])


def specification(value=.25):
    return dict(format='boundary-task-requirements-v1',source=dict(path='public fixture',clause='x lower face'),
        requirements=[dict(id='albedo',property='effective_albedo',expected=value,comparison=dict(kind='exact'),
            observations_needed=['root domain','participating face','effective albedo'],
            selector=dict(kind='root_box_face',axis=0,side='lower',domain_bounds_cm=[[-1.,1.],[-2.,2.],[-3.,3.]],
                          location_comparison=dict(kind='exact')))])


class BoundaryComparisonTests(unittest.TestCase):
    def verdict(self,obs,spec):
        return boundaries.compare(obs,spec)['verdicts'][0]

    def test_reuse_values_and_explicit_tolerance(self):
        self.assertEqual(self.verdict(observation(),specification())['verdict'],'conformity_established')
        self.assertEqual(self.verdict(observation(),specification(1.))['verdict'],'nonconforming')
        spec=specification(.25001)
        self.assertEqual(self.verdict(observation(),spec)['verdict'],'nonconforming')
        spec['requirements'][0]['comparison']=dict(kind='absolute',tolerance=.00002)
        self.assertEqual(self.verdict(observation(),spec)['verdict'],'conformity_established')

    def test_missing_observation_is_not_a_pass(self):
        obs=observation();obs['faces']=[]
        result=self.verdict(obs,specification())
        self.assertEqual((result['verdict'],result['cause']),('indeterminate','missing_or_ambiguous_face_observation'))

    def test_missing_effective_property_is_indeterminate(self):
        obs=observation();obs['surfaces'][0].pop('effective_albedo')
        self.assertEqual(self.verdict(obs,specification())['cause'],'missing_effective_property_observation')

    def test_mismatch_remains_visible_beside_unknown(self):
        spec=specification(1.);other=deepcopy(spec['requirements'][0]);other['id']='missing'
        other['selector']['axis']=1;spec['requirements'].append(other)
        result=boundary_assessment.evaluate(observation(),spec,dict(nontransmission_surfaces=[]))
        self.assertEqual([v['verdict'] for v in result['verdicts']],['nonconforming','indeterminate'])
        self.assertIsNone(result['score_check'])

    def test_nonexternal_behavior_retains_coverage_limit(self):
        result=boundary_assessment.evaluate(observation(),specification(),dict(nontransmission_surfaces=[dict(id=82,boundary='reflective')]))
        self.assertEqual(result['verdicts'][0]['verdict'],'conformity_established')
        self.assertIsNone(result['score_check'])

    def test_changed_domain_cannot_match_an_unrelated_surface(self):
        obs=observation();obs['domain']['bounds_cm'][1]=[-4.,4.]
        self.assertEqual(self.verdict(obs,specification())['cause'],'required_domain_location_not_matched')
