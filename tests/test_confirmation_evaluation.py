"""Independent physical witnesses and failure controls for confirmation semantics."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from evaluation.confirmation import cases, references
from evaluation.benchmark_suite.suite_checks import settings_checks
from evaluation.candidates.assessment import fidelity_checks
from evaluator.profiles import CONFIRMATION_PROTOCOL, BOUNDARY_PROTOCOL
from experiments import run
from prompts.prepare import build_prompt


class ConfirmationEvaluationTests(unittest.TestCase):
    def test_literal_material_witnesses(self):
        witnesses=[
            ('offset_plate_bank',[.26,0,0],'void'),
            ('offset_plate_bank',[.30,0,0],'zirconium'),
            ('offset_plate_bank',[0,4.1,0],'water'),
            ('staggered_seven_pin_cluster',[.7,1.2,0],'fuel_B'),
            ('three_annular_fuel_channels',[-1.5,-.8,0],'water'),
            ('three_annular_fuel_channels',[-1.2,-.8,0],'fuel_B'),
            ('separated_twin_bundles',[-3.85,-.65,0],'fuel_A'),
            ('separated_twin_bundles',[3.85,-.65,0],'fuel_B'),
            ('cross_shaped_mixture',[0,0,0],'mixture'),
            ('cross_shaped_mixture',[2,2,0],'water'),
            ('indc107_reflective_pin',[1.2701,0,0],'water'),
            ('indc107_reflective_pin',[1.2699,0,0],'uranium_metal'),
            ('stepped_axial_mixture',[3,0,-10],'mixture'),
            ('stepped_axial_mixture',[3,0,0],'water'),
            ('stepped_axial_mixture',[0,2,10],'water'),
            ('wrapped_eight_pin_channel',[0,0,0],'water'),
            ('wrapped_eight_pin_channel',[0,.53,0],'zirconium'),
            ('wrapped_eight_pin_channel',[2.15,0,0],'zirconium'),
            ('mixed_boundary_fuel_slab',[0,0,0],'fuel_B'),
            ('cylindrical_void_sleeve',[4.1,0,0],'void'),
            ('cylindrical_void_sleeve',[4.1,0,13],'water'),
            ('cylindrical_void_sleeve',[9,9,0],'water')]
        for case,p,expected in witnesses:
            with self.subTest(case=case,point=p):
                self.assertEqual(cases.expected(case,p),expected)

    def test_temperature_depends_on_fuel_location(self):
        self.assertEqual(cases.temperature('dual_temperature_pin_pair',[-.65,0,0]),293.6)
        self.assertEqual(cases.temperature('dual_temperature_pin_pair',[.65,0,0]),600.)
        self.assertEqual(cases.temperature('dual_temperature_pin_pair',[.65,.45,0]),293.6)

    def test_mixed_and_reflective_boundary_requirements(self):
        rows=cases.requirements('mixed_boundary_fuel_slab')['requirements']
        actual={(r['selector']['axis'],r['selector']['side']):r['expected']
                for r in rows if r['property']=='boundary_type'}
        self.assertEqual(actual,{(0,'lower'):'vacuum',(0,'upper'):'vacuum',
                                 (1,'lower'):'reflective',(1,'upper'):'reflective',
                                 (2,'lower'):'reflective',(2,'upper'):'reflective'})
        self.assertTrue(all(r['expected']=='reflective' for r in
            cases.requirements('dual_temperature_pin_pair')['requirements'] if r['property']=='boundary_type'))

    def settings(self):
        root=ET.fromstring('<model><settings/></model>');s=root.find('settings')
        sampling=dict(particles=10000,batches=400,inactive=100,generations_per_batch=2,seed=1,source='uniform')
        for name,value in sampling.items():
            if name!='source':ET.SubElement(s,name).text=str(value)
        ET.SubElement(s,'temperature_tolerance').text='1'
        source=ET.SubElement(s,'source',type='independent')
        space=ET.SubElement(source,'space',type='box')
        ET.SubElement(space,'parameters').text='-.1 -.1 -5 .1 .1 5'
        ET.SubElement(source,'angle',type='isotropic')
        ET.SubElement(source,'energy',type='watt',parameters='988000 2.249e-6')
        constraints=ET.SubElement(source,'constraints')
        ET.SubElement(constraints,'fissionable').text='true'
        ET.SubElement(s,'entropy_mesh').text='1'
        mesh=ET.SubElement(s,'mesh',id='1',type='regular')
        for name,value in [('dimension','6 6 12'),('lower_left','-1.95 -1.95 -18'),('upper_right','1.95 1.95 18')]:
            ET.SubElement(mesh,name).text=value
        return root,sampling

    def test_source_and_entropy_extents_are_independent(self):
        root,sampling=self.settings()
        result=settings_checks('restricted_source_nine_pin',root,sampling)
        self.assertEqual(result['status'],'passed_checks')
        root.find('./settings/source/space/parameters').text='-1.95 -1.95 -18 1.95 1.95 18'
        result=settings_checks('restricted_source_nine_pin',root,sampling)
        checks=fidelity_checks('restricted_source_nine_pin',dict(settings=result))
        self.assertFalse(checks['physics_settings']['source'])
        self.assertTrue(checks['physics_settings']['entropy_mesh_and_output'])

    def test_new_authoring_plan_selects_new_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'plan'
            run.prepare(folder,assistance='guided_construction',cases=['cross_shaped_mixture'])
            self.assertEqual(json.loads((folder/'plan.json').read_text())['evaluator_protocol'],CONFIRMATION_PROTOCOL)
            self.assertIn('Cross-shaped',build_prompt('cross_shaped_mixture'))

    def test_wrong_protocol_is_rejected_before_builder_inputs_are_read(self):
        from builder.route import prepare
        from evaluator.contracts import FACTORY
        from evaluator.profiles import FACTORY_PROFILE
        for case,protocol in [('cross_shaped_mixture',BOUNDARY_PROTOCOL),
                              ('reflective_pin_cell',CONFIRMATION_PROTOCOL)]:
            with self.subTest(case=case),self.assertRaisesRegex(ValueError,'confirmation protocol'):
                prepare(case,FACTORY,FACTORY_PROFILE,protocol,Path('/nonexistent-input'))

    def test_incomplete_or_inconsistent_reference_runs_cannot_qualify(self):
        records=[dict(kind='primary',keff=dict(mean=1.,std_dev=.0001,uncertainty='one sigma'),entropy_drift=0.) for _ in range(3)]
        records += [dict(records[0],kind=kind) for kind in ('long_inactive','point_source')]
        self.assertTrue(references.numerical(records)['passed'])
        bad=copy.deepcopy(records);bad[-1]['keff']['mean']=1.01
        self.assertFalse(references.numerical(bad)['passed'])
        bad=copy.deepcopy(records);bad[0]['entropy_drift']=None
        self.assertFalse(references.numerical(bad)['passed'])
        with self.assertRaises(ValueError):references.numerical(records[:3])
